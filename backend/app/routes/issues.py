import asyncio
import json
import logging
from contextlib import suppress

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from app.services.analysis import analyze_issue
from app.services.gemma import GemmaServiceError
from app.services.github import GitHubServiceError, github_service, validate_repository_ref

router = APIRouter(tags=["issues"])
logger = logging.getLogger("panda.analysis")


def _raise_http_error(error: GitHubServiceError) -> None:
    raise HTTPException(status_code=error.status_code, detail={"code": error.code, "message": error.message}) from error


@router.post("/issues/{owner}/{repo}/{issue_number}/analyze")
async def analyze_selected_issue(owner: str, repo: str, issue_number: int) -> StreamingResponse:
    if issue_number < 1:
        raise HTTPException(status_code=400, detail={"code": "invalid_issue_number", "message": "Issue number must be positive."})
    try:
        ref = validate_repository_ref(owner, repo)
    except GitHubServiceError as error:
        _raise_http_error(error)

    async def events():
        queue: asyncio.Queue[dict] = asyncio.Queue()

        async def run_pipeline() -> None:
            try:
                result = await analyze_issue(ref, issue_number, progress=lambda stage: queue.put_nowait({"type": "stage", "stage": stage}))
                await queue.put({"type": "result", "data": result})
            except (GitHubServiceError, GemmaServiceError) as error:
                await queue.put({"type": "error", "code": error.code, "message": error.message, "status": error.status_code})
            except Exception as error:
                logger.error("[PANDA] Unexpected analysis failure: %s", type(error).__name__)
                await queue.put({"type": "error", "code": "analysis_failed", "message": "PANDA could not complete the issue analysis. Please retry.", "status": 502})

        task = asyncio.create_task(run_pipeline())
        try:
            while True:
                event = await queue.get()
                yield json.dumps(event, ensure_ascii=False) + "\n"
                if event["type"] in {"result", "error"}:
                    break
        finally:
            if not task.done():
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task

    return StreamingResponse(events(), media_type="application/x-ndjson", headers={"Cache-Control": "no-cache"})


@router.get("/issues")
async def list_issues(
    owner: str = Query(min_length=1, max_length=39),
    repo: str = Query(min_length=1, max_length=100),
    page: int = Query(default=1, ge=1),
    category: str = Query(default="ALL", max_length=32),
    search: str = Query(default="", max_length=256),
    difficulty: str = Query(default="ALL", max_length=32),
    skill: str = Query(default="ALL", max_length=32),
    effort: str = Query(default="ALL", max_length=32),
) -> dict:
    try:
        ref = validate_repository_ref(owner, repo)
        labels = await github_service.labels(ref)
        return await github_service.search_issues(
            ref, labels, page=page, category=category, search=search,
            difficulty=difficulty, skill=skill, effort=effort,
        )
    except GitHubServiceError as error:
        _raise_http_error(error)


@router.get("/issues/{owner}/{repo}/{issue_number}")
async def get_issue(owner: str, repo: str, issue_number: int) -> dict:
    if issue_number < 1:
        raise HTTPException(status_code=400, detail={"code": "invalid_issue_number", "message": "Issue number must be positive."})
    try:
        return await github_service.issue_detail(validate_repository_ref(owner, repo), issue_number)
    except GitHubServiceError as error:
        _raise_http_error(error)

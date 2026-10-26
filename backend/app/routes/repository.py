from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.github import GitHubServiceError, RepositoryRef, github_service, parse_repository_url

router = APIRouter(tags=["repository"])


class ConnectRequest(BaseModel):
    url: str = Field(min_length=1, max_length=500)


def _raise_http_error(error: GitHubServiceError) -> None:
    raise HTTPException(status_code=error.status_code, detail={"code": error.code, "message": error.message}) from error


@router.post("/repository/connect")
async def connect_repository(payload: ConnectRequest) -> dict:
    try:
        ref = parse_repository_url(payload.url)
        repository = await github_service.repository(ref)
        labels = await github_service.labels(ref)
        issue_count = await github_service.search_issues(ref, labels, category="ALL")
        return {
            **repository,
            "owner": repository["owner"],
            "labels": labels,
            "open_issues_count": issue_count["total_count"],
            "issue_search_limit_reached": issue_count["search_limit_reached"],
        }
    except GitHubServiceError as error:
        _raise_http_error(error)


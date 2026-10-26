"""Orchestrate GitHub evidence retrieval and one structured local model call."""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable
from typing import Any

from app.services.gemma import gemma_service
from app.services.github import GitHubServiceError, RepositoryRef, github_service
from app.services.repository import repository_context_builder

logger = logging.getLogger("panda.analysis")
logger.setLevel(logging.INFO)
ANALYSIS_CACHE_TTL = 1800
_analysis_cache: dict[tuple[str, str, int, str, str], tuple[float, dict[str, Any]]] = {}


async def analyze_issue(
    ref: RepositoryRef,
    issue_number: int,
    progress: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    started = time.monotonic()
    try:
        return await _analyze_issue(ref, issue_number, progress)
    finally:
        logger.info("[PANDA] Total analysis time: %.2fs", time.monotonic() - started)


async def _analyze_issue(
    ref: RepositoryRef,
    issue_number: int,
    progress: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    started = time.monotonic()
    logger.info("[PANDA] Issue #%s selected", issue_number)
    if progress:
        progress("READING ISSUE")
    issue, repository = await asyncio.gather(
        github_service.issue_detail(ref, issue_number),
        github_service.repository(ref),
    )
    cache_key = (ref.owner.lower(), ref.repo.lower(), issue_number, str(issue.get("updated_at") or ""), repository["default_branch"])
    cached = _analysis_cache.get(cache_key)
    if cached and cached[0] > time.monotonic():
        logger.info("[PANDA] Reusing cached analysis for issue #%s", issue_number)
        return {**cached[1], "cached": True, "latency_ms": round((time.monotonic() - started) * 1000)}

    if progress:
        progress("FINDING RELEVANT FILES")
    comments = await github_service.issue_comments(ref, issue_number) if issue.get("comments_count", 0) else []
    logger.info("[PANDA] Building repository context")
    context_started = time.monotonic()
    context, evidence = await repository_context_builder.build(ref, repository, issue, comments, progress)
    logger.info("[PANDA] Repository context completed: %.2fs", time.monotonic() - context_started)
    logger.info("[PANDA] Relevant source files: %s", len(context["source_files"]))
    logger.info("[PANDA] Relevant tests: %s", len(context["tests"]))

    if progress:
        progress("ASKING GEMMA")
    analysis, metrics = await gemma_service.analyze(context)
    if progress:
        progress("BUILDING RECOMMENDATION")
    elapsed_ms = round((time.monotonic() - started) * 1000)
    result = {
        "issue": {
            "number": issue["number"],
            "title": issue["title"],
            "html_url": issue["html_url"],
            "labels": issue["labels"],
            "author": issue["author"],
            "state": issue["state"],
            "updated_at": issue["updated_at"],
            "body": issue["body"],
        },
        "repository": {
            "full_name": repository["full_name"],
            "default_branch": repository["default_branch"],
            "language": repository.get("language"),
        },
        "analysis": analysis.model_dump(),
        "evidence": evidence,
        "model": metrics["model"],
        "latency_ms": elapsed_ms,
        "cached": False,
    }
    _analysis_cache[cache_key] = (time.monotonic() + ANALYSIS_CACHE_TTL, result)
    return result


def clear_analysis_cache() -> None:
    """Small hook used by verification to exercise repeated calls deterministically."""
    _analysis_cache.clear()

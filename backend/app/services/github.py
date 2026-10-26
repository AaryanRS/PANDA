"""GitHub REST API boundary and short-lived in-memory response cache."""

from __future__ import annotations

import asyncio
import base64
import logging
import re
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote, urlsplit

import httpx

from app.config.settings import settings
from app.services.classification import classify_issue

API_ROOT = "https://api.github.com"
PER_PAGE = 10
SEARCH_RESULT_LIMIT = 1000
CACHE_TTL_SECONDS = 60
CLASSIFICATION_CANDIDATE_LIMIT = SEARCH_RESULT_LIMIT
CLASSIFICATION_PAGE_SIZE = 100
PANDA_FILTERS = {
    "difficulty": {"Beginner", "Intermediate", "Advanced"},
    "skill": {"Python", "Testing", "Documentation", "Performance", "Backend", "Frontend", "Data / ML", "DevOps / CI", "Architecture", "Other"},
    "effort": {"Small", "Medium", "Large"},
}
logger = logging.getLogger("panda.github")


def _safe_exception_detail(error: BaseException) -> str:
    details: list[str] = []
    current: BaseException | None = error
    seen: set[int] = set()
    for _ in range(4):
        if current is None or id(current) in seen:
            break
        seen.add(id(current))
        message = str(current)
        if settings.github_token:
            message = message.replace(settings.github_token, "[REDACTED]")
        details.append(f"{type(current).__name__}: {message[:300]}")
        current = current.__cause__ or current.__context__
    return " <- ".join(details)

CATEGORY_ALIASES: dict[str, tuple[str, ...]] = {
    "BUG FIX": ("bug", "bugs", "bugfix", "bug fix", "defect", "type: bug"),
    "NEW FEATURE": ("enhancement", "feature", "feature request", "new feature", "type: feature"),
    "REFACTOR": ("refactor", "refactoring"),
    "TESTING": ("test", "tests", "testing"),
    "DOCUMENTATION": ("documentation", "docs", "documentation-needed"),
    "PERFORMANCE": ("performance", "perf", "optimization", "optimisation"),
}


class GitHubServiceError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 502):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


@dataclass(frozen=True)
class RepositoryRef:
    owner: str
    repo: str

    @property
    def full_name(self) -> str:
        return f"{self.owner}/{self.repo}"


def parse_repository_url(url: str) -> RepositoryRef:
    try:
        parsed = urlsplit(url.strip())
    except ValueError as exc:
        raise GitHubServiceError("invalid_url", "Enter a valid GitHub repository URL.", 400) from exc
    if parsed.scheme != "https" or parsed.netloc.lower() != "github.com" or parsed.query or parsed.fragment:
        raise GitHubServiceError("invalid_url", "Use a repository URL like https://github.com/owner/repository.", 400)
    path = parsed.path.strip("/")
    parts = path.split("/")
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise GitHubServiceError("invalid_url", "The URL must include both a GitHub owner and repository name.", 400)
    owner, repo = parts
    if repo.lower().endswith(".git"):
        repo = repo[:-4]
    if not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?", owner) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,100}", repo) or repo in {".", ".."}:
        raise GitHubServiceError("invalid_url", "The owner or repository name in this URL is malformed.", 400)
    return RepositoryRef(owner, repo)


def validate_repository_ref(owner: str, repo: str) -> RepositoryRef:
    if (
        not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?", owner)
        or not re.fullmatch(r"[A-Za-z0-9_.-]{1,100}", repo)
        or repo in {".", ".."}
    ):
        raise GitHubServiceError("invalid_repository", "The owner or repository name is malformed.", 400)
    return RepositoryRef(owner, repo)


def _normalized_label(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def _normalize_issue(issue: dict[str, Any]) -> dict[str, Any]:
    author = issue.get("user") or {}
    normalized = {
        "number": issue.get("number"),
        "title": issue.get("title") or "(untitled issue)",
        "body_excerpt": re.sub(r"\s+", " ", issue.get("body") or "").strip()[:280],
        "html_url": issue.get("html_url"),
        "labels": [label["name"] for label in issue.get("labels", []) if isinstance(label, dict) and isinstance(label.get("name"), str)],
        "created_at": issue.get("created_at"),
        "updated_at": issue.get("updated_at"),
        "comments_count": issue.get("comments", 0),
        "author": author.get("login") if isinstance(author, dict) else None,
        "state": issue.get("state"),
    }
    normalized["panda"] = classify_issue({**normalized, "body": issue.get("body") or ""})
    return normalized


class GitHubService:
    def __init__(self) -> None:
        self._cache: dict[tuple[Any, ...], tuple[float, Any]] = {}
        self._candidate_tasks: dict[tuple[Any, ...], asyncio.Task[tuple[list[dict[str, Any]], int]]] = {}
        self._headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "PANDA-open-source-workspace",
        }
        if settings.github_token:
            self._headers["Authorization"] = f"Bearer {settings.github_token}"

    def _read_cache(self, key: tuple[Any, ...]) -> Any | None:
        cached = self._cache.get(key)
        if cached is None:
            return None
        expiry, value = cached
        if expiry <= time.monotonic():
            self._cache.pop(key, None)
            return None
        return value

    def _write_cache(self, key: tuple[Any, ...], value: Any, ttl: int = CACHE_TTL_SECONDS) -> Any:
        self._cache[key] = (time.monotonic() + ttl, value)
        return value

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> tuple[Any, httpx.Headers]:
        safe_url = str(httpx.URL(API_ROOT).join(path)).split("?", 1)[0]
        try:
            async with httpx.AsyncClient(base_url=API_ROOT, headers=self._headers, timeout=20) as client:
                response = await client.get(path, params=params)
        except httpx.TimeoutException as exc:
            logger.warning("[PANDA] GitHub request failed url=%s error=%s", safe_url, _safe_exception_detail(exc))
            raise GitHubServiceError("github_unavailable", "GitHub did not respond in time. Please retry.", 503) from exc
        except httpx.HTTPError as exc:
            logger.warning("[PANDA] GitHub request failed url=%s error=%s", safe_url, _safe_exception_detail(exc))
            raise GitHubServiceError("github_unavailable", "GitHub could not be reached. Please retry.", 503) from exc

        if response.status_code == 404:
            raise GitHubServiceError("repository_not_found", "GitHub could not find that repository or issue.", 404)
        if response.status_code in (403, 429) and (
            response.status_code == 429
            or response.headers.get("X-RateLimit-Remaining") == "0"
            or "rate limit" in response.text.lower()
        ):
            advice = " Add an optional GITHUB_TOKEN to improve API access." if not settings.github_token else " Try again after GitHub's rate limit resets."
            raise GitHubServiceError("github_rate_limit", f"GitHub API rate limit reached.{advice}", 429)
        if response.status_code >= 500:
            raise GitHubServiceError("github_unavailable", "GitHub is temporarily unavailable. Please retry.", 503)
        if not response.is_success:
            raise GitHubServiceError("github_request_failed", "GitHub could not complete this request.", 502)
        try:
            return response.json(), response.headers
        except ValueError as exc:
            logger.warning("[PANDA] GitHub response parsing failed url=%s exception=%s", safe_url, type(exc).__name__)
            raise GitHubServiceError("github_unexpected_response", "GitHub returned an unexpected response.", 502) from exc

    async def repository(self, ref: RepositoryRef) -> dict[str, Any]:
        key = ("repository", ref.owner.lower(), ref.repo.lower())
        cached = self._read_cache(key)
        if cached is not None:
            return cached
        data, _ = await self._get(f"/repos/{ref.owner}/{ref.repo}")
        if not isinstance(data, dict):
            raise GitHubServiceError("github_unexpected_response", "GitHub returned an unexpected repository response.")
        owner_data = data.get("owner") or {}
        if not isinstance(owner_data, dict):
            raise GitHubServiceError("github_unexpected_response", "GitHub returned incomplete repository metadata.")
        required = ("name", "full_name", "default_branch", "html_url")
        if not all(data.get(field) for field in required) or not owner_data.get("login"):
            raise GitHubServiceError("github_unexpected_response", "GitHub returned incomplete repository metadata.")
        return self._write_cache(key, {
            "owner": owner_data["login"],
            "name": data["name"],
            "full_name": data["full_name"],
            "description": data.get("description"),
            "default_branch": data["default_branch"],
            "language": data.get("language"),
            "stars": data.get("stargazers_count", 0),
            "html_url": data["html_url"],
        })

    async def labels(self, ref: RepositoryRef) -> list[str]:
        key = ("labels", ref.owner.lower(), ref.repo.lower())
        cached = self._read_cache(key)
        if cached is not None:
            return cached
        labels: list[str] = []
        for page in range(1, 11):
            data, _ = await self._get(f"/repos/{ref.owner}/{ref.repo}/labels", {"per_page": 100, "page": page})
            if not isinstance(data, list):
                raise GitHubServiceError("github_unexpected_response", "GitHub returned an unexpected labels response.")
            labels.extend(label["name"] for label in data if isinstance(label, dict) and isinstance(label.get("name"), str))
            if len(data) < 100:
                break
        return self._write_cache(key, labels)

    def category_labels(self, category: str, labels: list[str]) -> list[str] | None:
        if category.strip().upper() == "ALL":
            return []
        normalized = {_normalized_label(alias) for alias in CATEGORY_ALIASES.get(category.strip().upper(), ())}
        if not normalized:
            raise GitHubServiceError("invalid_category", "Choose a supported issue category.", 400)
        return [label for label in labels if _normalized_label(label) in normalized]

    async def search_issues(
        self,
        ref: RepositoryRef,
        labels: list[str],
        page: int = 1,
        category: str = "ALL",
        search: str = "",
        difficulty: str = "ALL",
        skill: str = "ALL",
        effort: str = "ALL",
    ) -> dict[str, Any]:
        category = category.strip().upper()
        search = search.strip()[:256]
        normalized_filters: dict[str, str] = {}
        for name, value in (("difficulty", difficulty), ("skill", skill), ("effort", effort)):
            candidate = value.strip()
            if candidate.casefold() == "all":
                normalized_filters[name] = "ALL"
                continue
            canonical = next((item for item in PANDA_FILTERS[name] if item.casefold() == candidate.casefold()), None)
            if canonical is None:
                raise GitHubServiceError("invalid_panda_filter", f"Choose a supported PANDA {name} filter.", 400)
            normalized_filters[name] = canonical
        if page > SEARCH_RESULT_LIMIT // PER_PAGE:
            raise GitHubServiceError(
                "search_result_limit",
                "PANDA can browse at most 1,000 GitHub Search results (pages 1–100) for one query.",
                400,
            )
        key = ("issues", ref.owner.lower(), ref.repo.lower(), category, search.casefold(), page)
        matching_labels = self.category_labels(category, labels)
        if matching_labels is None:
            raise GitHubServiceError("invalid_category", "Choose a supported issue category.", 400)
        if category != "ALL" and not matching_labels:
            return self._write_cache(key, {
                "issues": [], "page": page, "per_page": PER_PAGE, "total_count": 0,
                "total_pages": 0, "has_next": False, "has_previous": page > 1,
                "category": category, "category_available": False, "matched_labels": [],
                "search_limit_reached": False,
            })

        if any(value != "ALL" for value in normalized_filters.values()):
            return await self._search_classified_issues(
                ref, matching_labels, page, category, search,
                normalized_filters["difficulty"], normalized_filters["skill"], normalized_filters["effort"],
            )

        cached = self._read_cache(key)
        if cached is not None:
            return cached

        query = f"repo:{ref.full_name} is:issue is:open"
        if matching_labels:
            query += " (" + " OR ".join(f'label:"{label.replace(chr(34), "")}"' for label in matching_labels) + ")"
        if search:
            safe_search = search.replace('"', " ").replace("\\", " ").replace("\n", " ").replace("\r", " ").strip()
            if safe_search:
                query += f' "{safe_search}" in:title,body'
        data, _ = await self._get("/search/issues", {"q": query, "per_page": PER_PAGE, "page": page, "sort": "created", "order": "desc"})
        if not isinstance(data, dict) or not isinstance(data.get("items"), list) or not isinstance(data.get("total_count"), int):
            raise GitHubServiceError("github_unexpected_response", "GitHub returned an unexpected issue search response.")
        issues = []
        for issue in data["items"]:
            # Be defensive even though is:issue excludes pull requests in search.
            if not isinstance(issue, dict) or "pull_request" in issue:
                continue
            if not isinstance(issue.get("number"), int) or not isinstance(issue.get("html_url"), str):
                raise GitHubServiceError("github_unexpected_response", "GitHub returned an incomplete issue result.")
            if not isinstance(issue.get("number"), int) or not isinstance(issue.get("html_url"), str):
                raise GitHubServiceError("github_unexpected_response", "GitHub returned an incomplete issue result.")
            issues.append(_normalize_issue(issue))
        total_count = data["total_count"]
        total_pages = min((total_count + PER_PAGE - 1) // PER_PAGE, SEARCH_RESULT_LIMIT // PER_PAGE)
        return self._write_cache(key, {
            "issues": issues, "page": page, "per_page": PER_PAGE,
            "total_count": total_count, "total_pages": total_pages,
            "has_next": page < total_pages, "has_previous": page > 1,
            "category": category, "category_available": True,
            "matched_labels": matching_labels,
            "search_limit_reached": total_count > SEARCH_RESULT_LIMIT,
        })

    async def _load_classified_candidates(self, query: str) -> tuple[list[dict[str, Any]], int]:
        params = {"q": query, "per_page": CLASSIFICATION_PAGE_SIZE, "page": 1, "sort": "created", "order": "desc"}
        data, _ = await self._get("/search/issues", params)
        if not isinstance(data, dict) or not isinstance(data.get("items"), list) or not isinstance(data.get("total_count"), int):
            raise GitHubServiceError("github_unexpected_response", "GitHub returned an unexpected issue search response.")
        total_count = data["total_count"]
        page_count = min((total_count + CLASSIFICATION_PAGE_SIZE - 1) // CLASSIFICATION_PAGE_SIZE, CLASSIFICATION_CANDIDATE_LIMIT // CLASSIFICATION_PAGE_SIZE)
        raw_issues = list(data["items"])
        for batch_start in range(2, page_count + 1, 3):
            pages = range(batch_start, min(batch_start + 3, page_count + 1))
            page_results = await asyncio.gather(*(
                self._get("/search/issues", {**params, "page": candidate_page})
                for candidate_page in pages
            ))
            for page_data, _ in page_results:
                if not isinstance(page_data, dict) or not isinstance(page_data.get("items"), list):
                    raise GitHubServiceError("github_unexpected_response", "GitHub returned an unexpected issue search response.")
                raw_issues.extend(page_data["items"])

        issues: list[dict[str, Any]] = []
        for issue in raw_issues[:CLASSIFICATION_CANDIDATE_LIMIT]:
            if not isinstance(issue, dict) or "pull_request" in issue:
                continue
            if not isinstance(issue.get("number"), int) or not isinstance(issue.get("html_url"), str):
                raise GitHubServiceError("github_unexpected_response", "GitHub returned an incomplete issue result.")
            issues.append(_normalize_issue(issue))
        return issues, total_count

    async def _search_classified_issues(
        self,
        ref: RepositoryRef,
        matching_labels: list[str],
        page: int,
        category: str,
        search: str,
        difficulty: str,
        skill: str,
        effort: str,
    ) -> dict[str, Any]:
        if page > CLASSIFICATION_CANDIDATE_LIMIT // PER_PAGE:
            raise GitHubServiceError("search_result_limit", "PANDA estimate filters paginate a bounded window of at most 1,000 GitHub search candidates (100 pages).", 400)

        query = f"repo:{ref.full_name} is:issue is:open"
        if matching_labels:
            query += " (" + " OR ".join(f'label:"{label.replace(chr(34), "")}"' for label in matching_labels) + ")"
        safe_search = search.replace('"', " ").replace("\\", " ").replace("\n", " ").replace("\r", " ").strip()
        if safe_search:
            query += f' "{safe_search}" in:title,body'

        cache_key = ("classified_candidates", ref.owner.lower(), ref.repo.lower(), category, search.casefold())
        candidates = self._read_cache(cache_key)
        if candidates is None:
            task = self._candidate_tasks.get(cache_key)
            if task is None:
                task = asyncio.create_task(self._load_classified_candidates(query))
                self._candidate_tasks[cache_key] = task
            try:
                candidates = await task
                self._write_cache(cache_key, candidates, ttl=300)
            finally:
                if task.done() and self._candidate_tasks.get(cache_key) is task:
                    self._candidate_tasks.pop(cache_key, None)
        issues, candidate_total = candidates

        result_key = ("classified_issue_page", ref.owner.lower(), ref.repo.lower(), category, search.casefold(), difficulty, skill, effort, page)
        cached_result = self._read_cache(result_key)
        if cached_result is not None:
            return cached_result
        filtered = [issue for issue in issues
                    if (difficulty == "ALL" or issue["panda"]["difficulty"] == difficulty)
                    and (skill == "ALL" or issue["panda"]["skill"] == skill)
                    and (effort == "ALL" or issue["panda"]["effort"] == effort)]
        total_matching = len(filtered)
        total_pages = (total_matching + PER_PAGE - 1) // PER_PAGE
        start = (page - 1) * PER_PAGE
        return self._write_cache(result_key, {
            "issues": filtered[start:start + PER_PAGE], "page": page, "per_page": PER_PAGE,
            "total_count": total_matching, "total_pages": total_pages,
            "has_next": page < total_pages, "has_previous": page > 1,
            "category": category, "category_available": True,
            "matched_labels": matching_labels,
            "search_limit_reached": candidate_total > CLASSIFICATION_CANDIDATE_LIMIT,
            "candidate_count": len(issues),
            "candidate_limit": CLASSIFICATION_CANDIDATE_LIMIT,
            "matching_count_exact": candidate_total <= CLASSIFICATION_CANDIDATE_LIMIT,
        })

    async def issue_detail(self, ref: RepositoryRef, issue_number: int) -> dict[str, Any]:
        key = ("issue_detail", ref.owner.lower(), ref.repo.lower(), issue_number)
        cached = self._read_cache(key)
        if cached is not None:
            return cached
        data, _ = await self._get(f"/repos/{ref.owner}/{ref.repo}/issues/{issue_number}")
        if not isinstance(data, dict) or "pull_request" in data:
            raise GitHubServiceError("issue_not_found", "That issue could not be found.", 404)
        if not isinstance(data.get("number"), int) or not isinstance(data.get("html_url"), str):
            raise GitHubServiceError("github_unexpected_response", "GitHub returned incomplete issue detail.")
        user = data.get("user") or {}
        return self._write_cache(key, {
            "number": data.get("number"), "title": data.get("title") or "(untitled issue)",
            "body": data.get("body") or "", "html_url": data.get("html_url"),
            "labels": [label["name"] for label in data.get("labels", []) if isinstance(label, dict) and isinstance(label.get("name"), str)],
            "created_at": data.get("created_at"), "updated_at": data.get("updated_at"),
            "comments_count": data.get("comments", 0),
            "author": user.get("login") if isinstance(user, dict) else None,
            "state": data.get("state"),
        })

    async def issue_comments(self, ref: RepositoryRef, issue_number: int) -> list[dict[str, str]]:
        key = ("issue_comments", ref.owner.lower(), ref.repo.lower(), issue_number)
        cached = self._read_cache(key)
        if cached is not None:
            return cached
        data, _ = await self._get(
            f"/repos/{ref.owner}/{ref.repo}/issues/{issue_number}/comments",
            {"per_page": 30, "page": 1, "sort": "updated", "direction": "desc"},
        )
        if not isinstance(data, list):
            raise GitHubServiceError("github_unexpected_response", "GitHub returned an unexpected comments response.")
        comments: list[dict[str, str]] = []
        for item in data[:20]:
            if not isinstance(item, dict):
                continue
            user = item.get("user") or {}
            comments.append({
                "author": user.get("login", "unknown") if isinstance(user, dict) else "unknown",
                "created_at": str(item.get("created_at") or ""),
                "body": str(item.get("body") or "")[:1800],
            })
        return self._write_cache(key, comments)

    async def repository_tree(self, ref: RepositoryRef) -> dict[str, Any]:
        repository = await self.repository(ref)
        branch = repository["default_branch"]
        key = ("repository_tree", ref.owner.lower(), ref.repo.lower(), branch)
        cached = self._read_cache(key)
        if cached is not None:
            return cached
        branch_ref, _ = await self._get(f"/repos/{ref.owner}/{ref.repo}/git/ref/heads/{quote(branch, safe='/')}")
        commit_sha = (((branch_ref.get("object") or {}).get("sha")) if isinstance(branch_ref, dict) else None)
        if not commit_sha:
            raise GitHubServiceError("github_unexpected_response", "GitHub returned an unexpected branch reference.")
        tree_data, _ = await self._get(f"/repos/{ref.owner}/{ref.repo}/git/trees/{commit_sha}", {"recursive": 1})
        if not isinstance(tree_data, dict) or not isinstance(tree_data.get("tree"), list):
            raise GitHubServiceError("github_unexpected_response", "GitHub returned an unexpected repository tree.")
        entries = [
            {"path": entry["path"], "type": entry.get("type"), "size": entry.get("size", 0)}
            for entry in tree_data["tree"]
            if isinstance(entry, dict) and isinstance(entry.get("path"), str)
        ]
        return self._write_cache(key, {
            "branch": branch,
            "commit_sha": commit_sha,
            "truncated": bool(tree_data.get("truncated", False)),
            "entries": entries,
        }, ttl=600)

    async def file_content(self, ref: RepositoryRef, branch: str, path: str) -> str | None:
        key = ("file_content", ref.owner.lower(), ref.repo.lower(), branch, path)
        cached = self._read_cache(key)
        if cached is not None:
            return cached
        encoded_path = quote(path, safe="/")
        data, _ = await self._get(
            f"/repos/{ref.owner}/{ref.repo}/contents/{encoded_path}",
            {"ref": branch},
        )
        if not isinstance(data, dict) or data.get("encoding") != "base64" or not isinstance(data.get("content"), str):
            return None
        try:
            decoded = base64.b64decode(data["content"], validate=False).decode("utf-8", errors="replace")
        except (ValueError, UnicodeError):
            return None
        return self._write_cache(key, decoded, ttl=600)


github_service = GitHubService()

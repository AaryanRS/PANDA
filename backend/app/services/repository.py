"""Build a small, issue-focused package of repository evidence."""

from __future__ import annotations

import asyncio
import re
import time
from collections import Counter
from typing import Any, Callable

from app.services.github import GitHubServiceError, RepositoryRef, github_service

SOURCE_EXTENSIONS = {".py", ".pyi", ".js", ".jsx", ".ts", ".tsx", ".java", ".go", ".rs", ".rb", ".c", ".h", ".cpp", ".hpp", ".cs", ".php", ".swift", ".kt"}
TEST_PARTS = {"test", "tests", "__tests__", "spec", "specs"}
SKIP_PARTS = {".git", "node_modules", "vendor", "third_party", "build", "dist", "site-packages", "__pycache__"}
STOP_WORDS = {
    "about", "after", "again", "also", "and", "because", "before", "being", "below", "between", "can", "could",
    "data", "does", "during", "each", "example", "examples", "for", "frame", "from", "have", "into", "issue", "just", "more", "most", "other",
    "over", "same", "some", "such", "than", "that", "their", "them", "then", "there", "these",
    "the", "they", "this", "those", "through", "under", "very", "want", "what", "when", "where", "which",
    "while", "with", "would", "your", "should", "using", "used", "version", "actual", "expected",
    "com", "https", "result",
}
TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]{2,}")
PATH_RE = re.compile(r"(?<![\w.-])(?:[\w.-]+/)+[\w.-]+\.(?:pyi?|js|jsx|ts|tsx|java|go|rs|rb|c|h|cpp|hpp|cs|php|swift|kt)(?![\w.-])", re.I)
MODULE_PATH_RE = re.compile(r"\b((?:[A-Za-z_]\w*\.){2,}[A-Za-z_]\w*)\.[A-Za-z_]\w*\b")
SYMBOL_RE = re.compile(r"\b(?:async\s+)?(?:def|class)\s+([A-Za-z_][A-Za-z0-9_]*)")
MAX_SOURCE_FILES = 3
MAX_SOURCE_CHARS = 2400
MAX_TEST_FILES = 2
MAX_TEST_CHARS = 1500
MAX_DOCUMENTATION_FILES = 1
MAX_DOCUMENTATION_CHARS = 1000
MAX_ISSUE_BODY_CHARS = 4000
MAX_COMMENT_COUNT = 2
MAX_COMMENT_CHARS = 500
FILE_TRUNCATION_MARKER = "\n[File excerpt bounded by PANDA.]"
PATH_GENERIC_TERMS = {
    "dataframe", "column", "columns", "terminal", "width", "result", "output",
    "test", "tests", "testing", "pandas", "python", "example", "examples", "issue",
}


def _words(value: str) -> list[str]:
    expanded = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", value)
    return [word.lower() for word in TOKEN_RE.findall(expanded) if word.lower() not in STOP_WORDS]


def _issue_signals(issue: dict[str, Any], comments: list[dict[str, str]]) -> tuple[Counter[str], set[str]]:
    weights: Counter[str] = Counter()
    title = str(issue.get("title") or "")
    body = str(issue.get("body") or "")[:MAX_ISSUE_BODY_CHARS]
    for token in _words(title):
        weights[token] += 5
    for label in issue.get("labels", []):
        for token in _words(str(label)):
            weights[token] += 2
    for token in _words(body):
        weights[token] += 1
    comment_text = " ".join(comment.get("body", "")[:1000] for comment in comments[:10])
    for token in _words(comment_text):
        weights[token] += 0.5
    issue_text = f"{title}\n{body}\n{comment_text}"
    explicit_paths = {path.replace("\\", "/").rstrip(".,;:)") for path in PATH_RE.findall(issue_text)}
    explicit_paths.update(module.replace(".", "/") + ".py" for module in MODULE_PATH_RE.findall(issue_text))
    # Keep ranking bounded and avoid letting common incidental terms dominate.
    weights = Counter(dict(weights.most_common(28)))
    return weights, explicit_paths


def _relevant_comments(issue: dict[str, Any], comments: list[dict[str, str]]) -> list[dict[str, str]]:
    issue_terms = Counter(_words(f"{issue.get('title', '')} {str(issue.get('body') or '')[:MAX_ISSUE_BODY_CHARS]}"))
    ranked: list[tuple[float, str, dict[str, str]]] = []
    for comment in comments:
        body = str(comment.get("body") or "")[:MAX_COMMENT_CHARS]
        terms = set(_words(body))
        score = sum(issue_terms[term] for term in terms)
        if score:
            ranked.append((score, str(comment.get("created_at") or ""), {**comment, "body": body}))
    ranked.sort(key=lambda item: (-item[0], item[1]))
    return [item[2] for item in ranked[:MAX_COMMENT_COUNT]]


def _path_tokens(path: str) -> set[str]:
    stem = re.sub(r"\.[^.]+$", "", path)
    return set(_words(stem.replace("/", " ").replace("_", " ").replace("-", " ")))


def _score_path(path: str, weights: Counter[str], explicit_paths: set[str]) -> float:
    normalized = path.replace("\\", "/").lower()
    explicit = {value.lower() for value in explicit_paths}
    if normalized in explicit:
        return 10000.0
    basename = path.rsplit("/", 1)[-1]
    stem = re.sub(r"\.[^.]+$", "", basename).lower()
    parts = [part.lower() for part in path.split("/")[:-1]]
    path_terms = _path_tokens(path)
    score = 0.0
    for token, weight in weights.items():
        if token in PATH_GENERIC_TERMS:
            continue
        if token in stem or token == stem:
            score += weight * 6
        elif token in path_terms:
            score += weight * (3 if token in parts else 4)
        elif len(token) > 5 and any(token in term or term in token for term in path_terms if len(term) > 4):
            score += weight * 0.7
    return score


def _is_test(path: str) -> bool:
    parts = [part.lower() for part in path.split("/")]
    stem = re.sub(r"\.[^.]+$", "", parts[-1])
    return any(part in TEST_PARTS for part in parts[:-1]) or stem.startswith(("test_", "test.", "spec_")) or stem.endswith(("_test", ".test", ".spec"))


def _is_documentation(path: str) -> bool:
    lower = path.lower()
    parts = lower.split("/")
    base = parts[-1]
    return base.startswith("readme") or any(part in {"doc", "docs", "documentation"} for part in parts[:-1]) or base.endswith((".md", ".rst", ".adoc"))


def _is_strong_documentation_match(path: str, weights: Counter[str], explicit_paths: set[str]) -> bool:
    if path.lower() in {item.lower() for item in explicit_paths}:
        return True
    path_terms = _path_tokens(path)
    return any(
        weight >= 4 and token not in PATH_GENERIC_TERMS and token in path_terms
        for token, weight in weights.items()
    )


def _is_skipped(path: str) -> bool:
    return any(part.lower() in SKIP_PARTS for part in path.split("/"))


def _source_test_related(test_path: str, source_paths: list[str]) -> float:
    test_parts = [part.lower() for part in test_path.split("/")]
    test_stem = re.sub(r"\.[^.]+$", "", test_parts[-1])
    test_stem = re.sub(r"^(test_|spec_)", "", test_stem).removesuffix("_test")
    score = 0.0
    for source_path in source_paths:
        source_parts = [part.lower() for part in source_path.split("/")]
        source_stem = re.sub(r"\.[^.]+$", "", source_parts[-1])
        shared_dirs = set(source_parts[:-1]) & set(test_parts[:-1])
        shared_dirs.discard("pandas")
        source_dirs = [part for part in source_parts[:-1] if part not in TEST_PARTS and part != "pandas"]
        test_dirs = [part for part in test_parts[:-1] if part not in TEST_PARTS and part != "pandas"]
        root_score = 1 if "pandas" in source_parts[:-1] and "pandas" in test_parts[:-1] else 0
        depth_penalty = abs(len(source_dirs) - len(test_dirs)) * 4
        directory_score = max(0, len(shared_dirs) * 4 + root_score - depth_penalty)
        if source_stem == test_stem:
            name_score = 16
        elif min(len(source_stem), len(test_stem)) >= 5 and (source_stem in test_stem or test_stem in source_stem):
            name_score = 12
        else:
            name_score = 0
        score = max(score, directory_score + name_score)
    return score


def _symbols_in(content: str, issue_signals: set[str]) -> list[str]:
    declared = set(SYMBOL_RE.findall(content))
    return sorted(symbol for symbol in declared if symbol.lower() in issue_signals)


def _focused_excerpt(content: str, weights: Counter[str], max_chars: int) -> tuple[str, bool]:
    if len(content) <= max_chars:
        return content, False
    lines = content.splitlines()
    signals = [(token.lower(), weight) for token, weight in weights.items() if len(token) >= 4]
    line_scores: list[float] = []
    for line in lines:
        lowered = line.lower()
        score = sum(weight for token, weight in signals if token in lowered)
        if re.match(r"\s*(?:async\s+)?(?:def|class)\s+", line):
            score += 0.5
        line_scores.append(score)

    window_size = 48
    stride = 12
    windows: list[tuple[float, int, int]] = []
    for start in range(0, len(lines), stride):
        end = min(len(lines), start + window_size)
        score = sum(line_scores[start:end])
        if score > 0:
            windows.append((score, start, end))
        if end == len(lines):
            break
    windows.sort(key=lambda item: (-item[0], item[1]))
    selected: list[tuple[int, int]] = []
    budget = max_chars
    for _, start, end in windows:
        if any(start < chosen_end and end > chosen_start for chosen_start, chosen_end in selected):
            continue
        snippet = "\n".join(lines[start:end])
        marker = f"\n[Relevant excerpt: original lines {start + 1}-{end}]\n"
        cost = len(snippet) + len(marker)
        if cost > budget:
            continue
        selected.append((start, end))
        budget -= cost
        if budget < 500:
            break

    if not selected:
        return content[:max_chars], True
    excerpts = [
        f"[Relevant excerpt: original lines {start + 1}-{end}]\n" + "\n".join(lines[start:end])
        for start, end in sorted(selected)
    ]
    excerpt = "\n\n[Unrelated file sections omitted by PANDA]\n\n".join(excerpts)
    return excerpt[:max_chars], True


class RepositoryContextBuilder:
    def __init__(self) -> None:
        self._context_cache: dict[tuple[Any, ...], tuple[float, dict[str, Any], dict[str, Any]]] = {}

    async def build(
        self,
        ref: RepositoryRef,
        repository: dict[str, Any],
        issue: dict[str, Any],
        comments: list[dict[str, str]],
        progress: Callable[[str], None] | None = None,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        updated = str(issue.get("updated_at") or "")
        cache_key = (ref.full_name.lower(), repository["default_branch"], issue["number"], updated)
        cached = self._context_cache.get(cache_key)
        if cached and cached[0] > time.monotonic():
            return cached[1], cached[2]

        tree = await github_service.repository_tree(ref)
        weights, explicit_paths = _issue_signals(issue, comments)
        signals = set(weights)
        entries = [entry for entry in tree["entries"] if entry.get("type") == "blob" and isinstance(entry.get("path"), str)]
        source_candidates: list[tuple[float, dict[str, Any]]] = []
        test_candidates: list[tuple[float, dict[str, Any]]] = []
        doc_candidates: list[tuple[float, dict[str, Any]]] = []
        for entry in entries:
            path = entry["path"]
            if _is_skipped(path) or int(entry.get("size") or 0) > 1_000_000:
                continue
            if _is_test(path) and "." + path.rsplit(".", 1)[-1].lower() in SOURCE_EXTENSIONS:
                test_candidates.append((_score_path(path, weights, explicit_paths), entry))
            elif _is_documentation(path) and (
                path.lower().endswith((".md", ".rst", ".adoc", ".txt"))
                or path.rsplit("/", 1)[-1].lower().startswith("readme")
            ):
                doc_candidates.append((_score_path(path, weights, explicit_paths), entry))
            elif "." in path.rsplit("/", 1)[-1] and "." + path.rsplit(".", 1)[-1].lower() in SOURCE_EXTENSIONS:
                source_candidates.append((_score_path(path, weights, explicit_paths), entry))

        source_candidates.sort(key=lambda item: (-item[0], item[1]["path"]))
        explicit_source_paths = {path.lower() for path in explicit_paths}
        explicitly_named_sources = [entry for _, entry in source_candidates if entry["path"].lower() in explicit_source_paths]
        if explicitly_named_sources:
            selected_sources = explicitly_named_sources[:MAX_SOURCE_FILES]
        else:
            selected_sources = [entry for score, entry in source_candidates if score > 0][:MAX_SOURCE_FILES]
        selected_source_paths = [entry["path"] for entry in selected_sources]
        test_candidates = [
            (score + _source_test_related(entry["path"], selected_source_paths), entry)
            for score, entry in test_candidates
        ]
        test_candidates.sort(key=lambda item: (-item[0], item[1]["path"]))
        selected_tests = [entry for score, entry in test_candidates if score >= 8][:MAX_TEST_FILES]
        doc_candidates.sort(key=lambda item: (-item[0], item[1]["path"]))
        selected_docs = [
            entry for score, entry in doc_candidates
            if score >= 12 and _is_strong_documentation_match(entry["path"], weights, explicit_paths)
        ][:MAX_DOCUMENTATION_FILES]
        if progress:
            progress("READING SOURCE AND TESTS")

        async def fetch_one(entry: dict[str, Any], max_chars: int, kind: str) -> dict[str, Any] | None:
            path = entry["path"]
            try:
                content = await github_service.file_content(ref, repository["default_branch"], path)
            except GitHubServiceError:
                return None
            if not content:
                return None
            truncated = len(content) > max_chars
            excerpt_budget = max_chars - len(FILE_TRUNCATION_MARKER) if truncated else max_chars
            bounded, excerpted = _focused_excerpt(content, weights, excerpt_budget)
            if truncated or excerpted:
                bounded = bounded[:excerpt_budget] + FILE_TRUNCATION_MARKER
            return {"path": path, "content": bounded, "truncated": truncated or excerpted, "kind": kind}

        fetch_jobs = [
            *((entry, MAX_SOURCE_CHARS, "source") for entry in selected_sources),
            *((entry, MAX_TEST_CHARS, "test") for entry in selected_tests),
            *((entry, MAX_DOCUMENTATION_CHARS, "documentation") for entry in selected_docs),
        ]
        fetched = await asyncio.gather(*(fetch_one(*job) for job in fetch_jobs))
        by_kind = {kind: [item for item in fetched if item and item["kind"] == kind] for kind in ("source", "test", "documentation")}
        source_files = by_kind["source"]
        tests = by_kind["test"]
        documentation = by_kind["documentation"]

        source_symbols = [
            {"path": item["path"], "symbols": _symbols_in(item["content"], signals)}
            for item in source_files
        ]
        test_symbols = [
            {"path": item["path"], "symbols": _symbols_in(item["content"], signals)}
            for item in tests
        ]
        issue_context = {
            "number": issue["number"],
            "title": str(issue.get("title") or "")[:500],
            "body": str(issue.get("body") or "")[:MAX_ISSUE_BODY_CHARS],
            "labels": issue.get("labels", []),
            "comments": _relevant_comments(issue, comments),
        }
        repo_context = {
            "full_name": repository["full_name"],
            "default_branch": repository["default_branch"],
            "language": repository.get("language"),
            "description": (repository.get("description") or "")[:1000],
        }
        context = {
            "issue": issue_context,
            "repository": repo_context,
            "source_files": source_files,
            "tests": tests,
            "documentation": documentation,
        }
        evidence = {
            "files": source_symbols,
            "tests": test_symbols,
            "documentation": [item["path"] for item in documentation],
            "tree_truncated": tree["truncated"],
            "test_guidance": "No relevant existing test was confidently identified." if not tests else None,
        }
        self._context_cache[cache_key] = (time.monotonic() + 300, context, evidence)
        return context, evidence


repository_context_builder = RepositoryContextBuilder()

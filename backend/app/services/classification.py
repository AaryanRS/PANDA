"""Fast, deterministic PANDA estimates for issues on the currently loaded page."""

from __future__ import annotations

import re
from typing import Any


_SKILL_TERMS: dict[str, tuple[str, ...]] = {
    "Python": (r"\bpython\b", r"\.py\b", r"pytest", r"pip install", r"traceback", r"pandas\.", r"\bconda\b"),
    "Testing": (r"\btests?\b", r"\btesting\b", r"\bpytest\b", r"\bregression test\b", r"\bunit test\b", r"test suite"),
    "Documentation": (r"\bdocs?\b", r"documentation", r"readme", r"docstring", r"tutorial", r"typo", r"spelling"),
    "Performance": (r"performance", r"\bslow(?:er|est)?\b", r"benchmark", r"memory usage", r"\boptimization\b", r"\boptimisation\b", r"\bspeed\b"),
    "DevOps / CI": (r"\bci\b", r"github actions", r"build pipeline", r"workflow", r"packaging", r"deployment", r"\bdocker\b"),
    "Frontend": (r"\bui\b", r"frontend", r"react", r"\bcss\b", r"browser", r"component", r"javascript", r"typescript"),
    "Data / ML": (r"machine learning", r"\bml\b", r"\bmodel\b", r"dataset", r"training", r"prediction", r"estimator", r"\balgorithm\b", r"stable diffusion", r"\btransformer\b", r"\bneur(?:al|on)\b"),
    "Architecture": (r"architecture", r"redesign", r"refactor", r"migration", r"cross[- ](?:module|package|subsystem)", r"public api"),
    "Backend": (r"\bapi\b", r"server[- ]side", r"database", r"endpoint", r"request handling", r"\bbackend\b"),
}

_BEGINNER = (r"good first issue", r"first[- ]time contributor", r"help wanted", r"documentation[- ]only", r"\btypo\b", r"spelling", r"simple test", r"small isolated", r"straightforward")
_ADVANCED = (r"architecture", r"redesign", r"concurren(?:cy|t)", r"race condition", r"cross[- ](?:module|package|subsystem)", r"multiple (?:modules|packages|subsystems|components)", r"api redesign", r"large[- ]scale", r"major feature", r"migration", r"complex regression", r"performance (?:regression|optimization|optimisation|work)", r"deadlock", r"distributed")
_LARGE = (r"architecture", r"redesign", r"concurren(?:cy|t)", r"cross[- ](?:module|package|subsystem)", r"migration", r"major feature", r"large[- ]scale", r"entire codebase", r"memory leak", r"performance regression")
_SMALL = (r"documentation", r"\bdocs?\b", r"\btypo\b", r"spelling", r"simple test", r"one[- ]line", r"single[- ]file", r"small isolated")


def _matches(text: str, patterns: tuple[str, ...]) -> int:
    return sum(bool(re.search(pattern, text, re.IGNORECASE)) for pattern in patterns)


def classify_issue(issue: dict[str, Any]) -> dict[str, str]:
    """Return always-valid estimates using issue wording and labels as separate signals."""
    title = str(issue.get("title") or "")[:1000]
    body = str(issue.get("body") or issue.get("body_excerpt") or "")[:6000]
    raw_labels = issue.get("labels") or []
    labels = " ".join(str(label) for label in raw_labels[:30]) if isinstance(raw_labels, list) else ""
    text = f"{title}\n{body}".casefold()
    label_text = labels.casefold()

    beginner = _matches(text, _BEGINNER) * 2
    advanced = _matches(text, _ADVANCED) * 2
    # Labels help establish contributor intent, but are never sufficient by themselves.
    beginner += int(any(term in label_text for term in ("good first issue", "help wanted")))
    advanced += int(any(term in label_text for term in ("architecture", "breaking change")))
    if beginner >= 2 and beginner > advanced:
        difficulty = "Beginner"
    elif advanced >= 2 and advanced >= beginner:
        difficulty = "Advanced"
    else:
        difficulty = "Intermediate"

    scores = {skill: _matches(text, patterns) for skill, patterns in _SKILL_TERMS.items()}
    # Labels contribute at most a small corroborating signal; e.g. "bug" does not imply Backend.
    for skill, patterns in _SKILL_TERMS.items():
        scores[skill] += sum(1 for pattern in patterns if re.search(pattern, label_text, re.IGNORECASE)) // 2
    skill = max(scores, key=scores.get) if scores and max(scores.values()) > 0 else "Other"

    large = _matches(text, _LARGE) * 2
    small = _matches(text, _SMALL) * 2
    # Broad scope and multi-subsystem wording are useful effort signals.
    large += int(bool(re.search(r"\b(?:multiple|several|all) (?:modules|packages|subsystems|components)\b", text)))
    if large >= 2 and large >= small:
        effort = "Large"
    elif small >= 2 and small > large:
        effort = "Small"
    else:
        effort = "Medium"

    return {"difficulty": difficulty, "skill": skill, "effort": effort}

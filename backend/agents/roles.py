"""Specialist agent roles.

One shared runtime, role-specific instructions — not ten separate systems.
"""
from __future__ import annotations

ROLES: dict[str, dict] = {
    "architect": {
        "label": "Architect",
        "instructions": "Design the system structure, boundaries and data model. "
                        "Prefer modular, replaceable components.",
    },
    "planner": {
        "label": "Planner",
        "instructions": "Decompose the request into an ordered, dependency-aware plan "
                        "with verifiable tasks.",
    },
    "coding": {
        "label": "Coding Agent",
        "instructions": "Implement the smallest correct change. Produce complete file "
                        "contents. Never claim a change without a file operation.",
    },
    "debug": {
        "label": "Debug Agent",
        "instructions": "Work only from real error output. Identify the root cause, then "
                        "produce a minimal fix.",
    },
    "reviewer": {
        "label": "Reviewer",
        "instructions": "Review changes for correctness, clarity and regressions. "
                        "Report concrete issues, not opinions.",
    },
    "qa": {
        "label": "QA Agent",
        "instructions": "Design and run real tests. Treat every claim as unverified until "
                        "an execution result confirms it.",
    },
    "research": {
        "label": "Research Agent",
        "instructions": "Gather the technical facts needed to proceed. Cite concrete APIs "
                        "and versions.",
    },
    "performance": {
        "label": "Performance Agent",
        "instructions": "Identify measurable performance risks and propose specific, "
                        "verifiable improvements.",
    },
    "security": {
        "label": "Security Agent",
        "instructions": "Audit for injection, secret exposure and unsafe execution. "
                        "Report concrete findings.",
    },
    "deployment": {
        "label": "Deployment Agent",
        "instructions": "Describe how to build, run and ship the project, including "
                        "required environment and runner capabilities.",
    },
}


def role_catalog() -> list[dict]:
    return [{"id": key, **value} for key, value in ROLES.items()]


def role_instructions(role_id: str) -> str:
    role = ROLES.get(role_id)
    return role["instructions"] if role else ""

"""JSON Schema loading and validation with readable, path-annotated errors."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from importlib import resources
from typing import Any

import yaml
from jsonschema import Draft202012Validator

_SCHEMA_FILE = "platform.v1.schema.json"


@dataclass(frozen=True)
class Issue:
    path: str
    message: str

    def __str__(self) -> str:
        return f"{self.path or '<root>'}: {self.message}"


def load_schema() -> dict[str, Any]:
    text = resources.files("pipeline_platform").joinpath("schemas", _SCHEMA_FILE).read_text("utf-8")
    return json.loads(text)


def _format_path(parts: Any) -> str:
    out = ""
    for p in parts:
        out += f"[{p}]" if isinstance(p, int) else (f".{p}" if out else str(p))
    return out


def validate_schema(doc: Any) -> list[Issue]:
    """Structural validation against the v1 JSON Schema."""
    validator = Draft202012Validator(load_schema())
    issues = [Issue(_format_path(e.absolute_path), e.message) for e in validator.iter_errors(doc)]
    return sorted(issues, key=lambda i: (i.path, i.message))


def validate_semantics(doc: dict[str, Any]) -> list[Issue]:
    """Rules JSON Schema cannot express: unique names, compilable regexes."""
    issues: list[Issue] = []
    envs = (doc.get("deploy") or {}).get("environments") or []
    seen: dict[str, int] = {}
    for i, env in enumerate(envs):
        name = env.get("name")
        if name in seen:
            issues.append(Issue(f"deploy.environments[{i}].name", f"duplicate environment '{name}'"))
        seen[name] = i
        pattern = (env.get("refs") or {}).get("tags")
        if pattern is not None:
            try:
                re.compile(pattern)
            except re.error as exc:
                issues.append(Issue(f"deploy.environments[{i}].refs.tags", f"invalid regex: {exc}"))
    return issues


def validate(doc: Any) -> list[Issue]:
    """Schema first; semantic checks only run on a structurally valid document."""
    issues = validate_schema(doc)
    if issues:
        return issues
    return validate_semantics(doc)


def load_config(path: str) -> Any:
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)

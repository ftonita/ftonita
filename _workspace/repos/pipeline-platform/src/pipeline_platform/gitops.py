"""Bump `image.tag` in a Helm values file without disturbing comments or formatting."""

from __future__ import annotations

import re


class TagNotFoundError(ValueError):
    """The values file has no `image:` block with a `tag:` key."""


_TAG_RE = re.compile(r"^(?P<indent>\s+)tag:(?P<sp>\s*)(?P<val>\"[^\"]*\"|'[^']*'|[^\s#]*)(?P<rest>.*)$")


def bump_image_tag(text: str, tag: str) -> str:
    """Set the `tag` under the top-level `image:` key. Exactly one line changes."""
    if not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9._-]{0,127}", tag):
        raise ValueError(f"invalid image tag: {tag!r}")
    lines = text.split("\n")
    in_image = False
    for i, line in enumerate(lines):
        if re.match(r"^image:\s*(#.*)?$", line):
            in_image = True
            continue
        if in_image:
            if line.strip() and not line.startswith((" ", "\t")):
                break  # next top-level key
            m = _TAG_RE.match(line)
            if m:
                lines[i] = f'{m["indent"]}tag:{m["sp"] or " "}"{tag}"{m["rest"]}'
                return "\n".join(lines)
    raise TagNotFoundError("no `image:` block with a `tag:` key found")

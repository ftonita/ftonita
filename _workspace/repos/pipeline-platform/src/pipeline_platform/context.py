"""What triggered the pipeline. Evaluated at generation time, not inside the child pipeline.

Child pipelines run with CI_PIPELINE_SOURCE=parent_pipeline, so `rules:` on merge request
events cannot work there. The generator therefore reads the parent's environment and emits
only the jobs that apply.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True)
class Context:
    kind: str  # "merge_request" | "branch" | "tag" | "other"
    branch: str = ""
    tag: str = ""
    default_branch: str = "main"

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> Context:
        default = env.get("CI_DEFAULT_BRANCH", "main")
        tag = env.get("CI_COMMIT_TAG", "")
        branch = env.get("CI_COMMIT_BRANCH", "")
        if env.get("CI_MERGE_REQUEST_IID") or env.get("CI_PIPELINE_SOURCE") == "merge_request_event":
            return cls("merge_request", env.get("CI_MERGE_REQUEST_SOURCE_BRANCH_NAME", branch), "", default)
        if tag:
            return cls("tag", "", tag, default)
        if branch:
            return cls("branch", branch, "", default)
        return cls("other", "", "", default)

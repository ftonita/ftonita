from pipeline_platform.context import Context


def test_branch():
    c = Context.from_env({"CI_COMMIT_BRANCH": "main", "CI_DEFAULT_BRANCH": "main"})
    assert (c.kind, c.branch) == ("branch", "main")


def test_tag_wins_over_empty_branch():
    c = Context.from_env({"CI_COMMIT_TAG": "v1.2.3"})
    assert (c.kind, c.tag) == ("tag", "v1.2.3")


def test_merge_request_detected_by_iid():
    c = Context.from_env({"CI_MERGE_REQUEST_IID": "7", "CI_MERGE_REQUEST_SOURCE_BRANCH_NAME": "feat"})
    assert (c.kind, c.branch) == ("merge_request", "feat")


def test_merge_request_detected_by_source():
    assert Context.from_env({"CI_PIPELINE_SOURCE": "merge_request_event"}).kind == "merge_request"


def test_other_when_nothing_known():
    assert Context.from_env({}).kind == "other"


def test_default_branch_fallback():
    assert Context.from_env({}).default_branch == "main"

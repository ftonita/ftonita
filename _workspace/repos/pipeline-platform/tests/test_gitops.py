import pytest

from pipeline_platform.gitops import TagNotFoundError, bump_image_tag

VALUES = """\
# comment
replicaCount: 2

image:
  repository: nexus.example.com:8082/shop/orders-api
  tag: "0000000"  # bumped by CI
  pullPolicy: IfNotPresent

sidecar:
  image:
    tag: untouched
"""


def test_bumps_only_the_tag_line():
    out = bump_image_tag(VALUES, "a1b2c3d4")
    assert 'tag: "a1b2c3d4"  # bumped by CI' in out
    changed = [(a, b) for a, b in zip(VALUES.split("\n"), out.split("\n"), strict=True) if a != b]
    assert len(changed) == 1


def test_nested_image_blocks_are_not_touched():
    assert "tag: untouched" in bump_image_tag(VALUES, "abc12345")


def test_is_idempotent():
    once = bump_image_tag(VALUES, "abc12345")
    assert bump_image_tag(once, "abc12345") == once


@pytest.mark.parametrize("raw", ["tag: latest", "tag: 'x'", "tag:"])
def test_handles_unquoted_single_quoted_and_empty(raw):
    out = bump_image_tag(f"image:\n  repository: r\n  {raw}\n", "deadbeef")
    assert '  tag: "deadbeef"' in out


def test_missing_image_block():
    with pytest.raises(TagNotFoundError):
        bump_image_tag("replicaCount: 1\n", "abc")


def test_image_block_without_tag_does_not_leak_into_next_block():
    with pytest.raises(TagNotFoundError):
        bump_image_tag("image:\n  repository: r\nother:\n  tag: x\n", "abc")


@pytest.mark.parametrize("bad", ["", "a b", "x;rm -rf /", '"q"', "a" * 129, "-lead"])
def test_rejects_unsafe_tags(bad):
    with pytest.raises(ValueError, match="invalid image tag"):
        bump_image_tag(VALUES, bad)

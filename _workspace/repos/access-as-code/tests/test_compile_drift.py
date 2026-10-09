from __future__ import annotations

import json

import yaml

from access_as_code.compile import compile_access, effective, policy_hcl, rolebinding, write
from access_as_code.demo import make_drifted_state
from access_as_code.drift import diff
from conftest import TODAY, g


def test_policy_hcl_splits_data_and_metadata_paths():
    hcl = policy_hcl("payments", "dev", ("read", "list", "create"))
    assert 'path "kv-payments/data/dev/*" {\n  capabilities = ["create", "read"]\n}' in hcl
    assert 'path "kv-payments/metadata/dev/*" {\n  capabilities = ["list", "read"]\n}' in hcl


def test_policy_for_list_only_has_no_data_path():
    assert "/data/" not in policy_hcl("t", "e", ("list",))


def test_vault_groups_and_policies_follow_grants(make):
    art = compile_access(
        make(
            g(subject="group:devs", role="developer"),
            g(subject="bob", role="deployer", env="prod", ticket="SEC-1", expires="2026-11-01"),
        ),
        TODAY,
    )
    assert sorted(art.vault_policies) == ["payments-dev-developer", "payments-prod-deployer"]
    assert art.vault_groups == {"payments-dev-developer": ["alice", "bob"], "payments-prod-deployer": ["bob"]}


def test_expired_offboarded_and_invalid_grants_never_reach_output(make):
    art = compile_access(
        make(
            g(subject="gone"),
            g(subject="bob", expires="2026-10-07"),
            g(role="ghost"),
            g(subject="group:devs", team="nope"),
        ),
        TODAY,
    )
    assert art.as_state() == {"vault_policies": {}, "vault_groups": {}, "kubernetes": {}, "gitlab": {}}


def test_grant_expiring_today_is_still_effective(make):
    assert effective(make(g(expires="2026-10-08")), TODAY)


def test_gitlab_level_is_the_highest_across_grants(make):
    art = compile_access(
        make(g(role="viewer"), g(role="deployer", env="prod", ticket="SEC-1", expires="2026-11-01")), TODAY
    )
    assert art.gitlab == {"payments": {"alice": "maintainer"}}


def test_kubernetes_bindings_group_by_namespace_and_level(make):
    art = compile_access(
        make(g(subject="group:devs", role="developer"), g(subject="bob", role="viewer")), TODAY
    )
    assert art.kubernetes == {"payments-dev/edit": ["alice", "bob"], "payments-dev/view": ["bob"]}
    rb = rolebinding("payments-dev/edit", ["alice", "bob"])
    assert rb["metadata"] == {
        "name": "aac-edit",
        "namespace": "payments-dev",
        "labels": {"managed-by": "access-as-code"},
    }
    assert rb["roleRef"]["name"] == "edit" and [s["name"] for s in rb["subjects"]] == ["alice", "bob"]


def test_role_without_facets_produces_nothing_for_that_system(make):
    art = compile_access(make(g(role="approver")), TODAY)
    assert (
        art.vault_policies == {}
        and art.kubernetes == {}
        and art.gitlab == {"payments": {"alice": "maintainer"}}
    )


def test_compile_is_deterministic(good):
    assert compile_access(good, TODAY) == compile_access(good, TODAY)


def test_write_creates_expected_files(good, tmp_path):
    paths = write(compile_access(good, TODAY), tmp_path)
    names = {str(p.relative_to(tmp_path)) for p in paths}
    assert "vault/policies/payments-dev-developer.hcl" in names and "gitlab/members.json" in names
    assert "kubernetes/payments-dev--edit.yaml" in names
    assert (
        yaml.safe_load((tmp_path / "kubernetes/payments-dev--edit.yaml").read_text())["kind"] == "RoleBinding"
    )
    groups = json.loads((tmp_path / "vault/groups.json").read_text())
    assert groups["payments-dev-developer"] == {
        "policies": ["payments-dev-developer"],
        "members": ["alice", "bob"],
    }


def test_no_drift_when_state_matches(good):
    state = compile_access(good, TODAY).as_state()
    assert diff(state, json.loads(json.dumps(state))) == []


def test_policy_whitespace_is_not_drift(good):
    state = compile_access(good, TODAY).as_state()
    other = json.loads(json.dumps(state))
    k = next(iter(other["vault_policies"]))
    other["vault_policies"][k] += "\n\n"
    assert diff(state, other) == []


def test_drift_detection_kinds(good):
    state = compile_access(good, TODAY).as_state()
    drifted = make_drifted_state(state)
    found = {(d.kind, d.area) for d in diff(state, drifted)}
    assert found == {
        ("changed", "vault_groups"),
        ("changed", "vault_policies"),
        ("extra", "vault_policies"),
        ("missing", "kubernetes"),
        ("changed", "gitlab"),
    }


def test_drift_details_name_the_person(good):
    state = compile_access(good, TODAY).as_state()
    details = " ".join(d.detail for d in diff(state, make_drifted_state(state)))
    assert "zed" in details and "maintainer" in details

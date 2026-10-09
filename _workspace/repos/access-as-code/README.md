# access-as-code

[![ci](https://github.com/ftonita/access-as-code/actions/workflows/ci.yml/badge.svg)](https://github.com/ftonita/access-as-code/actions)
![Vault](https://img.shields.io/badge/Vault-policies-FFEC6E?logo=vault&logoColor=black)
![Kubernetes](https://img.shields.io/badge/Kubernetes-RBAC-326CE5?logo=kubernetes&logoColor=white)
![GitLab](https://img.shields.io/badge/GitLab-members-FC6D26?logo=gitlab&logoColor=white)

**Declare who may do what in one reviewed YAML file. Lint it against least-privilege rules, compile it to Vault policies, Kubernetes RBAC and GitLab membership, and detect drift from what is actually configured.**

Access that lives in click-ops UIs cannot be reviewed, diffed or audited. Here every change is a merge request: reviewers see exactly which person gets which role on which team and environment, CI rejects risky grants, and the same file generates the configuration for all three systems.

> **All people, teams, tickets and tenants are synthetic.** This is a reference design for a least-privilege access model, not data or code from any employer.

## The model

```yaml
roles:
  developer: { vault: [read, list], kubernetes: edit, gitlab: developer }
  deployer:  { vault: [read, list, create, update], kubernetes: edit, gitlab: maintainer }
  approver:  { gitlab: maintainer }
people:
  alice: { team: payments, status: active }
groups:
  payments-devs: [alice, bob]
grants:
  - { subject: "group:payments-devs", role: developer, team: payments, env: dev }
  - { subject: alice, role: deployer, team: payments, env: prod, ticket: SEC-110, expires: 2026-12-15 }
```

One grant = *subject* + *role* + *team* + *environment* (+ ticket, expiry, reason). A role is a bundle of facets for each system, so "developer" means the same thing in Vault, Kubernetes and GitLab.

## Lint rules (`access-as-code rules`)

| ID | Severity | Rule |
|---|---|---|
| AAC001 | error | No role may hold the Vault `sudo` capability. |
| AAC002 | error | Grants reference known teams, environments, roles and subjects. |
| AAC003 | error | Production grants need a ticket; direct person grants also need an expiry (max 90 days). |
| AAC004 | error | Elevated roles (`delete` / Kubernetes `admin`) in production need a ticket and expire within 7 days. |
| AAC005 | error | Offboarded people hold no access, directly or via a group. |
| AAC006 | error | Expired grants must be removed. |
| AAC007 | error | Separation of duties: nobody is both `deployer` and `approver` on one team in production, even through groups. |
| AAC008 | warning | Cross-team access needs a ticket. |
| AAC009 | warning | Duplicate grants. |
| AAC010 | info | Unused roles and groups. |
| AAC011 | warning | Grants expiring within 14 days are due for review. |

`lint` exits 1 on errors (`--strict`: also on warnings), so it works as a required merge-request check. `--today` pins the date for reproducible runs.

## Walkthrough on the bundled synthetic data

```text
$ access-as-code lint examples/access.bad.yml --today 2026-10-08
AAC001 error: role 'super-ops' grants the Vault 'sudo' capability
AAC003 error: grant #3 (bob -> deployer on payments/prod): direct production grant without an expiry
AAC005 error: grant #0 (group:payments-devs -> developer on payments/dev): 'gone' is offboarded
AAC007 error: 'alice' is both deployer and approver on payments/prod
...
11 error(s), 5 warning(s), 3 info                                   (exit 1)

$ access-as-code lint examples/access.yml --today 2026-10-08
AAC011 warning: grant #10 (bob -> break-glass on payments/prod): expires on 2026-10-12
0 error(s), 1 warning(s), 1 info                                    (exit 0)

$ access-as-code compile examples/access.yml --today 2026-10-08 --out build
wrote 20 files to build
```

Generated, for example `build/vault/policies/payments-prod-deployer.hcl`:

```hcl
path "kv-payments/data/prod/*" {
  capabilities = ["create", "read", "update"]
}

path "kv-payments/metadata/prod/*" {
  capabilities = ["list", "read"]
}
```

plus `vault/groups.json` (identity group -> policy + members), one Kubernetes `RoleBinding` per namespace and level (`payments-dev` / `edit`) and `gitlab/members.json` (highest level per person per team).

**Compile emits effective access only**: expired grants, offboarded people and invalid grants never reach the output, even if lint was skipped.

### Drift

```text
$ access-as-code diff examples/access.yml --today 2026-10-08 --actual actual.json
extra    vault_policies:legacy-admin  configured but not declared
changed  vault_policies:payments-dev-developer  content differs
changed  vault_groups:payments-dev-developer  missing members ['alice']
changed  vault_groups:payments-prod-break-glass  extra members ['zed']
missing  kubernetes:payments-dev/edit  declared but not configured
changed  gitlab:scoring  erin: declared 'developer', actual 'maintainer'
6 difference(s)                                                      (exit 1)
```

`actual.json` here comes from `access-as-code demo-state`, which fabricates plausible hand-made changes. In real use you export the same four sections from your systems (Vault policies and identity groups, RoleBindings, GitLab members) on a schedule and fail the job on any difference.

## Suggested workflow

1. `access.yml` lives in a repo with CODEOWNERS (security + team leads).
2. Merge request: CI runs `lint` (blocking) and shows `review`.
3. After merge: `compile`, apply with your tooling (Terraform Vault provider, `kubectl apply`, GitLab API).
4. Nightly: `diff` against an exported snapshot; page on drift.

## What is verified

Reproduce with `pip install -e ".[dev]" && pytest` (45 tests, 99% line coverage): every lint rule (positive, negative and boundary cases such as an expiry exactly 90 days away or a grant expiring today), schema rejection, group resolution, deterministic compilation, exclusion of expired/offboarded access, drift of every kind, CLI exit codes.

**Not verified:** applying the output to real Vault, Kubernetes or GitLab instances; the HCL, RoleBinding and member-level formats follow the public documentation but were never loaded into those systems. Exporting the "actual" snapshot from live systems is not implemented (only the comparison is). Vault policy paths assume KV v2 mounts named `kv-<team>`. Roles are per-team and per-environment; finer scoping (single paths, time-of-day) is out of scope.

# vault-rbac-onboarding

[![ci](https://github.com/ftonita/vault-rbac-onboarding/actions/workflows/ci.yml/badge.svg)](https://github.com/ftonita/vault-rbac-onboarding/actions)
![Vault](https://img.shields.io/badge/HashiCorp_Vault-1.17-FFEC6E?logo=vault&logoColor=black)
![Terraform](https://img.shields.io/badge/Terraform-IaC-7B42BC?logo=terraform&logoColor=white)

Team onboarding for HashiCorp Vault as **policy-as-code**: add a team to a map, run `terraform apply`, and the team gets an isolated KV v2 engine, least-privilege policies per environment and AppRole identities for its pipelines.

> A sanitised reference of the approach used to migrate 10+ teams from legacy secret storage to Vault (1000+ credentials, least-privilege model for 50+ developers). No employer code or data.

## What one `teams` entry creates

```hcl
teams = {
  payments = { environments = ["stage", "prod"] }
}
```

| Resource | Purpose |
|---|---|
| `kv-payments` (KV v2 mount) | Per-team engine, so a leaked token exposes one team only. |
| `payments-prod-ci` policy + AppRole | Read/write **only** `kv-payments/prod/*`, token TTL 15 min. |
| `payments-prod-readonly` policy | Attach to developer groups (OIDC/LDAP) for read-only access. |
| File audit device | Every access is logged. |

## Prove it works (local, ~1 minute)

Expected result of `make test`:

```bash
make up        # Vault in dev mode (docker compose)
make apply     # terraform apply of policies/roles
make test      # asserts isolation end to end
```

```
own team/env      : 200   (expect 200)
other team        : 403   (expect 403)
other environment : 403   (expect 403)
PASS
```

`scripts/smoke-test.sh` logs in with AppRole as `payments-prod-ci` and verifies it cannot read another team's or another environment's secrets. The same check runs in GitHub Actions on every push.

## Production notes

- Dev mode is for the sandbox only: run Vault with Raft storage, auto-unseal and TLS.
- Deliver `role_id`/`secret_id` to pipelines through a trusted channel (response wrapping / CI-native secret injection).
- Migration playbook: inventory legacy secrets -> create team entry -> import values -> switch the pipeline to AppRole -> revoke the legacy store.

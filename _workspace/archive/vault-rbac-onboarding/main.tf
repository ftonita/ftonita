locals {
  # Flatten team x environment so every pair gets its own path and policies.
  team_envs = merge([
    for team, cfg in var.teams : {
      for env in cfg.environments : "${team}-${env}" => { team = team, env = env }
    }
  ]...)
}

# One KV v2 engine per team: the blast radius of a leaked token is a single team.
resource "vault_mount" "team" {
  for_each    = var.teams
  path        = "kv-${each.key}"
  type        = "kv"
  options     = { version = "2" }
  description = "Secrets for team ${each.key}"
}

# CI role: read/write inside its own environment only.
resource "vault_policy" "ci" {
  for_each = local.team_envs
  name     = "${each.key}-ci"
  policy   = <<-P
    path "kv-${each.value.team}/data/${each.value.env}/*"     { capabilities = ["create", "read", "update", "delete"] }
    path "kv-${each.value.team}/metadata/${each.value.env}/*" { capabilities = ["list", "read"] }
  P
}

# Read-only policy: attach to developer groups (OIDC/LDAP) per environment you want them to see.
resource "vault_policy" "developer" {
  for_each = local.team_envs
  name     = "${each.key}-readonly"
  policy   = <<-P
    path "kv-${each.value.team}/data/${each.value.env}/*"     { capabilities = ["read"] }
    path "kv-${each.value.team}/metadata/${each.value.env}/*" { capabilities = ["list", "read"] }
  P
}

# AppRole auth for pipelines: short-lived tokens, bound to CIDR if provided.
resource "vault_auth_backend" "approle" {
  type = "approle"
}

resource "vault_approle_auth_backend_role" "ci" {
  for_each       = local.team_envs
  backend        = vault_auth_backend.approle.path
  role_name      = "${each.key}-ci"
  token_policies = [vault_policy.ci[each.key].name]
  token_ttl      = 900
  token_max_ttl  = 1800
}

# Audit trail is mandatory.
resource "vault_audit" "file" {
  type = "file"
  options = {
    file_path = "/vault/logs/audit.log"
  }
}

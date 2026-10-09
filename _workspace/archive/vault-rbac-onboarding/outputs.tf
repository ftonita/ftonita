output "ci_role_names" {
  description = "AppRole names to hand to each team's pipeline."
  value       = { for k, r in vault_approle_auth_backend_role.ci : k => r.role_name }
}

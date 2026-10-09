variable "teams" {
  description = <<-D
    Teams to onboard. Each team gets its own KV v2 mount, a read-write policy for CI
    (AppRole) and a read-only policy to attach to developer groups/OIDC roles. Nothing is shared between teams.
  D
  type = map(object({
    environments = list(string)
  }))
}

#!/usr/bin/env bash
# Publishes the five reference repos as separate public GitHub repositories.
# Needs `gh auth login` (run locally). Safe to re-run: existing repos are skipped.
set -euo pipefail
cd "$(dirname "$0")/repos"
declare -A DESC=(
  [pipeline-platform]="One .platform.yml -> generated GitLab child pipeline: Vault id_tokens, Nexus/Artifactory, Ansible/Helm/ArgoCD"
  [vault-migration-toolkit]="Inventory, plan, migrate and verify secrets into Vault KV v2 without ever printing a value"
  [access-as-code]="Least-privilege access as reviewed YAML: lint, compile to Vault/Kubernetes/GitLab, detect drift"
  [release-bottleneck-analyzer]="Find where change lead time is spent (review, merge, release queue) and estimate what fixing it saves"
  [opsbot]="ChatOps Telegram bot with roles, rate limiting, audit log and a two-person rule for production changes"
)
declare -A TOPICS=(
  [pipeline-platform]="gitlab-ci,devops,hashicorp-vault,helm,argocd,ansible,nexus,json-schema,ci-cd"
  [vault-migration-toolkit]="hashicorp-vault,secrets-management,migration,devops,python"
  [access-as-code]="rbac,least-privilege,hashicorp-vault,kubernetes,gitlab,policy-as-code,devops"
  [release-bottleneck-analyzer]="dora-metrics,lead-time,devops,engineering-metrics,python"
  [opsbot]="chatops,telegram-bot,aiogram,alertmanager,devops,python"
)
for r in "${!DESC[@]}"; do
  if gh repo view "ftonita/$r" >/dev/null 2>&1; then echo "skip $r (exists)"; continue; fi
  ( cd "$r"
    git init -q -b main
    git add -A && git commit -qm "Initial commit"
    gh repo create "ftonita/$r" --public --description "${DESC[$r]}" --source . --push
    gh repo edit "ftonita/$r" --add-topic "${TOPICS[$r]}"
    rm -rf .git )
done
echo "Done. Pin the five repos: github.com/ftonita -> Customize your pins."

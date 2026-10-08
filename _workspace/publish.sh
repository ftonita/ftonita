#!/usr/bin/env bash
# Run LOCALLY (needs `gh auth login`). Publishes each reference repo as its own public GitHub repository.
set -euo pipefail
cd "$(dirname "$0")/repos"
declare -A DESC=(
  [terraform-hybrid-iac]="Multi-environment Terraform for OpenStack-compatible clouds with a merge-request GitLab pipeline"
  [gitlab-ci-templates]="Reusable GitLab CI templates: Kaniko build, SonarQube, Trivy, Gitleaks, Ansible/GitOps deploy"
  [vault-rbac-onboarding]="HashiCorp Vault team onboarding as policy-as-code with an end-to-end isolation test"
  [ansible-ha-databases]="Ansible roles for PostgreSQL (Patroni + Keepalived) and Redis Sentinel failover clusters"
)
declare -A TOPICS=(
  [terraform-hybrid-iac]="terraform,openstack,iac,gitlab-ci,devops"
  [gitlab-ci-templates]="gitlab-ci,ci-cd,kaniko,sonarqube,trivy,devops"
  [vault-rbac-onboarding]="vault,hashicorp-vault,terraform,rbac,secrets-management,devops"
  [ansible-ha-databases]="ansible,postgresql,patroni,keepalived,redis-sentinel,high-availability,devops"
)
for r in "${!DESC[@]}"; do
  ( cd "$r"
    git init -q -b main
    git add -A && git commit -qm "Initial commit"
    gh repo create "ftonita/$r" --public --description "${DESC[$r]}" --source . --push
    gh repo edit "ftonita/$r" --add-topic "${TOPICS[$r]}"
  )
done
echo "Done. Now pin these 4 repos on your profile (Customize your pins)."

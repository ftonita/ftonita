# examples/gitops-repo

Synthetic GitOps repository that the `argocd` deploy method writes to. Everything here is fictional.

```
charts/app/                 one generic Helm chart shared by all apps
apps/<app>/<env>/values.yaml  per-app, per-environment values (image.tag is bumped by CI)
argocd/project.yaml         AppProject: allowed source repo and destinations
argocd/applicationset.yaml  one Application per apps/<app>/<env> directory
```

## How a release flows

1. `pipeline-platform` builds `nexus.example.com:8082/shop/orders-api:<short-sha>`.
2. The `deploy:dev` job runs `pipeline-platform bump-tag --file apps/orders-api/dev/values.yaml --tag <short-sha>`, commits and pushes.
3. ArgoCD sees the commit and syncs `orders-api-dev`. Git history is the deployment history; rollback is `git revert`.
4. `stage` and `prod` are manual jobs in the same pipeline, so promotion is an explicit click with an audit trail.

## What is and is not verified

- The values files are valid YAML and `image.tag` bumping is covered by unit tests in the parent repo.
- `helm lint`, `helm template` and manifest schema validation run in the parent repo's GitHub Actions workflow. They were **not** run by the author's sandbox (no Helm binary available there).
- The ApplicationSet was never applied to a live ArgoCD instance.

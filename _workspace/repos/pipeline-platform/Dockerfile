# Image used by `platform:generate` and by the ArgoCD deploy job (git + argocd CLI).
FROM python:3.12-slim

ARG ARGOCD_VERSION=v2.12.4
RUN apt-get update \
 && apt-get install -y --no-install-recommends git curl ca-certificates \
 && curl -fsSL -o /usr/local/bin/argocd \
      "https://github.com/argoproj/argo-cd/releases/download/${ARGOCD_VERSION}/argocd-linux-amd64" \
 && chmod +x /usr/local/bin/argocd \
 && apt-get purge -y curl && apt-get autoremove -y && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/pipeline-platform
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir .

# GitLab runs jobs with its own uid; keep the image usable without root-only paths.
USER 1000
ENTRYPOINT []

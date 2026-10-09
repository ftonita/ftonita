<p align="center">
  <img src="assets/banner.svg" alt="Iskander Safin, DevOps Engineer. Platform and reliability." width="100%">
</p>

<p align="center">
  <b><i>Reviewed infrastructure. Boring pipelines. Secrets nobody pastes in chat.</i></b><br>
  <sub>Kazan · UTC+3 · fully remote</sub>
</p>

<p align="center">
  <a href="https://t.me/ftonita"><img alt="Telegram: @ftonita" src="https://img.shields.io/badge/Telegram-%40ftonita-167CAF?style=for-the-badge&logo=telegram&logoColor=white"></a>
  <a href="mailto:farmtonita@gmail.com"><img alt="Email: farmtonita@gmail.com" src="https://img.shields.io/badge/Email-farmtonita%40gmail.com-D04432?style=for-the-badge&logo=gmail&logoColor=white"></a>
</p>

> [!NOTE]
> **Open to remote DevOps / Platform / SRE roles with international teams.** Message me on Telegram or by email.

## About

I build the platform that product teams ship on: infrastructure that is reviewed and repeatable, pipelines that are boring in the best way, and secrets that never travel through chat. 5+ years in IT infrastructure, 3+ of them in DevOps. At *Smart Horizon* I run hybrid infrastructure (OpenStack, VK Cloud, Yandex Cloud) for several microfinance products; at Sber I rebuilt release pipelines. I mentor junior engineers and run technical interviews.

## Impact

<table>
  <tr>
    <td align="center" valign="top" width="50%"><h3>14 → 3–4 days</h3>release delivery time<br><sub>CI/CD rebuilt for 2 teams · Sber</sub></td>
    <td align="center" valign="top" width="50%"><h3>90%</h3>of deployments automated<br><sub>GitLab CI/CD + Ansible · onboarding in 1–2 days</sub></td>
  </tr>
  <tr>
    <td align="center" valign="top"><h3>1000+ credentials</h3>moved to Vault for 10+ teams<br><sub>custom RBAC and secret engines</sub></td>
    <td align="center" valign="top"><h3>50+ developers</h3>on a least-privilege model<br><sub>access control that did not exist before</sub></td>
  </tr>
  <tr>
    <td align="center" valign="top"><h3>4 environments</h3>across 3 products, one Terraform solution<br><sub>every change through a merge request</sub></td>
    <td align="center" valign="top"><h3>700 hosts</h3>monitored in one place<br><sub>Zabbix/Glaber + Grafana · logs via Kafka → OpenSearch</sub></td>
  </tr>
</table>

## Selected work

Reference implementations of patterns from my DevOps work, rebuilt from scratch on **synthetic data** (no employer code or data). Each README ends with what was verified and what was not.

**[pipeline-platform](https://github.com/ftonita/pipeline-platform)** &nbsp;[![CI](https://github.com/ftonita/pipeline-platform/actions/workflows/ci.yml/badge.svg)](https://github.com/ftonita/pipeline-platform/actions)<br>
One `.platform.yml` replaces a whole CI config: JSON Schema validation, then a GitLab child pipeline with only the jobs that apply. Vault via `id_tokens`, SHA-tagged images in Nexus, deploy by Ansible, Helm or ArgoCD.<br>
<sub>GitLab CI · Vault · Nexus · Helm · ArgoCD · Python</sub>

**[vault-migration-toolkit](https://github.com/ftonita/vault-migration-toolkit)** &nbsp;[![CI](https://github.com/ftonita/vault-migration-toolkit/actions/workflows/ci.yml/badge.svg)](https://github.com/ftonita/vault-migration-toolkit/actions)<br>
Moves secrets from legacy storage into Vault safely: finds weak and reused ones, maps them to team and environment paths, applies with check-and-set, verifies. Never prints a value. Tested against a real Vault in CI.<br>
<sub>Vault KV v2 · Python · migration safety</sub>

**[access-as-code](https://github.com/ftonita/access-as-code)** &nbsp;[![CI](https://github.com/ftonita/access-as-code/actions/workflows/ci.yml/badge.svg)](https://github.com/ftonita/access-as-code/actions)<br>
Who may do what, as reviewed YAML. Eleven least-privilege lint rules; compiles to Vault policies, Kubernetes RBAC and GitLab members; detects drift.<br>
<sub>Vault · Kubernetes RBAC · GitLab · policy-as-code</sub>

**[release-bottleneck-analyzer](https://github.com/ftonita/release-bottleneck-analyzer)** &nbsp;[![CI](https://github.com/ftonita/release-bottleneck-analyzer/actions/workflows/ci.yml/badge.svg)](https://github.com/ftonita/release-bottleneck-analyzer/actions)<br>
Finds where lead time is really lost (review, merge or release queue), computes DORA-style metrics and estimates what a fix would save.<br>
<sub>DORA metrics · Python · zero runtime dependencies</sub>

**[opsbot](https://github.com/ftonita/opsbot)** &nbsp;[![CI](https://github.com/ftonita/opsbot/actions/workflows/ci.yml/badge.svg)](https://github.com/ftonita/opsbot/actions)<br>
A ChatOps Telegram bot for on-call: roles, rate limits, an audit trail and a two-person rule for production changes.<br>
<sub>aiogram · Alertmanager · security design</sub>

## Learning in public

**[devops-cursus](https://github.com/ftonita/devops-cursus)**: Russian-language DevOps manuals I write to refresh the fundamentals and to learn AI-assisted engineering.

- **Content:** four manuals so far (Git, CI/CD, Docker, Git workflow), three with self-check quizzes, plus a shared glossary. Next on the [roadmap](https://github.com/ftonita/devops-cursus/blob/main/ROADMAP.MD): Kubernetes, IaC, monitoring, DevSecOps, SRE.
- **How it is made:** a small multi-agent pipeline (researcher → writer → reviewer → quiz builder), each agent on the model tier that fits its job.
- **How it ships:** a [MkDocs site](https://ftonita.github.io/devops-cursus/) built and published by a GitHub Actions workflow that doubles as a worked example for the CI/CD lesson.

## How I work

- **Everything as code, reviewed in merge requests:** infrastructure, access and pipelines.
- **AI-assisted, test-gated:** I use AI assistants for drafts and review; tests and CI decide what ships.
- **Honest documentation:** every project states what was verified and what was not.

## Toolbox

<table>
  <tr>
    <td><b>IaC &amp; cloud</b></td>
    <td><img alt="Terraform" src="https://img.shields.io/badge/-Terraform-7B42BC?style=flat-square&logo=terraform&logoColor=white"> <img alt="Ansible" src="https://img.shields.io/badge/-Ansible-EE0000?style=flat-square&logo=ansible&logoColor=white"> <img alt="OpenStack" src="https://img.shields.io/badge/-OpenStack-E7123D?style=flat-square&logo=openstack&logoColor=white"> <img alt="VK Cloud" src="https://img.shields.io/badge/-VK_Cloud-006FED?style=flat-square&logo=vk&logoColor=white"> <img alt="Yandex Cloud" src="https://img.shields.io/badge/-Yandex_Cloud-E32503?style=flat-square&logo=yandexcloud&logoColor=white"></td>
  </tr>
  <tr>
    <td><b>CI/CD &amp; GitOps</b></td>
    <td><img alt="GitLab CI" src="https://img.shields.io/badge/-GitLab_CI-CE4603?style=flat-square&logo=gitlab&logoColor=white"> <img alt="Jenkins" src="https://img.shields.io/badge/-Jenkins-D14333?style=flat-square&logo=jenkins&logoColor=white"> <img alt="ArgoCD" src="https://img.shields.io/badge/-ArgoCD-CE4812?style=flat-square&logo=argo&logoColor=white"> <img alt="SonarQube" src="https://img.shields.io/badge/-SonarQube-307BAB?style=flat-square&logo=sonarqube&logoColor=white"> <img alt="Nexus" src="https://img.shields.io/badge/-Nexus-1B1C30?style=flat-square&logo=sonatype&logoColor=white"></td>
  </tr>
  <tr>
    <td><b>Containers</b></td>
    <td><img alt="Kubernetes" src="https://img.shields.io/badge/-Kubernetes-326CE5?style=flat-square&logo=kubernetes&logoColor=white"> <img alt="OpenShift" src="https://img.shields.io/badge/-OpenShift-EE0000?style=flat-square&logo=redhatopenshift&logoColor=white"> <img alt="Helm" src="https://img.shields.io/badge/-Helm-0F1689?style=flat-square&logo=helm&logoColor=white"> <img alt="Docker" src="https://img.shields.io/badge/-Docker-1077C6?style=flat-square&logo=docker&logoColor=white"> <img alt="k3s" src="https://img.shields.io/badge/-k3s-FFC61C?style=flat-square&logo=k3s&logoColor=black"></td>
  </tr>
  <tr>
    <td><b>Security &amp; observability</b></td>
    <td><img alt="Vault" src="https://img.shields.io/badge/-Vault-FFEC6E?style=flat-square&logo=vault&logoColor=black"> <img alt="Prometheus" src="https://img.shields.io/badge/-Prometheus-D33F19?style=flat-square&logo=prometheus&logoColor=white"> <img alt="Grafana" src="https://img.shields.io/badge/-Grafana-C15200?style=flat-square&logo=grafana&logoColor=white"> <img alt="Zabbix" src="https://img.shields.io/badge/-Zabbix-CC2936?style=flat-square&logo=zabbix&logoColor=white"></td>
  </tr>
  <tr>
    <td><b>Data, code &amp; OS</b></td>
    <td><img alt="PostgreSQL" src="https://img.shields.io/badge/-PostgreSQL-4169E1?style=flat-square&logo=postgresql&logoColor=white"> <img alt="Redis" src="https://img.shields.io/badge/-Redis-DC382D?style=flat-square&logo=redis&logoColor=white"> <img alt="Python" src="https://img.shields.io/badge/-Python-3776AB?style=flat-square&logo=python&logoColor=white"> <img alt="Bash" src="https://img.shields.io/badge/-Bash-3D841D?style=flat-square&logo=gnubash&logoColor=white"> <img alt="Linux" src="https://img.shields.io/badge/-Linux-FCC624?style=flat-square&logo=linux&logoColor=black"></td>
  </tr>
</table>

<sub>Also: Patroni, Redis Sentinel, Keepalived, MySQL tuning, VictoriaMetrics, Filebeat, Kafka, OpenSearch, Nginx, Django/DRF, aiogram.</sub>

## Education and achievements

- **School 21** (Ecole 42 curriculum), Kazan: Software Engineering, alumnus 2024; volunteer mentor for new participants.
- **Languages:** Russian (native), English B2 with working proficiency in technical communication.
- Hackathons: 🥇 Stackers New Year web hackathon (DevOps, backend) · 🥈 School 21 Data Science (team lead) · 🥉 Roseltorg.

<details>
<summary><b>Older projects: Python, web and systems programming</b></summary>

- [PassBot](https://github.com/ftonita/PassBot): pass-control Telegram bot with a web interface, containerised with Docker Compose.
- [MicroShop](https://github.com/ftonita/MicroShop_on_Django) · [Simple Blog](https://github.com/ftonita/Simple_Blog_on_Django): Django / DRF applications (Stripe, sessions, accounts).
- [Inception](https://github.com/ftonita/Inception): WordPress stack on a VM with Docker Compose and Make only.
- [NetPractice](https://github.com/ftonita/NetPractice) · [born2beroot](https://github.com/ftonita/born2beroot): networking and Linux hardening.
- C / C++ foundations from the 42 curriculum: [libft](https://github.com/ftonita/libft), [minishell](https://github.com/ftonita/minishell), [Philosophers](https://github.com/ftonita/Philosophers), [CPP Modules](https://github.com/ftonita/CPP).

</details>

<p align="center">
  Let's talk: <a href="https://t.me/ftonita">Telegram @ftonita</a> · <a href="mailto:farmtonita@gmail.com">farmtonita@gmail.com</a>
</p>

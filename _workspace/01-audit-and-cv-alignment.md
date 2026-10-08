# 1. Аудит публичного GitHub и сверка с CV (v3)

> Источник: публичный профиль и GitHub Search API (50 репозиториев), состояние на 2026-10-08. Содержимое отдельных DevOps-репозиториев (jenkins-demo, devops-cursus, clickhouse-backup-ansible и др.) я не смог открыть: у сессии доступ только к `ftonita/ftonita`. Их стоит просмотреть самому по чек-листу ниже.

## Что есть сейчас
| Показатель | Значение |
|---|---|
| Репозитории / подписчики / звёзды | ~50 / 49 / 5 |
| Pinned | Philosophers, minitalk, libft, MicroShop (всё C и Django 2021-2022) |
| Bio | «DevOps, Python (WEB, tgAPI), C/C++» |
| README | Список учебных проектов, карточки github-readme-stats, никаких результатов |
| Свежая активность | jenkins-demo (09.2026), devops-cursus (09.2026), example-app (03.2026), clickhouse-backup-ansible (06.2026) |

## Расхождения с CV
| CV | GitHub | Вывод |
|---|---|---|
| Позиционирование: DevOps, 5+ лет, Terraform/Vault/GitOps | Первое впечатление: студент 42 (C, libft, minishell) | Главная проблема: pinned и README рассказывают про 2021-2022 |
| Метрики (14→3-4 дня, 90%, 1000+ секретов, 10+ команд) | Ни одной цифры | В README добавлен блок Impact |
| Terraform, Vault, ArgoCD, Patroni, Redis Sentinel, GitLab-шаблоны | Нет ни одного публичного примера | Созданы 4 референс-репозитория |
| Kubernetes/ArgoCD/Helm | Нет | Следующий репозиторий в роадмапе |
| «Web developer» в заголовке | CV уже DevOps | Заголовок переписан |
| Python/Django | Есть | Оставлено, свернуто в `<details>` |

## Мусор, который рекрутер увидит за 10 секунд
Пустые, безымянные, дублирующиеся и учебные репозитории без описания: `undefined`, `cv`, `passbot21`, `21passbot`, `nur_fest`, `jazz_dev`, `signories`, `userbot`, `userbot_repo`, `gnl_1`, `minishell-1`, `python-devops`, `docker-compose-jenkins`, `example-*`, `21_PythonDS_Test` и т.д.

**Рекомендация (делаешь сам, я ничего не удаляю):**
1. Пустые и дубли: Settings → Archive или Make private.
2. Учебные C/42-проекты: оставить публичными, но убрать из pinned.
3. Для каждого оставшегося: description + topics. Без README и описания репозиторий лучше скрыть.
4. Посмотреть `jenkins-demo`, `devops-cursus`, `clickhouse-backup-ansible`: если там нет секретов и приватных данных, довести до уровня новых репозиториев (README, CI, LICENSE) или заменить новыми.
5. Проверить историю всех публичных репозиториев на утечки (`gitleaks detect`), особенно `vpnbot_devops`, `PassBot`, `userbot*`.

## Hygiene профиля
- Bio: `DevOps Engineer · Terraform · Vault · GitLab CI · Kubernetes · Ansible`
- Company: `@Smart Horizon`, Location: `Kazan / Remote`, Website: Telegram или LinkedIn
- Pinned (6): 4 новых репозитория + PassBot + Inception
- Включить «Private contributions» в настройках, чтобы рабочая активность была видна на графике

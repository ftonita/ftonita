# ansible-ha-databases

[![ci](https://github.com/ftonita/ansible-ha-databases/actions/workflows/ci.yml/badge.svg)](https://github.com/ftonita/ansible-ha-databases/actions)
![Ansible](https://img.shields.io/badge/Ansible-ansible--lint_production-EE0000?logo=ansible&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Patroni_HA-4169E1?logo=postgresql&logoColor=white)
![Redis](https://img.shields.io/badge/Redis-Sentinel-DC382D?logo=redis&logoColor=white)

Ansible roles for highly available data stores with **automatic failover**:

- **PostgreSQL**: etcd (DCS) + Patroni + Keepalived. A virtual IP always follows the current primary, so applications use one stable address.
- **Redis**: replication + Sentinel with quorum.

> A sanitised version of the failover clusters I designed and run in production. No employer code or data.

## Architecture

```mermaid
flowchart LR
    App --> VIP(("VIP 10.0.0.10"))
    VIP --> PG1["pg1 (primary)"]
    PG1 -. streaming replication .-> PG2["pg2 (replica)"]
    PG1 -. streaming replication .-> PG3["pg3 (replica)"]
    ETCD[("etcd quorum")] --- PG1
    ETCD --- PG2
    ETCD --- PG3
```

Keepalived tracks `GET /primary` on the local Patroni REST API: only the leader holds the VIP, and it moves within seconds of a Patroni promotion.

## Usage

```bash
cp -r inventories/example inventories/prod        # edit hosts and group_vars
ansible-vault create inventories/prod/group_vars/vault.yml
# define: vault_patroni_superuser_password, vault_patroni_replication_password, vault_redis_password
ansible-playbook -i inventories/prod site.yml --check --diff   # dry run
ansible-playbook -i inventories/prod site.yml
```

## Design notes

- `serial: 1`: nodes are changed one at a time, the cluster never goes down for a config roll.
- `use_pg_rewind` + `maximum_lag_on_failover`: a stale replica is never promoted; a former primary rejoins without a full rebuild.
- Passwords are templated with `no_log`, files are `0640`, nothing secret is in Git.
- Lints clean with `ansible-lint` **production** profile (enforced in CI).

## Roadmap

- [ ] Molecule scenario (Docker) for converge + failover test
- [ ] pgBackRest backups and restore check
- [ ] Prometheus exporters and alert rules

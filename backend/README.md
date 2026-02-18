## Backend Workspace

Use this directory for backend code, tests, and Python tooling.

### Common Commands

```bash
make help
make dev
make test
make lint
make format
```

### Docker Compose

Compose files are maintained at repository root as the single source of truth:

- `../docker-compose.yml`
- `../docker-compose.local.yml`

`make docker-*` and `make local-*` from this directory are wired to those root compose files and root `.env`.

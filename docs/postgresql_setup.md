# PostgreSQL Setup

## Architecture

```text
Windows
   |
   v
Docker
   |
   v
PostgreSQL container
   |
   v
saleslens database
```

## Configuration

The Docker Compose configuration is in `docker/compose.yml`.

- Service: `postgres`
- Container: `saleslens-postgres`
- PostgreSQL image: `postgres:15`
- Database: `saleslens`
- User: `saleslens_user`
- Host port: `5432`
- Container port: `5432`
- Persistent Docker volume: `saleslens_postgres_data`

Local credentials are in `.env`, which Git ignores. `.env.example` is the versioned template and contains only placeholder values. Do not commit `.env` or a real password.

## Main Commands

Run all commands from the project root.

Start PostgreSQL in the background:

```powershell
docker compose --env-file .env -f docker/compose.yml up -d
```

Check service status and health:

```powershell
docker compose --env-file .env -f docker/compose.yml ps
```

View PostgreSQL logs:

```powershell
docker compose --env-file .env -f docker/compose.yml logs postgres
```

Stop the container while preserving the database volume:

```powershell
docker compose --env-file .env -f docker/compose.yml down
```

Restart the environment:

```powershell
docker compose --env-file .env -f docker/compose.yml up -d
```

## Connection Parameters

- Host: `localhost`
- Port: `5432`
- Database: `saleslens`
- User: `saleslens_user`
- Password: value stored locally in `.env`

`localhost:5432` means an application running on this Windows machine connects to port 5432 on the local machine. Docker forwards that port to PostgreSQL port 5432 inside the container.

## Container and Volume

A container is the running, isolated PostgreSQL application. It can be stopped, recreated, or upgraded without changing the project files.

The Docker volume is persistent storage managed by Docker. `saleslens_postgres_data` stores PostgreSQL database files outside the container lifecycle. Therefore `docker compose down` removes the container but keeps the database data. Removing the volume explicitly would remove the database data.

## Verification

The setup is validated with `pg_isready`, `SELECT version()`, `SELECT current_database()`, `SELECT current_user`, and `SELECT 1`. No SalesLens business table or CSV data is created or loaded during this setup step.

# approval-service

FastAPI-сервис для согласования контента перед публикацией. Сервис принимает заявки на approval, хранит историю изменений, не допускает кросс-workspace доступа, поддерживает идемпотентные повторы mutating-запросов и готов к дальнейшей интеграции через outbox-события.

## Highlights

- FastAPI + SQLAlchemy 2 + Alembic
- SQLite для локального запуска, PostgreSQL через `docker compose`
- `workspace_id` как жёсткая граница данных
- idempotency через `Idempotency-Key` для всех mutating POST
- финальные статусы без повторного перехода
- audit trail по успешным изменениям
- outbox-таблица для последующей доставки доменных событий
- auth stub на заголовках без внешнего identity provider

## API

```text
GET    /health
GET    /ready
POST   /api/v1/workspaces/{workspace_id}/approval-requests
GET    /api/v1/workspaces/{workspace_id}/approval-requests
GET    /api/v1/workspaces/{workspace_id}/approval-requests/{request_id}
POST   /api/v1/workspaces/{workspace_id}/approval-requests/{request_id}/approve
POST   /api/v1/workspaces/{workspace_id}/approval-requests/{request_id}/reject
POST   /api/v1/workspaces/{workspace_id}/approval-requests/{request_id}/cancel
```

## Domain rules

- данные одного `workspace` недоступны из другого
- повтор того же запроса с тем же `Idempotency-Key` не создаёт дубль
- reuse того же `Idempotency-Key` с другим телом даёт `409 Conflict`
- `approved`, `rejected`, `canceled` считаются финальными статусами
- каждое успешное изменение пишет след в `approval_request_events`
- каждое успешное изменение пишет доменное событие в `outbox_events`
- в публичные ответы и события не попадают provider payloads, токены, email и другие чувствительные поля

## Project structure

```text
app/
  api/            HTTP routes and dependencies
  core/           config
  db/             SQLAlchemy base and session
  models/         persistence models
  repositories/   data access
  schemas/        request and response schemas
  services/       business logic
alembic/          database migrations
tests/            API tests
```

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload
```

По умолчанию сервис стартует на `http://127.0.0.1:8000` и использует:

```bash
DATABASE_URL=sqlite:///./approval_service.db
```

## Docker

```bash
docker compose up --build
```

Это поднимает:

- приложение на `http://127.0.0.1:8000`
- PostgreSQL на `localhost:5432`

## Auth stub

Для локального запуска авторизация задаётся заголовками:

- `X-Auth-Workspace-Id`
- `X-Auth-User-Id`
- `X-Auth-Actions`
- `Idempotency-Key`

Пример набора заголовков:

```bash
-H "X-Auth-Workspace-Id: ws_1" \
-H "X-Auth-User-Id: usr_author" \
-H "X-Auth-Actions: approval:create,approval:read,approval:decide,approval:cancel" \
-H "Idempotency-Key: req-001"
```

Поддерживаемые действия:

- `approval:read`
- `approval:create`
- `approval:decide`
- `approval:cancel`

`X-Auth-Workspace-Id` обязан совпадать с `{workspace_id}` в URL.

## Running tests

```bash
pytest
```

GitHub Actions запускает `pytest` на каждом push в `main` и на каждом pull request.

## Example requests

Создание заявки:

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/workspaces/ws_1/approval-requests" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: req-create-1" \
  -H "X-Auth-Workspace-Id: ws_1" \
  -H "X-Auth-User-Id: usr_author" \
  -H "X-Auth-Actions: approval:create,approval:read" \
  -d '{
    "sourceType": "publication",
    "sourceId": "pub_123",
    "title": "Instagram reel draft",
    "description": "Needs final approval",
    "reviewerUserIds": ["usr_1", "usr_2"]
  }'
```

Approve:

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/workspaces/ws_1/approval-requests/{request_id}/approve" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: req-approve-1" \
  -H "X-Auth-Workspace-Id: ws_1" \
  -H "X-Auth-User-Id: usr_reviewer" \
  -H "X-Auth-Actions: approval:decide,approval:read" \
  -d '{"comment":"Approved"}'
```

Reject:

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/workspaces/ws_1/approval-requests/{request_id}/reject" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: req-reject-1" \
  -H "X-Auth-Workspace-Id: ws_1" \
  -H "X-Auth-User-Id: usr_reviewer" \
  -H "X-Auth-Actions: approval:decide,approval:read" \
  -d '{"reason":"Brand tone is wrong"}'
```

Cancel:

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/workspaces/ws_1/approval-requests/{request_id}/cancel" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: req-cancel-1" \
  -H "X-Auth-Workspace-Id: ws_1" \
  -H "X-Auth-User-Id: usr_author" \
  -H "X-Auth-Actions: approval:cancel,approval:read" \
  -d '{"reason":"Draft was removed"}'
```

## Notes

- Детали модели данных, idempotency и интеграционного подхода описаны в [DESIGN.md](./DESIGN.md)
- Для локальной проверки доступны `/health` и `/ready`

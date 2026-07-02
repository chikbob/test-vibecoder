# approval-service

Backend-сервис согласования контента на FastAPI.

## Что реализовано

- создание заявки на согласование;
- список заявок в рамках `workspace`;
- получение одной заявки;
- approve / reject / cancel;
- изоляция данных по `workspace_id`;
- идемпотентность для всех mutating POST через `Idempotency-Key`;
- audit trail в таблице `approval_request_events`;
- outbox-таблица `outbox_events` для последующей интеграции через события;
- защита публичных ответов и событий от сырых provider payloads и секретов: сервис принимает только безопасные поля доменной модели.

## Стек

- Python 3.9+
- FastAPI
- SQLAlchemy 2
- Alembic
- SQLite для локального запуска
- PostgreSQL в `docker-compose`

## Auth stub

Для локального запуска используется auth-заглушка на заголовках:

- `X-Auth-Workspace-Id`: workspace пользователя
- `X-Auth-User-Id`: внешний идентификатор пользователя
- `X-Auth-Actions`: список действий через запятую
- `Idempotency-Key`: обязателен для идемпотентных повторов mutating POST

Пример:

```bash
-H "X-Auth-Workspace-Id: ws_1" \
-H "X-Auth-User-Id: usr_1" \
-H "X-Auth-Actions: approval:create,approval:read,approval:decide,approval:cancel"
```

Проверки:

- `X-Auth-Workspace-Id` должен совпадать с `{workspace_id}` в URL;
- для каждого endpoint требуется соответствующее действие:
  - `approval:read`
  - `approval:create`
  - `approval:decide`
  - `approval:cancel`

## Локальный запуск

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload
```

По умолчанию используется SQLite:

```bash
DATABASE_URL=sqlite:///./approval_service.db
```

Сервис будет доступен на `http://127.0.0.1:8000`.

## Docker

```bash
docker compose up --build
```

Сервис будет доступен на `http://127.0.0.1:8000`, PostgreSQL на `localhost:5432`.

## Тесты

```bash
pytest
```

## Примеры запросов

Создание:

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

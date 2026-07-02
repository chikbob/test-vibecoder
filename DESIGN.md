# DESIGN

## Границы сервиса

Сервис хранит только процесс согласования. Все внешние сущности передаются как идентификаторы:

- `workspace_id`
- `source_type`
- `source_id`
- `reviewer_user_ids`
- `created_by_user_id`
- `decision_by_user_id`

Ни публикации, ни сценарии, ни пользователи, ни workspace-справочники сервис не материализует.

## Модель данных

### `approval_requests`

Основная заявка:

- идентификатор заявки;
- `workspace_id`;
- тип и идентификатор внешнего объекта;
- заголовок и описание;
- список reviewer user ids;
- текущий статус;
- кто создал заявку;
- кто принял финальное решение;
- комментарий approve или причина reject/cancel;
- timestamps.

### `approval_request_events`

Audit trail успешных изменений:

- тип события (`created`, `approved`, `rejected`, `canceled`);
- actor;
- безопасный payload изменения;
- время.

### `outbox_events`

Подготовка к интеграции через события:

- topic;
- aggregate type / id;
- workspace;
- безопасный payload доменного события;
- время создания.

### `idempotency_records`

Таблица хранения повторов клиентских POST:

- `workspace_id`;
- операция;
- `Idempotency-Key`;
- hash тела запроса;
- сохраненный HTTP status;
- сохраненный response body.

Уникальность: `(workspace_id, operation, idempotency_key)`.

## Обработка повторов

Для всех mutating POST поддерживается `Idempotency-Key`.

Алгоритм:

1. сервис считает SHA-256 от тела запроса;
2. ищет запись `(workspace_id, operation, idempotency_key)`;
3. если запись найдена и hash совпадает, возвращает прежний ответ;
4. если запись найдена, но hash отличается, отвечает `409 Conflict`;
5. если записи нет, выполняет бизнес-изменение и записывает idempotency record в той же транзакции.

Это исключает создание дублей при корректном повторе одного и того же клиентского запроса.

## Финальные состояния

Статусы:

- `pending`
- `approved`
- `rejected`
- `canceled`

`approved`, `rejected`, `canceled` считаются финальными. После перехода в любой из них заявка больше не может менять финальный статус; сервис отвечает `409 Conflict`.

## Изоляция workspace

Во всех запросах выборка идет по `(workspace_id, request_id)` или только по `workspace_id`. Auth stub дополнительно требует совпадения `X-Auth-Workspace-Id` и path-параметра `{workspace_id}`.

## События и интеграции

Сейчас сервис только пишет доменные события в `outbox_events`. Это дает базу для дальнейшего фонового publisher-а в Kafka, NATS, SQS или другой транспорт без изменения прикладной логики API.

События intentionally ограничены безопасными полями доменной модели. В них не попадают:

- секреты;
- токены;
- email;
- storage keys;
- signed URLs;
- provider URLs;
- сырые provider payloads.

## Компромиссы

- reviewer membership сейчас хранится списком строк в одной записи, без отдельной join-таблицы;
- auth stub проверяет только workspace и action scopes, без JWT и real identity provider;
- нет отдельного publisher-процесса для outbox, только таблица;
- нет optimistic locking / version column, потому что для тестового задания достаточно транзакционной проверки финального статуса и идемпотентности.

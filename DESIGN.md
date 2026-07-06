# Design Notes — Approval Service

## Модель данных

Два объекта: заявка и решение.

```
approval_requests
├── id                UUID, PK
├── workspace_id      String  — область видимости
├── source_type       Enum    — publication | scenario | edit | external
├── source_id         String  — внешний идентификатор объекта
├── title             String
├── description       String, nullable
├── reviewer_user_ids JSON    — список внешних идентификаторов пользователей
├── created_by        String  — внешний идентификатор автора
├── status            Enum    — pending | approved | rejected | cancelled
├── idempotency_key   String, nullable, unique per workspace
├── created_at        DateTime
└── updated_at        DateTime

approval_decisions
├── id              UUID, PK
├── request_id      FK → approval_requests.id
├── action          Enum    — approve | reject | cancel
├── actor_user_id   String
├── comment         String, nullable  — для approve
├── reason          String, nullable  — для reject / cancel
└── created_at      DateTime
```

Решения хранятся отдельной таблицей, а не перезаписывают поля заявки — это сохраняет полную историю изменений.

---

## Границы сервиса

Сервис управляет только процессом согласования. Всё, что находится за его пределами — публикации, сценарии, пользователи, рабочие пространства — передаётся как внешние идентификаторы и не валидируется. Сервис не знает, существуют ли `source_id` или `reviewer_user_ids` в реальности.

Изоляция по `workspace_id` обеспечивается на уровне каждого запроса к БД — фильтрация по `workspace_id` обязательна во всех эндпоинтах. Заявка из чужого workspace недоступна и возвращает `404`.

---

## Обработка повторов

Идемпотентность реализована через заголовок `Idempotency-Key`. Ключ хранится в `approval_requests.idempotency_key` с уникальным ограничением `(workspace_id, idempotency_key)`.

Алгоритм:
1. Если ключ передан — ищем существующую запись.
2. Если найдена — возвращаем `200` с тем же объектом без записи в БД.
3. Если не найдена — создаём. При гонке двух одновременных запросов `IntegrityError` перехватывается и возвращается уже созданная запись.

Запросы без `Idempotency-Key` всегда создают новую заявку.

Переход в финальный статус (`approved`, `rejected`, `cancelled`) необратим — повторный вызов любого action-эндпоинта вернёт `409 Conflict`.

---

## События и интеграции

При каждом изменении состояния вызывается `publish_event(event_type, payload)` (`app/events.py`). Текущая реализация — логирование. Тело функции заменяется на публикацию в брокер (Kafka, RabbitMQ, SNS) без изменения остального кода.

| Событие                          | Когда                   |
|----------------------------------|-------------------------|
| `approval_request.created`       | заявка создана          |
| `approval_request.approved`      | заявка согласована      |
| `approval_request.rejected`      | заявка отклонена        |
| `approval_request.cancelled`     | заявка отменена         |

Payload содержит только идентификаторы (`requestId`, `workspaceId`, `actorUserId`). Персональные данные, токены и внутренние URL в события не попадают.

---

## Известные компромиссы

**Auth-заглушка.** Заголовки `X-User-Id` и `X-Permissions` принимаются без верификации подписи. В продакшене нужен middleware, проверяющий JWT или вызывающий auth-сервис.

**Один финальный решатель.** Сервис не проверяет, что решение принимает один из `reviewer_user_ids`. Любой пользователь с правом `approval:decide` может принять решение. Логика мажоритарного голосования не реализована.

**Нет пагинации.** `GET /approval-requests` возвращает все заявки workspace без ограничений. При большом объёме нужна пагинация (offset/cursor).

**Синхронные события.** `publish_event` вызывается внутри HTTP-запроса. При медленном брокере это увеличит latency. Решение — отдельная очередь или outbox-паттерн.

**SQLite в тестах.** Тесты используют SQLite вместо PostgreSQL, поэтому поведение JSON-полей и некоторые edge-cases могут отличаться.

# Approval Service

Бэкенд-сервис для согласования контента перед публикацией. Принимает заявки на согласование и фиксирует итоговое решение (approve / reject / cancel).

## Содержание

- [Стек](#стек)
- [Требования](#требования)
- [Установка](#установка)
- [Запуск](#запуск)
- [Тесты](#тесты)
- [Аутентификация](#аутентификация)
- [API](#api)
- [Миграции](#миграции)

---

## Стек

- **Python 3.12** + **FastAPI**
- **PostgreSQL 15** (Docker) / **SQLite** (локально)
- **SQLAlchemy 2.0** + **Alembic**
- **pytest** + **httpx**

---

## Требования

- [Python 3.12+](https://www.python.org/downloads/)
- [Docker](https://docs.docker.com/get-docker/) и [Docker Compose](https://docs.docker.com/compose/) — для запуска через Docker
- [Git](https://git-scm.com/)

---

## Установка

### 1. Клонировать репозиторий

```bash
git clone https://github.com/AlenaSygrysheva/approval-service
cd approval-service
```

### 2. Настроить переменные окружения

```bash
cp .env.example .env
```

Открыть `.env` и заполнить своими значениями:

```env
POSTGRES_USER=user
POSTGRES_PASSWORD=password
POSTGRES_DB=approval_db
DATABASE_URL=postgresql://user:password@db:5432/approval_db
ENVIRONMENT=development
```

> При локальном запуске без Docker замените хост `db` на `localhost` в `DATABASE_URL`.

### 3. Установить зависимости (только для локального запуска)

```bash
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

---

## Запуск

### Docker Compose (рекомендуется)

Поднимает PostgreSQL и приложение, миграции применяются автоматически:

```bash
docker compose up --build
```

Сервис доступен на `http://localhost:8000`.  
Swagger UI: `http://localhost:8000/docs`

### Локально с SQLite (без Docker)

```bash
DATABASE_URL="sqlite:///./approval.db" alembic upgrade head
DATABASE_URL="sqlite:///./approval.db" uvicorn app.main:app --reload
```

### Локально с PostgreSQL

Запустить только базу данных:

```bash
docker compose up db
```

Применить миграции и запустить приложение:

```bash
alembic upgrade head
uvicorn app.main:app --reload
```

---

## Тесты

Тесты используют SQLite и не требуют запущенного PostgreSQL:

```bash
pytest tests/ -v
```

Для ручного тестирования — готовые curl-команды в файле `requests.http`.

---

## Аутентификация

Сервис использует заглушку авторизации. Каждый запрос (кроме `/health` и `/ready`) должен содержать заголовки:

```
X-User-Id: usr_1
X-Permissions: approval:read,approval:create,approval:decide,approval:cancel
```

| Право             | Действие              |
|-------------------|-----------------------|
| `approval:read`   | чтение заявок         |
| `approval:create` | создание заявки       |
| `approval:decide` | approve / reject      |
| `approval:cancel` | cancel                |

---

## API

| Метод | URL                                                          |
|-------|--------------------------------------------------------------|
| GET   | `/health`                                                    |
| GET   | `/ready`                                                     |
| POST  | `/api/v1/workspaces/{workspace_id}/approval-requests`        |
| GET   | `/api/v1/workspaces/{workspace_id}/approval-requests`        |
| GET   | `/api/v1/workspaces/{workspace_id}/approval-requests/{id}`   |
| POST  | `/api/v1/workspaces/{workspace_id}/approval-requests/{id}/approve` |
| POST  | `/api/v1/workspaces/{workspace_id}/approval-requests/{id}/reject`  |
| POST  | `/api/v1/workspaces/{workspace_id}/approval-requests/{id}/cancel`  |

### Создание заявки

```json
{
  "sourceType": "publication",
  "sourceId": "pub_123",
  "title": "Instagram reel draft",
  "description": "Needs final approval",
  "reviewerUserIds": ["usr_2", "usr_3"]
}
```

`sourceType`: `publication` | `scenario` | `edit` | `external`

Для идемпотентности передайте заголовок `Idempotency-Key: <ключ>` — повторный запрос вернёт `200` с уже существующей заявкой.

### Решения

```json
// approve
{ "comment": "Approved" }

// reject
{ "reason": "Brand tone is wrong" }

// cancel
{ "reason": "Draft was removed" }
```

### Статусы

```
pending → approved
        → rejected
        → cancelled
```

После перехода в финальный статус любое повторное изменение вернёт `409 Conflict`.

---

## Миграции

```bash
alembic upgrade head                          # применить все
alembic downgrade -1                          # откатить последнюю
alembic revision --autogenerate -m "name"     # сгенерировать по изменениям в моделях
```

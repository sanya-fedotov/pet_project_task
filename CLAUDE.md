# Botofarm

## Что это
RESTful микросервис-ботоферма. Сервис выдаёт пользовательские 
credentials для E2E-тестирования. Позволяет создавать пользователей,
получать их список и блокировать для использования в тестах.

## Стек (строго, без замены)
- Python 3.11+
- FastAPI + uvicorn (ASGI)
- SQLAlchemy 2 (async) + asyncpg
- PostgreSQL 14+
- Pydantic v2
- Alembic (миграции)
- passlib[bcrypt] (хеширование паролей)
- python-jose (JWT)
- pytest + httpx + pytest-asyncio
- prometheus-fastapi-instrumentator
- Docker + docker-compose
- Helm (minikube)
- ruff + mypy

## Структура проекта
app/
  api/
    v1/
      users.py       — эндпоинты пользователей
      health.py      — пробы
      auth.py        — авторизация
  core/
    config.py        — pydantic-settings
    database.py      — async engine, session, get_db
    security.py      — bcrypt, JWT
  crud/
    user.py          — CRUD операции
  models/
    user.py          — SQLAlchemy модель
  schemas/
    user.py          — Pydantic схемы
  services/
    botfarm.py       — бизнес-логика
  main.py
alembic/
  versions/
  env.py
tests/
  conftest.py
  unit/
  api/
monitoring/
  prometheus.yml
  grafana/
.github/
  workflows/
    ci.yml
    docker.yml

## Модель User (строго по ТЗ)
- id: UUID, primary key, default uuid4
- created_at: datetime, default now(), не изменяется
- login: str, email, уникальный
- password: str, только bcrypt hash, никогда не возвращается в ответе
- project_id: UUID, обязательный
- env: enum — prod | preprod | stage
- domain: enum — canary | regular
- locktime: datetime | None, nullable

## API эндпоинты (строго по ТЗ)
POST   /api/v1/users          — create_user (201)
GET    /api/v1/users          — get_users (200)
POST   /api/v1/users/lock     — lock_user (200 или 404)
POST   /api/v1/users/free     — free_users (200)
POST   /api/v1/auth/token     — получить JWT
GET    /api/v1/health         — liveness probe
GET    /api/v1/health/ready   — readiness probe
GET    /metrics               — Prometheus метрики

## Логика блокировки (критично)
lock_user:
  - Ищет первого пользователя где locktime IS NULL 
    или locktime < now() - LOCK_TTL_SECONDS
  - Использует SELECT FOR UPDATE SKIP LOCKED (атомарно)
  - Устанавливает locktime = now()
  - Возвращает пользователя или 404 если все заняты

free_users:
  - Устанавливает locktime = NULL у всех пользователей
  - Возвращает количество разблокированных

## Принципы (обязательны для всех агентов)
- Clean Architecture: api → service → crud → model
  Бизнес-логика только в services/
  Работа с БД только в crud/
  Валидация только в schemas/
- SOLID: одна ответственность на модуль
- DRY: никакого дублирования
- Async везде: весь I/O через async/await, ноль блокирующих вызовов
- Type hints: на всех функциях включая возвращаемые типы
- Docstrings: Google-style на всех публичных функциях и классах
- PEP8: snake_case функции, PascalCase классы, UPPER_CASE константы
- Twelve-Factor: конфиг только через переменные окружения
- Секреты: никогда в коде, никогда в логах, никогда в ответах API

## Переменные окружения
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/botofarm
SECRET_KEY=
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
LOCK_TTL_SECONDS=300

## Что проверяется на сдаче
- Async стиль (asyncio + asyncpg)
- Архитектура и разделение логики
- Валидация входных данных
- Корректная работа lock/free
- Dependency Injection для сессий БД
- Покрытие тестами не менее 75%
- Docker-compose поднимает всё одной командой
- Alembic миграции
- OAuth2 авторизация
- Пробы: startup, liveness, readiness
- ruff + mypy без ошибок
- Helm чарты для minikube
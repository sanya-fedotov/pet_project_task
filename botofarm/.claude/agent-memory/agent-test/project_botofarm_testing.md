---
name: Botofarm testing infrastructure and known issues
description: Key facts about the botofarm test setup, fixture scopes, and pre-existing bugs that were fixed
type: project
---

The botofarm project uses pytest-asyncio in `asyncio_mode = "auto"` with `asyncio_default_fixture_loop_scope = "session"`.

**Session-scoped PG fixtures vs function-scoped tests — loop mismatch bug**

The `pg_engine` and `pg_db_session` fixtures in `conftest.py` are `scope="session"`, which means asyncpg creates connections on the session event loop. Function-scoped tests default to their own event loops, causing:
  `RuntimeError: Task ... got Future ... attached to a different loop`

**Fix applied:** `tests/api/test_lock_pg.py` uses `pytestmark = pytest.mark.asyncio(loop_scope="session")` to run all PG integration tests on the shared session loop.

**Why:** This matches the session-scoped engine's loop lifetime.

**How to apply:** Any new test file that uses `pg_async_client`, `pg_db_session`, or `pg_engine` fixtures MUST also declare `loop_scope="session"` (either via `pytestmark` or per-test decorator).

---

**Lock/free endpoints require a JSON body**

`POST /api/v1/users/lock` and `POST /api/v1/users/free` accept Pydantic models (`LockUserRequest`, `FreeUsersRequest`) — all fields optional, but FastAPI still requires the body to be present. Sending the request without a body returns 422.

**Fix:** Always pass `json={}` (empty dict) as the minimum body when calling these endpoints in tests.

---

**service.lock_user and service.free_users require filter schemas**

`botfarm_service.lock_user(db, filters: LockUserRequest)` and `botfarm_service.free_users(db, filters: FreeUsersRequest)` both require their filter argument — callers must construct and pass the schema even when no filters are needed.

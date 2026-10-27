# Weekly report backend — Phase 3

FastAPI, SQLAlchemy 2, Pydantic 2, and SQLite foundation. Requires Python 3.11+.
User creation, work-item CRUD, and on-demand weekly reports are implemented. There is no authentication,
scheduler, AI summary generation, or report snapshot storage.

## Setup and run

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
uvicorn app.main:app --reload
```

Application startup creates the tables. Interactive API documentation is available
at `/docs`, with the API schema at `/openapi.json`.

## REST API

| Method | Path | Result |
| --- | --- | --- |
| POST | `/users` | Create user, `201` |
| POST | `/users/{user_id}/work-items` | Create item, `201` |
| GET | `/users/{user_id}/work-items` | List items, `200` |
| GET | `/users/{user_id}/work-items/{item_id}` | Read item, `200` |
| PATCH | `/users/{user_id}/work-items/{item_id}` | Partially update item, `200` |
| DELETE | `/users/{user_id}/work-items/{item_id}` | Delete item, `204` with no body |
| GET | `/users/{user_id}/weekly-report?week_start=YYYY-MM-DD` | Generate weekly report, `200` |

Create a user with `{"name": "Alice"}`. Create an item with, for example:

```json
{
  "title": "Build API",
  "description": "Implement work-item CRUD",
  "category": "Engineering",
  "status": "in_progress",
  "week_start": "2026-09-28"
}
```

The list endpoint accepts optional `week_start`, `category`, and `status` query
parameters, combined with AND. Categories match exactly and case-sensitively after
trimming surrounding whitespace. Week filters must also be Mondays. Results are
ordered by ID ascending, without pagination; an existing user with no matches gets
an empty list. User names need not be unique.

Creating or listing items for an unknown user returns `404`. Reading, updating,
or deleting a missing item or an item belonging to a different user returns the
same `404` response. Invalid request bodies or filters return `422`. PATCH updates
only supplied fields; an empty object is a successful no-op. Ownership and IDs
cannot be changed through request bodies. User scoping is not authentication:
callers can select any user ID in the URL.

### Weekly reports

Request `/users/1/weekly-report?week_start=2026-09-28` to report on that user's
items assigned to that Monday. The required date must be a Monday; missing or
invalid dates return `422`, and unknown users return `404`. Dates whose Sunday
would exceed the supported date range also return `422`.

Reports contain `user_id`, `user_name`, `week_start`, `week_end` (inclusive Sunday),
`total_items`, `completed_count`, `in_progress_count`, `pending_count`,
`completion_percentage`, and `items_by_category`. Category groups are a JSON object
mapping category names to arrays of full work-item responses, ordered by category
and then item ID. Category names remain case-sensitive.

The service queries by both user ID and exact `week_start`, counts statuses, and
groups the matching items in memory. Completion percentage is
`completed_count / total_items * 100`, rounded to two decimal places. Empty weeks
return `200` with zero counts, zero percentage, and `items_by_category: {}`.
Reports reflect current work items on every request; generation makes no database
writes and stores no snapshots.

Configuration via environment variables:

- `DATABASE_URL`: defaults to `sqlite:///./weekly_report.db`; only SQLite is supported.
- `LOG_LEVEL`: defaults to `INFO`.

The parent directory of a configured database file must already exist. Importing
the application does not open or create a database. Startup/shutdown are logged;
no work-item contents are logged.

## Data and validation

Users have an ID, name, and creation timestamp. Work items belong to a user and
have a title, description, category, status, explicit `week_start`, and creation
and update timestamps. Stored timestamps are naive UTC because SQLite does not
preserve timezone information. `updated_at` is maintained for SQLAlchemy updates.

Input schemas trim names, titles, and categories and reject blank values. Names
and titles are limited to 200 characters; categories to 50. Description defaults
to an empty string. Status defaults to `pending`; allowed values are `pending`,
`in_progress`, and `completed`. `week_start` must be a Monday. Partial updates
allow omitted fields but reject explicit nulls and unknown fields. Ownership is
supplied by the user ID in the URL, separately from the item input schema.

Database constraints enforce foreign keys, non-null fields, statuses, and Monday
dates. Text length and whitespace validation are handled by Pydantic; direct SQL
does not enforce those text rules. An index covers `(user_id, week_start)`.

The `get_db` dependency provides one session per request, closes it afterward,
and rolls back on exceptions. Write handlers explicitly commit their changes.
Table creation happens at startup and is suitable for local development; it does
not migrate existing schemas — use Alembic for that. No user-deletion cascade is configured.

## Tests

```sh
python -m pytest -q
```

Each test receives a temporary SQLite file and uses the real application lifespan.
Fixtures provide the application, client, engine, and session without touching the
development database. Tests cover table/index creation, persistence and defaults,
relationships, foreign-key and check constraints, session rollback, schema validation,
CRUD success/error responses, list filters, isolation between users, report grouping
and status counts, week boundaries, empty weeks, percentages, and live report updates.

Foreign-key setup follows the [SQLAlchemy SQLite documentation](https://docs.sqlalchemy.org/en/20/dialects/sqlite.html#foreign-key-support).

## Project layout

```
wrs/
├── app/
│   ├── main.py            # FastAPI application and lifespan
│   ├── models.py          # SQLAlchemy 2 models
│   ├── schemas.py         # Pydantic 2 request/response schemas
│   ├── database.py        # Engine, session, get_db dependency
│   ├── logging_config.py  # LOG_LEVEL-driven logging
│   ├── routers/           # users, work_items, reports
│   └── services/          # report aggregation logic
└── tests/                 # pytest, isolated SQLite per test
```

## License

MIT

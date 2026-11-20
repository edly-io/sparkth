# Test coverage

This guide covers how to measure the test coverage of the backend and frontend unit suites, and records a
baseline.

## Measuring coverage

Run both suites with coverage:

```bash
make test with-coverage=1
```

Or one side at a time:

```bash
make test.backend.pytest with-coverage=1   # pytest-cov, line coverage of sparkth/
make test.frontend.vitest with-coverage=1  # Vitest with the v8 provider
```

Both accept a path in `ARGS` to measure part of the suite, e.g.
`make test.backend.pytest ARGS=sparkth/plugins/slack with-coverage=1`.

What each side measures:

- **Backend**: every module under `sparkth/`, except tests and Alembic migrations (`[tool.coverage.run]` in
  `pyproject.toml`). The terminal report lists the missed lines for each file. Add `--cov-report=html` to
  `ARGS` for a browsable report in `htmlcov/`.
- **Frontend**: every `.ts`/`.tsx` file under `app/`, `core/`, `lib/` and `plugins/`, loaded by a test or not,
  so an untested file counts as uncovered. Test helpers and the generated API types are excluded (`coverage`
  in `frontend/vitest.config.ts`). The HTML report lands in `frontend/coverage/`.

### The `pg` and `wasm` lanes

A plain `pytest` skips the tests marked `pg` (TimescaleDB) and `wasm` (PXC sandbox), so the code they exercise
reads as less covered than it is. To include them, append their runs to the same coverage data:

```bash
uv run pytest --cov
make test.backend.analytics ARGS="--cov --cov-append"
make test.backend.wasm ARGS="--cov --cov-append --cov-report=term-missing"
```

The Playwright E2E suite (`make test.e2e`) and the `sparkth-pxc-xblock` distribution
(`make test.pxc.xblock`) are not measured.

## In CI

The `frontend` and `backend` CI jobs run their suites with coverage and write the total line coverage to the
run's summary page. The backend total excludes the `pg` and `wasm` lanes. No job fails on a coverage
threshold.

Each pull request also records its branch's totals in the Test Coverage section of its description.

## Baseline

Measured on 2026-11-20 against `main`, with line coverage. The backend run excludes the `pg` and `wasm` lanes.

| Suite | Lines covered |
|---|---|
| Backend | 95% (12,803 / 13,544) |
| Frontend | 71% (2,663 / 3,760) |

For the current totals, see the summary page of the latest CI run on `main`, or the Test Coverage section of a
recent pull request.

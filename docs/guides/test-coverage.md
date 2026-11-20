# Test coverage

This guide covers how to measure the test coverage of the backend and frontend unit suites, and records the
current figures.

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

## Current figures

Measured on 2026-11-20 against `main`, with line coverage. The backend run excludes the `pg` and `wasm` lanes.

| Suite | Lines covered |
|---|---|
| Backend | 95% (12,803 / 13,544) |
| Frontend | 71% (2,663 / 3,760) |

### Backend by package

| Package | Lines covered |
|---|---|
| `sparkth/api` | 95% |
| `sparkth/cli` | 93% |
| `sparkth/core` | 96% |
| `sparkth/lib` | 99% |
| `sparkth/llm` | 94% |
| `sparkth/mcp` | 88% |
| `sparkth/rag` | 95% |
| `sparkth/services` | 99% |
| `sparkth/main.py` | 75% |

### Frontend by area

| Area | Lines covered |
|---|---|
| `app/` | 70% |
| `core/` | 81% |
| `lib/` | 100% |

### Plugins

| Plugin | Backend | Frontend |
|---|---|---|
| canvas | 85% | 67% |
| compose | 96% | 70% |
| course_design | 100% | 100% |
| googledrive | 90% | 63% |
| moodle | 99% | 67% |
| openedx | 89% | 67% |
| pxc | 95% | 97% |
| slack | 92% | 30% |

The canvas, course_design, moodle and openedx frontend plugins are a few lines of registration code each, so
their percentages swing on a single line.

Refresh these tables when coverage shifts noticeably, with the commands above.

# AI Tutor Analysis — Test Documentation

> **Scope.** This folder documents the automated test suite for the
> `student_analysis_pipeline` FastAPI backend.  
> It is written for new contributors, QA engineers, and anyone who needs
> to understand *what* is tested, *why*, and *how to run it* locally or
> in CI.

For the current local, GitHub Actions, Grafana Cloud, and OpenShift dev deployment/testing setup, see [`../AI_TUTOR_TESTING_OBSERVABILITY.md`](../AI_TUTOR_TESTING_OBSERVABILITY.md). That overview is the canonical source for cross-repo stage ownership, OpenShift triggers, secrets, resources, and dashboard behavior. This folder focuses on the backend pytest suite itself.

---

## Contents

1. [`01_overview.md`](./01_overview.md) — test suite at a glance (counts, layers, tech stack)
2. [`02_gap_report_2026-04.md`](./02_gap_report_2026-04.md) — gap report done on 2026-04-20 that drove the newest round of test additions
3. [`03_new_tests_added.md`](./03_new_tests_added.md) — inventory of every test added in the 2026-04 pass, mapped to the source it covers
4. [`04_environment_setup.md`](./04_environment_setup.md) — how to set up and run the suite on macOS, Linux, and in CI (including Docker requirements)
5. [`05_manual_testing_workflows.md`](./05_manual_testing_workflows.md) — human click-through runbooks for each dashboard flow, to be run before every release
6. [`06_coverage_roadmap.md`](./06_coverage_roadmap.md) — how to wire `pytest-cov` into the current workflow and reach 90%+ coverage

---

## TL;DR (refreshed 2026-05-08)

| Metric | Before 2026-04 audit | Current (2026-05-08) |
|---|---:|---:|
| Total tests | 104 | **157** |
| Unit tests | 25 | **34** |
| Integration tests | 66 | **96** |
| Live/deployed-environment tests | 13 | **27** |
| Non-live tests run in CI | 91 | **130** |
| Passing rate | 100% | **100%** |
| Files with tests | 18 | **22** |
| **Line coverage (`pytest --cov=app`)** | *not measured* | **98%** (1093 stmts, 22 missed) |

Run everything:

```bash
conda activate oi
# Docker must be running (testcontainers spins up a real Postgres 16)
bash scripts/run_pytest_with_reports.sh
pytest -m "live and (smoke or integration or health or external_service)"  # explicit deployed-environment checks
pytest --cov=app                                                        # local coverage report
```

GitHub Actions runs the non-live backend suite. OpenShift runs only deployed-environment checks after backend image updates, using the marker expression `live and (smoke or integration or health or external_service)`.

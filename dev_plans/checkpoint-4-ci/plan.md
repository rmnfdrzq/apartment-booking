# Implementation Plan: Checkpoint 4 — Continuous Integration (GitHub Actions & GitLab CI)

**Document Path:** `/dev_plans/checkpoint-4-ci/plan.md`  
**Phase:** `feature/checkpoint-4-ci`  
**Milestone:** Checkpoint 4 Delivery (CI workflows, Docker image build in CI, failing/fixed run demonstration)  

---

## 1. Goal

Run the project's checks automatically on every push and pull request (merge request on GitLab), so that a broken change is visible within minutes. By the end of this phase, the repository will have:

1. **Workflow 1 — Build & Unit Tests:** installs the application, runs the full unit/integration test suite, builds the Docker image, and runs the test suite and a health check **inside the built image**.
2. **Workflow 2 — Coverage Gate:** measures test coverage and fails if it drops below a fixed threshold.
3. **Visible results:** a readable summary on every run (tests passed/failed, coverage per file), downloadable reports (JUnit XML, HTML coverage), and status badges in `README.md`.
4. **The same two workflows on GitLab** (`.gitlab-ci.yml`) for the university GitLab instance, with test results shown in GitLab's own test report and coverage widgets.
5. A documented procedure to **demonstrate a failing run** (a deliberately broken test) and the **fixed run**, leaving both workflows green and the application runnable.

---

## 2. Locked Decisions

### Decision 1: Two Separate Workflows on GitHub
- **What:** `.github/workflows/tests.yml` (build, unit tests, Docker image) and `.github/workflows/coverage.yml` (coverage gate), both triggered on `push` and `pull_request`.
- **Why:** The assignment asks for two workflows with distinct purposes; separate files give separate status checks and badges, so a coverage drop and a failing test are reported independently.

### Decision 2: Additional Check = Coverage Threshold (80 %)
- **What:** Measure coverage with `pytest --cov=app` (test failures do not stop the measurement), then `coverage report --fail-under=80` decides the result. Current coverage is 91 % (measured, Section 4).
- **Why:**
  - Coverage is listed in the assignment as an accepted additional check.
  - It passes today without unrelated code changes, while a linter would first require fixing 76 existing findings and reformatting 16 files written by other team members.
  - 80 % leaves headroom for normal development but still catches large untested additions.
  - Each workflow fails only for its own reason: a broken test turns **Build & Unit Tests** red while the **Coverage Gate** stays green, which makes the failure demonstration unambiguous (verified on GitHub).

### Decision 3: Docker Image Built and Exercised in CI
- **What:** The tests workflow runs `docker build`, then (a) `pytest` inside the image and (b) starts a container and polls `/health`.
- **Why:** "Build the Docker image as part of the CI process" is only meaningful if the image is proven to work; running tests in the image also catches files missing from the `Dockerfile` `COPY` list.
- **Note:** The image has no `curl`, so the two demo-script tests are skipped inside the container (expected: all others pass).

### Decision 4: Results Visible Without Opening Logs
- **What:** A small standard-library script `scripts/ci_summary.py` turns JUnit XML and coverage XML into a Markdown table written to the job summary; JUnit XML and HTML coverage are uploaded as artifacts; README badges show the latest status.
- **Why:** No third-party reporting actions (no extra permissions, works on forks); the same script output is readable in any CI.

### Decision 5: Pinned Runtimes and Fast Feedback
- **What:** Python 3.12 (same as the `Dockerfile`), `pip` cache, `concurrency` cancels outdated runs on the same branch, job timeouts of 15 minutes.
- **Why:** CI should test the same Python version that ships in the image, and a stuck job must not block the queue.

### Decision 6: GitLab Mirrors the Same Two Checks in One Pipeline
- **What:** One `.gitlab-ci.yml` with stages `test`, `build`, `quality`: `unit-tests`, `docker-build`, `coverage-check`. JUnit is attached via `artifacts:reports:junit`, coverage via `coverage:` regex and `artifacts:reports:coverage_report` (Cobertura). Pipelines run for branch pushes and merge requests without duplicates (`workflow:rules`).
- **Why:** GitLab runs one pipeline per push; jobs play the role of GitHub's workflows, and GitLab shows test results and coverage natively in the pipeline and merge request UI.
- **Risk note:** `docker-build` uses Docker-in-Docker, which requires a runner that allows privileged containers (Section 5, Risk 2).

### Decision 7: Failure Demonstration on a Branch, Never on `main`
- **What:** The deliberate failure is a one-line change to an assertion in an existing test, committed on the CI branch, followed by a revert commit.
- **Why:** The failed run link must exist for submission, but `main` must stay green and runnable.

---

## 3. What Exists Today

- **Branch:** `feature/checkpoint-4-ci`, created from `main` at `e727a52` (Checkpoint 3 merged).
- **Application:** FastAPI backend + web UI, SQLite persistence, `Dockerfile` (`python:3.12-slim`), `docker-compose.yml` with volume `apartment_data`.
- **Tests:** 165 pytest tests (unit, API integration, UI, end-to-end demo script); `pytest-cov` configured in `pyproject.toml`.
- **CI:** none — no `.github/workflows/`, no `.gitlab-ci.yml`.
- **Linting:** no linter configured.

---

## 4. Verified and Measured Facts

| Metric / Check | Verified State | Source |
| :--- | :--- | :--- |
| **Test suite on `main`** | 165 passed | `pytest` |
| **Line + branch coverage** | 91 % (`app/`) | `pytest --cov=app` |
| **Linter findings (ruff, default + plugins)** | 76 findings, 16 files not formatted | `ruff check`, `ruff format --check` |
| **Docker base image** | `python:3.12-slim` (no `curl`) | `Dockerfile` |
| **Tests copied into image** | Yes (`COPY tests/`) | `Dockerfile` |

---

## 5. Risks and Mitigations

### Risk 1: Flaky End-to-End Test in CI
- **Context:** `tests/test_demo_script.py` starts a real server and needs `bash` and `curl`.
- **Severity:** Medium.
- **Mitigation:** Both are present on GitHub's `ubuntu-latest` and on the GitLab `python:3.12` image; the script picks a free port and cleans up after itself.

### Risk 2: University GitLab Runner Without Privileged Docker
- **Context:** Docker-in-Docker needs `privileged = true` on the runner; shared university runners may not allow it.
- **Severity:** Medium (only the Docker build job is affected).
- **Mitigation:** The job is isolated in its own stage; an alternative Kaniko job (no privileges needed) is documented in the README section for GitLab.

### Risk 3: Coverage Threshold Too Strict
- **Context:** Future features may lower coverage temporarily.
- **Severity:** Low.
- **Mitigation:** Threshold set 11 points below current value; it is one number in each CI file.

### Risk 4: Failure Demo Left in the Codebase
- **Context:** Forgetting to revert the broken test leaves CI red.
- **Severity:** Medium.
- **Mitigation:** The demo is a single, clearly labelled commit, reverted with `git revert`; the final state is checked to be green before merging.

---

## 6. High-Level Implementation Stages

### Stage 1: CI Summary Script
- `scripts/ci_summary.py`: reads JUnit XML and Cobertura coverage XML, prints a Markdown summary; unit tests for it.

### Stage 2: GitHub Workflow 1 — Build & Unit Tests
- `.github/workflows/tests.yml`: checkout, Python 3.12 with pip cache, install, `pytest` with JUnit XML, job summary, upload report; second job builds the Docker image, runs tests inside it and a container health check.

### Stage 3: GitHub Workflow 2 — Coverage Gate
- `.github/workflows/coverage.yml`: `pytest --cov-fail-under=80`, Cobertura XML + HTML report, job summary, artifact upload.

### Stage 4: GitLab CI
- `.gitlab-ci.yml` with `unit-tests`, `docker-build`, `coverage-check`; native JUnit and coverage reports.

### Stage 5: Documentation
- README: CI section with badges, what each workflow checks, where to see results, how to run the same checks locally, GitLab import steps, failure demonstration steps.

### Stage 6: Verification
- Validate workflow syntax (actionlint, YAML parse), run every CI command locally, push the branch, confirm both workflows pass, push a deliberately failing test, confirm the tests workflow fails, revert, confirm both pass again.

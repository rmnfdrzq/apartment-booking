# Implementation Plan: Part 4 — E2E Integration, Demo Script & Checkpoint 1 Delivery

**Document Path:** `/dev_plans/part4-demo/plan.md`  
**Phase:** `feature/part4-demo`  
**User Stories Covered:** **US1–US4** (end-to-end verification of all stories)  
**Target Milestone:** Checkpoint 1 Delivery (tag `checkpoint-1`)  

---

## 1. Goal

Prove, with one command and with copy-pasteable instructions, that the whole system works as a running, persistent, documented backend. By the end of this phase, the project will have:

1. `scripts/demo.sh` — an executable end-to-end demo that runs the complete user journey from the roadmap (steps 1–10), asserts every HTTP status code and key response value, prints colorized PASS/FAIL lines, and exits non-zero on the first failure.
2. Automated **persistence verification**: the script stops and restarts the server and checks that the data is still there.
3. Automated **Swagger/OpenAPI verification**: `/docs` is reachable and every user-story endpoint is documented.
4. A working **manual cURL walkthrough** in `README.md` (Option 2), verified by actually running it.
5. An automated **e2e test** that runs the demo script inside `pytest`, so the demo can never silently break.
6. A **Checkpoint 1 sign-off**: every grading criterion mapped to concrete, verified evidence; roadmap updated; release tag ready.

---

## 2. Locked Decisions

### Decision 1: The Demo Script Manages Its Own Server and Database by Default
- **What:** By default `scripts/demo.sh` starts `uvicorn` on a free local port with a fresh database in a temporary directory, runs the journey, restarts the server for the persistence check, and cleans everything up on exit (`trap`). With `BASE_URL=http://127.0.0.1:8000 ./scripts/demo.sh` it runs against an already running server instead and skips the restart step.
- **Why:**
  - Roadmap step 10 (server restart) is impossible if the script does not own the server process.
  - Reproducible: the result does not depend on data already in `./data/apartments.db`, and demo data never pollutes it.
  - The evaluator needs only one command.

### Decision 2: Dates Relative to Today
- **What:** All demo dates are computed at runtime relative to the current date (e.g. check-in today + 30 days).
- **Why:** Fixed dates go stale. Once they are in the past, "active booking" rules change (e.g. an apartment with only finished bookings can be deleted), and the demo would start failing on its own.

### Decision 3: Portable Bash, No Extra Tools
- **What:** Bash 3.2 compatible (default on macOS), dependencies limited to `curl` and the project's own Python (`.venv/bin/python` if present, else `python3`). Python is used for JSON field extraction, date arithmetic, and picking a free port.
- **Why:**
  - The team develops on macOS (bash 3.2, BSD `date`), the course environment may be Linux (GNU `date`); `date -d` vs `date -v` differ, `jq` may not be installed.
  - Python is already a hard requirement of the project.

### Decision 4: Assert, Don't Just Print
- **What:** Each step checks the expected HTTP status code and key fields (e.g. `total_price`, `status`, search result contents). The script uses `set -euo pipefail`, prints a summary, and exits with code `1` on the first failed assertion (with the response body shown).
- **Why:** A demo that only prints JSON can "pass" while the system is broken. Exit codes also make it usable in CI and in `pytest`.

### Decision 5: Readable Output for Presenting
- **What:** Numbered steps matching the roadmap, one line per check (`✔`/`✘`), colors only when the output is a terminal and `NO_COLOR` is not set.
- **Why:** The script is presented live at the checkpoint; colors must not corrupt logs or the e2e test output.

### Decision 6: E2E Test Runs the Real Script
- **What:** `tests/test_demo_script.py` executes `scripts/demo.sh` as a subprocess and asserts exit code `0`. It is skipped automatically if `bash` or `curl` are not available.
- **Why:** The demo is part of the deliverable; running it in the test suite catches API changes that would break it.

### Decision 7: Release Tag After Merge
- **What:** The `checkpoint-1` tag is created on `main` after `feature/part4-demo` is merged, not on the feature branch.
- **Why:** Matches the team git workflow in `roadmap.md`: the tag must point at the stable, reviewed code that is graded.

---

## 3. What Exists Today

- **Branch:** `feature/part4-demo`, created from `main` at `33e3311` (Part 3 merged via PR #2).
- **Merged on `main`:** Parts 0–3 — all four user stories (US1–US4) are implemented and tested.
- **Documentation:**
  - `README.md` already describes `scripts/demo.sh` (Option 1), a manual cURL walkthrough (Option 2), persistence verification (Section 11), and a Checkpoint 1 checklist (Section 14).
  - `roadmap.md`: Phases 1–3 marked done, Phase 4 open.
- **Missing:** `scripts/` directory and `demo.sh`, e2e test for the demo, `checkpoint-1` tag.
- **Documentation gaps found:**
  - README Option 1 tells the user to start the server manually, which makes the restart step impossible to automate.
  - The manual walkthrough uses fixed November 2026 dates, which will become past dates during the course.
  - README Section 12 still reports "33 tests" and "97% coverage".

---

## 4. Verified and Measured Facts

| Metric / Check | Verified State | Source |
| :--- | :--- | :--- |
| **Active Git Branch** | `feature/part4-demo` (from `main` @ `33e3311`) | `git branch --show-current` |
| **Existing Test Suite** | 152 passed, 98% coverage | `pytest` |
| **Implemented Endpoints** | `/health`, 6 × `/apartments…` (incl. `/search`), 5 × `/bookings…` | `/openapi.json` |
| **Persistence** | Data survives a `uvicorn` restart on a file database | Manual run during Part 1 and Part 3 |
| **Runtime (verification env)** | Linux, bash 5, Python 3.13.16, curl present | `bash --version`, `python3 --version` |
| **Team Runtime** | macOS arm64, Python 3.14 (bash 3.2 by default) | Part 0 plan |

---

## 5. Risks and Mitigations

### Risk 1: Demo Breaks Because of Stale Dates
- **Context:** Fixed dates become past dates; active-booking rules then behave differently.
- **Severity:** High (demo fails during the presentation).
- **Mitigation:** Relative dates in the script (Decision 2); README walkthrough moved to dates far in the future with a note to use future dates.

### Risk 2: Port Already in Use / Leftover Server Processes
- **Context:** Port 8000 may be taken (e.g. by the developer's own server); a failed run could leave `uvicorn` running.
- **Severity:** Medium.
- **Mitigation:** Pick a free port automatically; `trap` on `EXIT`/`INT`/`TERM` kills the server and removes the temporary directory; wait for `/health` with a timeout and print the server log on failure.

### Risk 3: Demo Pollutes the Real Database
- **Context:** Running the demo against `./data/apartments.db` adds demo records to the developer's data.
- **Severity:** Medium.
- **Mitigation:** Temporary database via `DATABASE_URL` in self-managed mode (Decision 1).

### Risk 4: Platform Differences (macOS vs Linux)
- **Context:** bash 3.2, BSD vs GNU tools, missing `jq`.
- **Severity:** Medium.
- **Mitigation:** Decision 3; avoid bash 4 features (associative arrays, `mapfile`, `${var,,}`); check with `bash -n` and a strict shell linter where available.

### Risk 5: Demo Passes While the System Is Wrong
- **Context:** Printing responses without checking them hides regressions.
- **Severity:** Medium.
- **Mitigation:** Assertions on status codes and key fields (Decision 4); e2e test (Decision 6).

### Risk 6: README Walkthrough Out of Sync with the API
- **Context:** Manual commands may reference wrong fields, codes, or expected outputs.
- **Severity:** Medium.
- **Mitigation:** Execute the walkthrough commands against a live server during verification and fix every mismatch.

---

## 6. High-Level Implementation Stages

### Stage 1: Demo Script (Step 4.1 Option 1, Step 4.2, Step 4.3)
- Create `scripts/demo.sh` (executable) with helpers for requests, assertions, JSON field extraction, and date arithmetic.
- Implement the journey: health check → host adds 2 apartments → guest searches → guest books apartment 1 → overlapping booking rejected (`409`) → second guest books apartment 2 (`201`) → booking update and apartment transfer (`PUT`) → cancellation → search shows apartment 1 free again → server restart and persistence check.
- Add Swagger/OpenAPI checks (`/docs` → `200`, every user-story path present in `/openapi.json`).
- Self-managed and external (`BASE_URL`) modes; cleanup via `trap`.

### Stage 2: E2E Test
- Create `tests/test_demo_script.py` running the script as a subprocess (skipped if `bash`/`curl` are missing).

### Stage 3: Documentation (Step 4.1 Option 2)
- README Option 1: one-command usage, both modes, what the script checks.
- README Option 2: run the walkthrough against a live server; move dates into the future; fix any mismatch with real responses.
- README Section 12: remove stale test numbers.

### Stage 4: Checkpoint 1 Sign-Off (Step 4.4)
- Re-verify every criterion in README Section 14 and link concrete evidence.
- Mark Phase 4 done in `roadmap.md`.

### Stage 5: Verification, Senior Review & Git
- Run `bash -n`, shell linter, Python linter/formatter, and the full `pytest` suite; run the demo in both modes.
- Perform the 11-point senior code review; fix all Critical/High/Medium issues.
- Commit on `feature/part4-demo` and push; after merge, tag `main` as `checkpoint-1`.

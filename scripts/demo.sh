#!/usr/bin/env bash
#
# End-to-end demo of the Apartment Booking API (Checkpoint 1).
#
# Runs the complete user journey for all four user stories and checks every
# HTTP status code and key response value. Stops with exit code 1 on the first
# failed check.
#
# Usage:
#   ./scripts/demo.sh                                   # starts its own server + temporary database
#   BASE_URL=http://127.0.0.1:8000 ./scripts/demo.sh    # uses a server that is already running
#
# Requirements: bash 3.2+, curl, and the project's Python dependencies
# (pip install -r requirements.txt). Works on macOS and Linux.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [ "${1:-}" = "-h" ] || [ "${1:-}" = "--help" ]; then
    sed -n '3,14p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
    exit 0
fi

# --- settings ------------------------------------------------------------------

if [ -n "${PYTHON:-}" ]; then
    PY="$PYTHON"
elif [ -x "$ROOT_DIR/.venv/bin/python" ]; then
    PY="$ROOT_DIR/.venv/bin/python"
else
    PY="python3"
fi

EXTERNAL_SERVER="no"
if [ -n "${BASE_URL:-}" ]; then
    EXTERNAL_SERVER="yes"
    BASE_URL="${BASE_URL%/}"
fi

if [ -t 1 ] && [ -z "${NO_COLOR:-}" ]; then
    GREEN=$'\033[32m' RED=$'\033[31m' YELLOW=$'\033[33m' BOLD=$'\033[1m' DIM=$'\033[2m' RESET=$'\033[0m'
else
    GREEN="" RED="" YELLOW="" BOLD="" DIM="" RESET=""
fi

TMP_DIR="$(mktemp -d "${TMPDIR:-/tmp}/apartment-demo.XXXXXX")"
RESPONSE_FILE="$TMP_DIR/response.json"
SERVER_LOG="$TMP_DIR/server.log"
DB_FILE="$TMP_DIR/demo.db"
SERVER_PID=""
CHECKS=0
RESP_STATUS=""
RESP_BODY=""

# --- output helpers --------------------------------------------------------------

step() { printf '\n%s%s%s\n' "$BOLD" "$1" "$RESET"; }
info() { printf '  %s%s%s\n' "$DIM" "$1" "$RESET"; }
pass() {
    CHECKS=$((CHECKS + 1))
    printf '  %s✔%s %s\n' "$GREEN" "$RESET" "$1"
}
fail() {
    printf '  %s✘ %s%s\n' "$RED" "$1" "$RESET" >&2
    if [ -n "$RESP_BODY" ]; then
        printf '    %sLast response (HTTP %s): %s%s\n' "$DIM" "$RESP_STATUS" "$RESP_BODY" "$RESET" >&2
    fi
    printf '\n%sDemo FAILED after %d passed checks.%s\n' "$RED" "$CHECKS" "$RESET" >&2
    exit 1
}

# --- python helpers (JSON, dates, ports) -----------------------------------------

# json EXPR [ARG...]: evaluate a Python expression on the last JSON response.
# The response is available as `d`, extra arguments as `a` (a list of strings).
# Values from the server are only ever passed as data, never inserted into EXPR.
json() {
    printf '%s' "$RESP_BODY" | "$PY" -I -c '
import json, sys
d = json.load(sys.stdin)
v = eval(sys.argv[1], {"__builtins__": {"all": all, "any": any, "len": len}, "d": d, "a": sys.argv[2:]})
print(json.dumps(v) if isinstance(v, (bool, list, dict)) or v is None else v)
' "$@"
}

# ISO date N days from today, e.g. day 30 -> 2026-11-24
day() {
    "$PY" -I -c 'import datetime, sys; print(datetime.date.today() + datetime.timedelta(days=int(sys.argv[1])))' "$1"
}

free_port() {
    "$PY" -I -c 'import socket; s = socket.socket(); s.bind(("127.0.0.1", 0)); print(s.getsockname()[1]); s.close()'
}

# --- HTTP helpers ------------------------------------------------------------------

# request METHOD PATH [JSON_BODY] -> sets RESP_STATUS and RESP_BODY
request() {
    local method="$1" path="$2" body="${3:-}"
    : >"$RESPONSE_FILE"
    if [ -n "$body" ]; then
        RESP_STATUS="$(curl -s -o "$RESPONSE_FILE" -w '%{http_code}' --max-time 10 -X "$method" \
            -H 'Content-Type: application/json' --data "$body" "$BASE_URL$path")" || RESP_STATUS="000"
    else
        RESP_STATUS="$(curl -s -o "$RESPONSE_FILE" -w '%{http_code}' --max-time 10 -X "$method" \
            "$BASE_URL$path")" || RESP_STATUS="000"
    fi
    RESP_BODY="$(cat "$RESPONSE_FILE")"
}

# expect_status CODE "description"
expect_status() {
    if [ "$RESP_STATUS" = "$1" ]; then
        pass "$2 → $1"
    else
        fail "$2: expected HTTP $1, got $RESP_STATUS"
    fi
}

# check "description" ACTUAL EXPECTED
check() {
    if [ "$2" = "$3" ]; then
        pass "$1"
    else
        fail "$1: expected '$3', got '$2'"
    fi
}

booking_body() { # apartment_id guest_name email start end
    printf '{"apartment_id": "%s", "guest_name": "%s", "guest_email": "%s", "start_date": "%s", "end_date": "%s"}' \
        "$1" "$2" "$3" "$4" "$5"
}

# --- server lifecycle --------------------------------------------------------------

start_server() {
    DATABASE_URL="sqlite:///$DB_FILE" "$PY" -m uvicorn app.main:app --host 127.0.0.1 --port "$PORT" \
        >>"$SERVER_LOG" 2>&1 &
    SERVER_PID=$!
    local _
    for _ in $(seq 1 50); do
        if curl -s -o /dev/null --max-time 1 "$BASE_URL/health"; then
            return 0
        fi
        if ! kill -0 "$SERVER_PID" 2>/dev/null; then
            break
        fi
        sleep 0.2
    done
    printf '%sServer did not start. Log:%s\n' "$RED" "$RESET" >&2
    tail -n 20 "$SERVER_LOG" >&2
    printf '\nHint: install dependencies with  pip install -r requirements.txt\n' >&2
    exit 1
}

stop_server() {
    if [ -n "$SERVER_PID" ]; then
        kill "$SERVER_PID" 2>/dev/null || true
        wait "$SERVER_PID" 2>/dev/null || true
        SERVER_PID=""
    fi
}

cleanup() {
    stop_server
    rm -rf "$TMP_DIR"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

# --- preflight ---------------------------------------------------------------------

command -v curl >/dev/null 2>&1 || {
    echo "curl is required but was not found." >&2
    exit 1
}
command -v "$PY" >/dev/null 2>&1 || {
    echo "Python was not found ($PY). Set PYTHON=/path/to/python." >&2
    exit 1
}

printf '%sApartment Booking API — Checkpoint 1 end-to-end demo%s\n' "$BOLD" "$RESET"
if [ "$EXTERNAL_SERVER" = "yes" ]; then
    info "Using running server at $BASE_URL (restart step will be skipped)"
else
    PORT="$(free_port)"
    BASE_URL="http://127.0.0.1:$PORT"
    info "Starting server at $BASE_URL with a temporary database"
    start_server
fi

# Dates relative to today, so the demo never goes stale.
D30="$(day 30)"
D31="$(day 31)"
D32="$(day 32)"
D34="$(day 34)"
D36="$(day 36)"
D37="$(day 37)"
D39="$(day 39)"
SEARCH="/apartments/search?start_date=$D30&end_date=$D34"
info "Guest travel window: $D30 → $D34 (4 nights)"

# --- 1. health ---------------------------------------------------------------------

step "1. Health check"
request GET /health
expect_status 200 "GET /health"
check "service reports status ok" "$(json 'd["status"]')" "ok"

# --- 2. host manages apartments (US1) ----------------------------------------------

step "2. Host adds and maintains apartments (US1)"
request POST /apartments '{"title": "Sunny Alpine Studio", "description": "Studio with mountain views", "address": "Piazza Walther 4, Bolzano", "price_per_night": 100.0, "max_guests": 2}'
expect_status 201 "POST /apartments (Sunny Alpine Studio)"
APT1="$(json 'd["id"]')"

request POST /apartments '{"title": "City Loft", "address": "Via Museo 12, Bolzano", "price_per_night": 90.0, "max_guests": 3}'
expect_status 201 "POST /apartments (City Loft)"
APT2="$(json 'd["id"]')"

request POST /apartments '{"title": "Bad listing", "address": "Nowhere", "price_per_night": -5}'
expect_status 422 "POST /apartments with negative price is rejected"

request PUT "/apartments/$APT1" '{"price_per_night": 120.0}'
expect_status 200 "PUT /apartments/{id} (price 100 → 120)"
check "price updated" "$(json 'd["price_per_night"]')" "120.0"

request GET /apartments
expect_status 200 "GET /apartments"
check "both apartments are listed" "$(json 'all(i in [x["id"] for x in d] for i in a)' "$APT1" "$APT2")" "true"

request GET "/apartments/$APT1"
expect_status 200 "GET /apartments/{id}"

# --- 3. guest searches (US3) -------------------------------------------------------

step "3. Guest searches for available apartments (US3)"
request GET "$SEARCH"
expect_status 200 "GET /apartments/search $D30 → $D34"
check "both apartments are available" "$(json 'all(i in [x["id"] for x in d] for i in a)' "$APT1" "$APT2")" "true"

request GET "/apartments/search?start_date=$D34&end_date=$D30"
expect_status 400 "search with check-out before check-in is rejected"

# --- 4. guest books apartment 1 (US2) ----------------------------------------------

step "4. Elena books Sunny Alpine Studio (US2)"
request POST /bookings "$(booking_body "$APT1" "Elena Rossi" "elena@example.com" "$D30" "$D34")"
expect_status 201 "POST /bookings $D30 → $D34"
ELENA="$(json 'd["id"]')"
check "total price = 4 nights × 120" "$(json 'd["total_price"]')" "480.0"
check "booking is CONFIRMED" "$(json 'd["status"]')" "CONFIRMED"

request GET "$SEARCH"
check "Sunny Alpine Studio no longer shows up in search" "$(json 'a[0] in [x["id"] for x in d]' "$APT1")" "false"

# --- 5. overlap prevention (US4) ---------------------------------------------------

step "5. Overlapping bookings are prevented (US4)"
request POST /bookings "$(booking_body "$APT1" "Bob Smith" "bob@example.com" "$D32" "$D36")"
expect_status 409 "Bob books Sunny Alpine Studio $D32 → $D36 (overlaps Elena)"

request POST /bookings "$(booking_body "$APT1" "Charlie Brown" "charlie@example.com" "$D34" "$D37")"
expect_status 201 "Charlie checks in on Elena's check-out day $D34 (same-day turnaround)"
CHARLIE="$(json 'd["id"]')"

# --- 6. second guest books apartment 2 ---------------------------------------------

step "6. Bob books City Loft instead"
request POST /bookings "$(booking_body "$APT2" "Bob Smith" "bob@example.com" "$D32" "$D36")"
expect_status 201 "POST /bookings City Loft $D32 → $D36"
BOB="$(json 'd["id"]')"
check "total price = 4 nights × 90" "$(json 'd["total_price"]')" "360.0"

# --- 7. update and transfer (US2) --------------------------------------------------

step "7. Guests change their bookings (US2)"
request PUT "/bookings/$BOB" "{\"start_date\": \"$D31\"}"
expect_status 200 "Bob arrives one day earlier ($D31 → $D36)"
check "price recalculated = 5 nights × 90" "$(json 'd["total_price"]')" "450.0"

request PUT "/bookings/$CHARLIE" "{\"apartment_id\": \"$APT2\"}"
expect_status 409 "Charlie cannot move to City Loft on dates overlapping Bob"

request PUT "/bookings/$CHARLIE" "{\"apartment_id\": \"$APT2\", \"start_date\": \"$D36\", \"end_date\": \"$D39\"}"
expect_status 200 "Charlie moves to City Loft $D36 → $D39"
check "booking now belongs to City Loft" "$(json 'd["apartment_id"]')" "$APT2"
check "price recalculated = 3 nights × 90" "$(json 'd["total_price"]')" "270.0"

# --- 8. cancel (US2) ---------------------------------------------------------------

step "8. Elena cancels her booking (US2)"
request POST "/bookings/$ELENA/cancel"
expect_status 200 "POST /bookings/{id}/cancel"
check "booking is CANCELLED" "$(json 'd["status"]')" "CANCELLED"

# --- 9. search again (US3) ---------------------------------------------------------

step "9. Search again: Sunny Alpine Studio is free again (US3)"
request GET "$SEARCH"
expect_status 200 "GET /apartments/search $D30 → $D34"
check "Sunny Alpine Studio is available" "$(json 'a[0] in [x["id"] for x in d]' "$APT1")" "true"
check "City Loft is not available (Bob's stay)" "$(json 'a[0] in [x["id"] for x in d]' "$APT2")" "false"

# --- 10. persistence ---------------------------------------------------------------

step "10. Data survives a server restart"
if [ "$EXTERNAL_SERVER" = "yes" ]; then
    printf '  %s– skipped: the server is not managed by this script (see README, section 11)%s\n' "$YELLOW" "$RESET"
else
    stop_server
    check "server stopped" "$(curl -s -o /dev/null -w '%{http_code}' --max-time 2 "$BASE_URL/health" || true)" "000"
    if [ -s "$DB_FILE" ]; then pass "SQLite database file exists on disk"; else fail "database file $DB_FILE is missing"; fi
    start_server
    pass "server restarted"
    request GET "/bookings/$BOB"
    expect_status 200 "Bob's booking still exists"
    check "Bob's changed dates were kept" "$(json 'd["start_date"] + " → " + d["end_date"]')" "$D31 → $D36"
    request GET "/bookings/$ELENA"
    check "Elena's cancellation was kept" "$(json 'd["status"]')" "CANCELLED"
    request GET "/apartments/$APT1"
    check "updated apartment price was kept" "$(json 'd["price_per_night"]')" "120.0"
fi

# --- 11. API documentation ---------------------------------------------------------

step "11. API is documented without a GUI (Swagger / OpenAPI)"
request GET /docs
expect_status 200 "GET /docs (Swagger UI)"
request GET /openapi.json
expect_status 200 "GET /openapi.json"
check "all user-story endpoints are documented" "$(json '
all(p in d["paths"] for p in [
    "/apartments", "/apartments/search", "/apartments/{apartment_id}",
    "/bookings", "/bookings/{booking_id}", "/bookings/{booking_id}/cancel",
])')" "true"

# --- 12. removing apartments (US1) -------------------------------------------------

step "12. Host removes apartments (US1)"
request DELETE "/apartments/$APT2"
expect_status 409 "City Loft cannot be removed while Bob and Charlie have active stays"
request POST "/bookings/$BOB/cancel"
expect_status 200 "Bob cancels"
request POST "/bookings/$CHARLIE/cancel"
expect_status 200 "Charlie cancels"
request DELETE "/apartments/$APT2"
expect_status 204 "DELETE City Loft"
request DELETE "/apartments/$APT1"
expect_status 204 "DELETE Sunny Alpine Studio"
request GET "/apartments/$APT1"
expect_status 404 "removed apartment is gone"

printf '\n%s✔ All %d checks passed.%s\n' "$GREEN" "$CHECKS" "$RESET"

#!/usr/bin/env bash
# Verify a scaffolded repo the same way every time:
#   bash <skill>/scripts/verify_scaffold.sh <repo-dir> [--docker]
# 1. leftovers from the templates (placeholders, variant markers, insecure keys)
# 2. config syntax (YAML, JSON, compose)
# 3. `just check` — everything CI runs
# 4. with --docker and a reachable daemon: build, start, and probe the hardened stack
# Prints a summary; exit code is non-zero if anything failed.
set -uo pipefail

repo="${1:?usage: verify_scaffold.sh <repo-dir> [--docker]}"
docker_mode="${2:-}"
here="$(cd "$(dirname "$0")" && pwd)"
# Python comes from uv, never from whatever `python3` is (or isn't) on the PATH.
command -v uv >/dev/null || { echo "uv is required (https://docs.astral.sh/uv/getting-started/installation/)" >&2; exit 2; }
py() { uv run --no-project --quiet --python ">=3.11" "$@"; }
cd "$repo" || exit 2

failures=()
step() { echo; echo "=== $1"; }
fail() { echo "FAIL: $1"; failures+=("$1"); }

step "Template leftovers"
leftovers=$(grep -rnE '<(project|Project|PG_MAJOR|NODE_LTS|PYTHON|UV|PNPM|DEBIAN|TRIVY|TIMEZONE|UNAUTHENTICATED_STATUS|OPENAPI_EXPORT_COMMAND|DEV_PORT|SUPERVISOR|owner|API_LIBRARY|UI_LIBRARY|SCHEMA_DIR|LICENSE_ID|FRONTEND|SHA|DIGEST|VERSION|ACTIONLINT|ZIZMOR|JUST|CONDUCT_EMAIL|PLUGIN_VERSION|DATE|RELEASES|CONTRIBUTIONS|ADRS|README_[A-Z_]+)>|\[(NINJA|DRF|DOCS|VUE|REACT|TAILWIND|RELEASE_PLEASE|MANUAL_RELEASES|EXTERNAL|TEAM_ONLY|BACKEND_DE|BACKEND_EN|ADRS|ARM64|NO_DOCS|/)\]|Template notes for the skill' \
  --exclude-dir=node_modules --exclude-dir=.venv --exclude-dir=.git . || true)
[ -n "$leftovers" ] && { echo "$leftovers"; fail "template placeholders left"; } || echo "none"
if grep -rn "django-insecure" backend/config/settings.py; then fail "generated insecure SECRET_KEY still in settings.py"; fi
for f in justfile SECURITY.md CODE_OF_CONDUCT.md CONTRIBUTING.md backend/uv.lock frontend/pnpm-lock.yaml frontend/openapi.json frontend/src/api/schema.d.ts AGENTS.md README.md .env.example; do
  [ -f "$f" ] || fail "missing $f"
done
[ -f frontend/package-lock.json ] && fail "package-lock.json exists (pnpm only)"
# Every project has a LICENSE file except proprietary ones ("UNLICENSED" in package.json).
[ -f LICENSE ] || grep -q '"UNLICENSED"' frontend/package.json || fail "missing LICENSE"

step "Config syntax"
uv run --no-project --quiet --python ">=3.11" --with pyyaml - <<'PY' || fail "YAML/JSON syntax"
import json, pathlib, sys
try:
    import yaml
except ImportError:
    yaml = None
bad = False
for p in [*pathlib.Path(".github/workflows").glob("*.y*ml"), pathlib.Path(".github/dependabot.yml")]:
    if yaml and p.exists():
        try: yaml.safe_load(p.read_text())
        except Exception as e: print(p, e); bad = True
for p in ["frontend/package.json", "frontend/openapi.json"]:
    try: json.loads(pathlib.Path(p).read_text())
    except Exception as e: print(p, e); bad = True
print("ok" if not bad else "errors"); sys.exit(1 if bad else 0)
PY
if command -v docker >/dev/null; then
  docker compose config -q && echo "compose.yml ok" || fail "docker compose config"
  docker compose -f compose.dev.yml config -q && echo "compose.dev.yml ok" || fail "compose.dev.yml config"
else
  echo "docker CLI missing: compose files not validated"
fi

step "House defaults checklist"
# Every auto item of references/checklist.md must pass in a fresh scaffold (--new: also the
# items for new projects only).
py "$here/check_repo.py" . --new || fail "house defaults checklist"

step "just check (= CI checks)"
[ -f .env ] || cp .env.example .env
# The same recipe CI runs; natively on SQLite. Needs just (e.g. `uv tool install rust-just`).
if command -v just >/dev/null; then
  just check || fail "just check"
else
  fail "just is not installed: uv tool install rust-just"
fi

if [ "$docker_mode" = "--docker" ]; then
  step "Docker stack"
  if ! docker info >/dev/null 2>&1; then
    fail "--docker requested but no Docker daemon reachable"
  else
    env_backup=$(mktemp); cp .env "$env_backup"
    secret=$(py -c "import secrets; print(secrets.token_urlsafe(50))")
    sed -i "s#^SECRET_KEY=.*#SECRET_KEY=$secret#; s#^ADMIN_PASSWORD=.*#ADMIN_PASSWORD=verify-$secret#; s#^DB_PASSWORD=.*#DB_PASSWORD=verify-db-pw#" .env
    # compose.yml runs the registry image; verify the image built from this checkout.
    export APP_IMAGE="verify-scaffold-local:latest"
    if docker build -t "$APP_IMAGE" . && docker compose up -d; then
      ok=false
      for _ in $(seq 1 60); do
        docker compose exec -T app python /usr/local/bin/healthcheck >/dev/null 2>&1 && { ok=true; break; }
        sleep 2
      done
      $ok || fail "app did not become healthy"
      sleep 15
      # The same probes as CI's smoke test (docker/smoke-test in the image).
      docker compose exec -T app sh /usr/local/bin/smoke-test app || fail "smoke test app"
      docker compose exec -T worker sh /usr/local/bin/smoke-test worker || fail "smoke test worker"
      docker compose logs app worker | tail -60
    else
      fail "docker compose up"
    fi
    docker compose down -v
    cp "$env_backup" .env; rm -f "$env_backup"
  fi
fi

echo
if [ ${#failures[@]} -eq 0 ]; then
  echo "ALL CHECKS PASSED"
else
  printf 'FAILED (%d):\n' "${#failures[@]}"; printf '  - %s\n' "${failures[@]}"
  exit 1
fi

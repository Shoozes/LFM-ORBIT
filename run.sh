#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$REPO_ROOT/source/backend"
FRONTEND_DIR="$REPO_ROOT/source/frontend"
BACKEND_VENV_SUFFIX="linux"
case "$(uname -s 2>/dev/null || printf '')" in
    Darwin*)
        BACKEND_VENV_SUFFIX="macos"
        ;;
    MINGW*|MSYS*|CYGWIN*)
        BACKEND_VENV_SUFFIX="windows"
        ;;
esac
BACKEND_VENV_DIR="${UV_PROJECT_ENVIRONMENT:-$BACKEND_DIR/.venv-$BACKEND_VENV_SUFFIX}"
export UV_PROJECT_ENVIRONMENT="$BACKEND_VENV_DIR"
RUNTIME_DIR="$REPO_ROOT/runtime-data"
LEGACY_BACKEND_RUNTIME_DIR="$BACKEND_DIR/runtime-data"
MODEL_DIR="$RUNTIME_DIR/models/lfm2.5-vlm-450m"
MODEL_FILE="$MODEL_DIR/LFM2.5-VL-450M-Q4_0.gguf"
MODEL_MANIFEST="$MODEL_DIR/model_manifest.json"
TOOLS_DIR="$RUNTIME_DIR/tools"
UV_BOOTSTRAP_BIN="$TOOLS_DIR/uv/bin/uv"
UV_VENV_DIR="$TOOLS_DIR/uv-venv"
UV_VENV_BIN="$UV_VENV_DIR/bin/uv"
UV_VENV_WIN_BIN="$UV_VENV_DIR/Scripts/uv.exe"
DEFAULT_MODEL_REPO_ID="Shoozes/lfm2.5-450m-vl-orbit-satellite"
DEFAULT_MODEL_REVISION="main"
SIMSAT_DIR="$BACKEND_DIR/SimSat-main"
UV_CMD=""
PYTHON_CMD=""
NODE_CMD=""
NPM_CMD=""
NPX_CMD=""

INSTALL=false
INSTALL_ONLY=false
RUN_APP_ONLY=false
CLEAN=false
VERIFY=false
FETCH_MODEL=false

show_usage() {
    cat <<'EOF'
LFM Orbit launcher

Usage:
  ./run.sh                 Open the interactive menu
  ./run.sh --install       Install locked deps, fetch the trained GGUF, then start backend + frontend
  ./run.sh --install-only  Advanced/dev: install locked deps without starting the app
  ./run.sh --run           Advanced/dev: start backend + frontend from existing deps
  ./run.sh --clean         Clear mutable runtime stores for a cold start
  ./run.sh --verify        Install deps and run backend, frontend, and E2E checks
EOF
}

load_dotenv() {
    local env_path="$REPO_ROOT/.env"
    if [[ ! -f "$env_path" ]]; then
        return
    fi

    while IFS= read -r raw_line || [[ -n "$raw_line" ]]; do
        local line="${raw_line#"${raw_line%%[![:space:]]*}"}"
        line="${line%"${line##*[![:space:]]}"}"
        [[ -z "$line" || "${line:0:1}" == "#" || "$line" != *=* ]] && continue

        local key="${line%%=*}"
        local value="${line#*=}"
        key="${key%"${key##*[![:space:]]}"}"
        value="${value#"${value%%[![:space:]]*}"}"
        value="${value%"${value##*[![:space:]]}"}"

        [[ "$key" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] || continue
        if [[ ${#value} -ge 2 ]]; then
            local first="${value:0:1}"
            local last="${value: -1}"
            if [[ "$first" == "$last" && ( "$first" == "'" || "$first" == '"' ) ]]; then
                value="${value:1:${#value}-2}"
            fi
        fi
        export "$key=$value"
    done < "$env_path"

    echo "[i] Loaded environment overrides from .env"
}

load_dotenv

set_production_runtime_defaults() {
    export OBSERVATION_PROVIDER="${OBSERVATION_PROVIDER:-simsat_sentinel}"
    export SIMSAT_ENABLED="${SIMSAT_ENABLED:-true}"
    export SIMSAT_DATA_SOURCE="${SIMSAT_DATA_SOURCE:-sentinel}"
    export DISABLE_EXTERNAL_APIS="${DISABLE_EXTERNAL_APIS:-true}"
}

set_production_runtime_defaults

require_command() {
    local name="$1"
    local hint="$2"
    if ! command -v "$name" >/dev/null 2>&1; then
        echo "[!] $name not found. $hint" >&2
        exit 1
    fi
}

resolve_command() {
    local candidate
    for candidate in "$@"; do
        if command -v "$candidate" >/dev/null 2>&1; then
            command -v "$candidate"
            return 0
        fi
    done
    return 1
}

is_wsl() {
    [[ -r /proc/version ]] && grep -qiE "microsoft|wsl" /proc/version
}

find_existing_uv() {
    if command -v uv >/dev/null 2>&1; then
        command -v uv
        return 0
    fi

    if [[ -x "$UV_BOOTSTRAP_BIN" ]]; then
        printf '%s\n' "$UV_BOOTSTRAP_BIN"
        return 0
    fi

    if [[ -x "$UV_VENV_BIN" ]]; then
        printf '%s\n' "$UV_VENV_BIN"
        return 0
    fi

    if [[ -x "$UV_VENV_WIN_BIN" ]]; then
        printf '%s\n' "$UV_VENV_WIN_BIN"
        return 0
    fi

    if ! is_wsl && command -v uv.exe >/dev/null 2>&1; then
        command -v uv.exe
        return 0
    fi

    return 1
}

ensure_uv() {
    if [[ -n "$UV_CMD" ]]; then
        return
    fi

    if UV_CMD="$(find_existing_uv)"; then
        return
    fi

    if [[ "${LFM_ORBIT_SKIP_UV_BOOTSTRAP:-}" == "1" ]]; then
        echo "[!] uv not found. Install uv or unset LFM_ORBIT_SKIP_UV_BOOTSTRAP so the launcher can bootstrap repo-local uv." >&2
        exit 1
    fi

    ensure_python
    echo "[*] uv not found; bootstrapping repo-local uv into runtime-data/tools/uv-venv..."
    mkdir -p "$TOOLS_DIR"
    "$PYTHON_CMD" -m venv "$UV_VENV_DIR"

    local venv_python="$UV_VENV_DIR/bin/python"
    if [[ ! -x "$venv_python" && -x "$UV_VENV_DIR/Scripts/python.exe" ]]; then
        venv_python="$UV_VENV_DIR/Scripts/python.exe"
    fi
    if [[ ! -x "$venv_python" ]]; then
        echo "[!] uv bootstrap virtualenv did not contain a Python executable." >&2
        exit 1
    fi

    "$venv_python" -m pip install --upgrade pip uv

    if UV_CMD="$(find_existing_uv)"; then
        return
    fi

    echo "[!] uv bootstrap did not produce a usable uv executable under $UV_VENV_DIR" >&2
    exit 1
}

ensure_python() {
    if [[ -n "$PYTHON_CMD" ]]; then
        return
    fi

    if PYTHON_CMD="$(resolve_command python python3 python.exe)"; then
        if "$PYTHON_CMD" - <<'PY'
import sys
raise SystemExit(0 if sys.version_info >= (3, 10) else 1)
PY
        then
            return
        fi
        echo "[!] Python 3.10+ is required. Found an older Python at $PYTHON_CMD." >&2
        exit 1
    fi

    echo "[!] Python 3.10+ not found. Install Python before running the launcher." >&2
    exit 1
}

ensure_node() {
    if [[ -n "$NODE_CMD" && -n "$NPM_CMD" && -n "$NPX_CMD" ]]; then
        return
    fi

    if ! NODE_CMD="$(resolve_command node node.exe)"; then
        echo "[!] Node.js 20.19.0 or newer 22.12.0+ not found. Install Node.js; .nvmrc pins 20.19.0." >&2
        if is_wsl; then
            echo "    In WSL, install Node inside WSL or ensure Windows node.exe is visible on PATH." >&2
        fi
        exit 1
    fi
    if ! NPM_CMD="$(resolve_command npm npm.cmd)"; then
        echo "[!] npm not found. Install Node.js 20.19.0 or newer 22.12.0+; npm ships with Node.js." >&2
        exit 1
    fi
    if ! NPX_CMD="$(resolve_command npx npx.cmd)"; then
        echo "[!] npx not found. Install Node.js 20.19.0 or newer 22.12.0+; npx ships with npm." >&2
        exit 1
    fi

    if ! "$NODE_CMD" -e "const [maj,min,patch]=process.versions.node.split('.').map(Number); const ok=(maj===20 && (min>19 || (min===19 && patch>=0))) || (maj>22) || (maj===22 && min>=12); process.exit(ok?0:1);"; then
        echo "[!] Unsupported Node.js version $("$NODE_CMD" --version). Use Node.js 20.19.0, or Node.js 22.12.0 or newer." >&2
        exit 1
    fi
    if ! "$NPM_CMD" --version >/dev/null 2>&1; then
        echo "[!] npm is present but failed to run. Reinstall Node.js or repair PATH so npm matches the active Node runtime." >&2
        exit 1
    fi
}

can_attempt_model_runtime_install() {
    local kernel_name
    kernel_name="$(uname -s 2>/dev/null || printf '')"
    if [[ "$kernel_name" == Linux* ]] && ! resolve_command cc gcc clang x86_64-linux-gnu-gcc >/dev/null; then
        return 1
    fi
    return 0
}

write_simsat_status() {
    if [[ -d "$SIMSAT_DIR" ]]; then
        echo "[i] SimSat vendored source is present."
    else
        echo "[i] SimSat vendored source is missing. Orbit stays on the SimSat/local path; direct providers require explicit OBSERVATION_PROVIDER overrides."
    fi
}

install_backend_deps() {
    ensure_uv
    if is_wsl && [[ "$BACKEND_DIR" == /mnt/* ]]; then
        export UV_LINK_MODE="${UV_LINK_MODE:-copy}"
    fi
    echo "[*] Syncing backend dependencies from uv.lock..."
    local sync_args=(sync --extra dev --locked)
    local include_model_runtime=false
    case "${LFM_ORBIT_INSTALL_MODEL_RUNTIME:-}" in
        1|true|TRUE|yes|YES|on|ON)
            include_model_runtime=true
            ;;
    esac
    if [[ "$FETCH_MODEL" == true ]]; then
        include_model_runtime=true
    fi
    if [[ -f "$MODEL_FILE" ]]; then
        include_model_runtime=true
    fi
    if [[ "$include_model_runtime" == true ]]; then
        if can_attempt_model_runtime_install; then
            sync_args+=(--extra model)
            echo "[i] Attempting llama-cpp model runtime install for GGUF inference."
        else
            include_model_runtime=false
            echo "[i] Skipping llama-cpp model runtime install because no Linux C/C++ compiler was found."
            echo "    Install build-essential, gcc/g++, or clang, then rerun with LFM_ORBIT_INSTALL_MODEL_RUNTIME=1 if local GGUF inference is required."
        fi
    fi

    (
        cd "$BACKEND_DIR"
        if ! "$UV_CMD" "${sync_args[@]}"; then
            if [[ "$include_model_runtime" == true ]]; then
                echo "[!] llama-cpp model runtime failed to install. Retrying core backend install without local GGUF runtime." >&2
                "$UV_CMD" sync --extra dev --locked
            else
                exit 1
            fi
        fi
    )
}

install_frontend_deps() {
    ensure_node
    echo "[*] Installing frontend dependencies from package-lock.json..."
    (
        cd "$FRONTEND_DIR"
        "$NPM_CMD" ci
    )
}

ensure_trained_model() {
    if [[ "$FETCH_MODEL" != true ]]; then
        echo "[i] Skipping trained GGUF fetch. Use --fetch-model for production/hackathon runs; fallback analysis is development-only."
        return
    fi

    ensure_python
    mkdir -p "$MODEL_DIR"

    local min_size_bytes=1048576

    if [[ -n "${LFM_MODEL_URL:-}" ]]; then
        local needs_download=false
        if [[ -f "$MODEL_FILE" ]]; then
            local file_size
            file_size=$(stat -c%s "$MODEL_FILE" 2>/dev/null || stat -f%z "$MODEL_FILE")
            if [[ "$file_size" -ge "$min_size_bytes" ]]; then
                echo "[i] Trained Orbit GGUF already present."
                return
            fi
            echo "[i] Existing GGUF file is incomplete ($file_size bytes). Re-downloading..."
            needs_download=true
        else
            needs_download=true
        fi

        if [[ "$needs_download" == true ]]; then
            echo "[*] Fetching trained Orbit GGUF from LFM_MODEL_URL..."
            echo "    Source: $LFM_MODEL_URL"
            echo "    Target: $MODEL_FILE"
            "$PYTHON_CMD" -c "import urllib.request, sys; print('Downloading trained Orbit model...', flush=True); urllib.request.urlretrieve(sys.argv[1], sys.argv[2])" "$LFM_MODEL_URL" "$MODEL_FILE"
        fi
    else
        local model_repo_id="${LFM_MODEL_REPO_ID:-${CANOPY_SENTINEL_MODEL_REPO_ID:-$DEFAULT_MODEL_REPO_ID}}"
        local model_revision="${LFM_MODEL_REVISION:-${CANOPY_SENTINEL_MODEL_REVISION:-$DEFAULT_MODEL_REVISION}}"

        if "$PYTHON_CMD" - "$MODEL_MANIFEST" "$MODEL_FILE" "$model_repo_id" "$model_revision" "$min_size_bytes" <<'PY'
import json
import sys
from pathlib import Path

manifest_path, model_path, expected_repo, expected_revision, min_size = sys.argv[1:6]
model = Path(model_path)
manifest = Path(manifest_path)
if not model.exists() or model.stat().st_size < int(min_size) or not manifest.exists():
    raise SystemExit(1)
try:
    payload = json.loads(manifest.read_text(encoding="utf-8"))
except Exception:
    raise SystemExit(1)
source = payload.get("source") if isinstance(payload.get("source"), dict) else {}
repo_id = str(source.get("repo_id") or payload.get("repo_id") or "")
revision = str(source.get("revision") or payload.get("revision") or "")
raise SystemExit(0 if repo_id == expected_repo and revision == expected_revision else 1)
PY
        then
            echo "[i] Trained Orbit GGUF already present from $model_repo_id@$model_revision."
            return
        fi

        echo "[*] Fetching trained Orbit GGUF bundle..."
        echo "    Repo: $model_repo_id@$model_revision"
        echo "    Target: $MODEL_DIR"
        (
            cd "$BACKEND_DIR"
            "$UV_CMD" run --no-sync python scripts/fetch_satellite_model.py --repo-id "$model_repo_id" --revision "$model_revision" --force
        )
    fi

    if [[ ! -f "$MODEL_FILE" ]]; then
        echo "[!] Expected GGUF file was not written: $MODEL_FILE" >&2
        exit 1
    fi
    local file_size
    file_size=$(stat -c%s "$MODEL_FILE" 2>/dev/null || stat -f%z "$MODEL_FILE")
    if [[ "$file_size" -lt "$min_size_bytes" ]]; then
        echo "[!] Downloaded GGUF file is too small ($file_size bytes)." >&2
        exit 1
    fi
    echo "[+] Trained Orbit GGUF model ready."
}

install_deps() {
    install_backend_deps
    write_simsat_status
    install_frontend_deps
    ensure_trained_model
    echo "[+] Install/repair complete."
}

install_playwright_browser() {
    ensure_node
    echo "[*] Ensuring Playwright Chromium is installed..."
    (
        cd "$FRONTEND_DIR"
        "$NPX_CMD" playwright install chromium
    )
}

run_verify() {
    echo "[*] Running full repo verification..."
    install_backend_deps
    install_frontend_deps
    install_playwright_browser

    (
        cd "$BACKEND_DIR"
        echo "[*] Backend tests..."
        "$UV_CMD" run --no-sync pytest -q
    )

    (
        cd "$FRONTEND_DIR"
        echo "[*] Frontend typecheck..."
        "$NPM_CMD" run lint
        echo "[*] Frontend production build..."
        "$NPM_CMD" run build
        echo "[*] Playwright E2E..."
        "$NPM_CMD" run test:e2e
    )

    echo "[+] Verification complete."
}

run_app() {
    ensure_node
    echo "[*] Starting LFM Orbit..."
    write_simsat_status

    if [[ ! -f "$MODEL_FILE" ]]; then
        echo "[!] Trained GGUF model not found. Run ./run.sh --install for the production/hackathon path; continuing with development fallback behavior."
    fi

    echo "[*] Launching backend..."
    local backend_pid
    if UV_CMD="$(find_existing_uv)"; then
        (
            cd "$BACKEND_DIR"
            "$UV_CMD" run --no-sync uvicorn api.main:app --host 127.0.0.1 --port 8000
        ) &
        backend_pid=$!
    elif [[ -x "$BACKEND_VENV_DIR/bin/python" ]]; then
        (
            cd "$BACKEND_DIR"
            "$BACKEND_VENV_DIR/bin/python" -m uvicorn api.main:app --host 127.0.0.1 --port 8000
        ) &
        backend_pid=$!
    elif [[ -x "$BACKEND_VENV_DIR/Scripts/python.exe" ]]; then
        (
            cd "$BACKEND_DIR"
            "$BACKEND_VENV_DIR/Scripts/python.exe" -m uvicorn api.main:app --host 127.0.0.1 --port 8000
        ) &
        backend_pid=$!
    else
        echo "[!] Backend runtime is not installed. Run ./run.sh --install first." >&2
        exit 1
    fi

    trap 'kill "$backend_pid" 2>/dev/null || true' EXIT

    echo "[*] Waiting for backend health check..."
    local ready=false
    for i in $(seq 1 30); do
        if curl -fsS http://127.0.0.1:8000/api/health >/dev/null 2>&1; then
            ready=true
            break
        fi
        echo "    Waiting... (${i}s)"
        sleep 1
    done

    if [[ "$ready" != true ]]; then
        echo "[!] Backend did not become healthy within 30 seconds." >&2
        exit 1
    fi

    echo "[+] Backend ready on http://127.0.0.1:8000"
    echo "[*] Launching frontend on http://127.0.0.1:5173 ..."
    (
        cd "$FRONTEND_DIR"
        "$NPM_CMD" run dev -- --host 127.0.0.1
    )
}

clean_data() {
    echo "[*] Cleaning runtime data for a cold start..."
    local paths_to_remove=(
        "$RUNTIME_DIR/agent_bus.sqlite"
        "$RUNTIME_DIR/dtn_queue.sqlite"
        "$RUNTIME_DIR/demo_metrics_summary.json"
        "$RUNTIME_DIR/api_cache.sqlite"
        "$LEGACY_BACKEND_RUNTIME_DIR/api_cache.sqlite"
    )

    for path in "${paths_to_remove[@]}"; do
        if [[ -f "$path" ]]; then
            rm -f "$path"
            echo "    Removed $path"
        fi
    done

    local observation_store_dir="$BACKEND_DIR/assets/observation_store"
    if [[ -d "$observation_store_dir" ]]; then
        find "$observation_store_dir" -maxdepth 1 -type f -name '*.json' -print -delete
    fi

    echo "[+] Clean complete."
}

show_banner() {
    if [[ -f "$REPO_ROOT/docs/banner.txt" ]]; then
        cat "$REPO_ROOT/docs/banner.txt"
    else
        echo "LFM Orbit"
    fi
}

run_menu() {
    while true; do
        clear
        show_banner
        echo "======================================"
        echo "              LFM ORBIT               "
        echo "======================================"
        echo "1. Install/Repair + Fetch trained Orbit GGUF -> Run"
        echo "2. Verify (backend + frontend + E2E)"
        echo "3. Clean (cold-start runtime reset)"
        echo "4. Exit"
        echo "======================================"

        read -r -p "Select an option: " choice
        case "$choice" in
            1)
                FETCH_MODEL=true
                install_deps
                run_app
                exit 0
                ;;
            2)
                run_verify
                exit 0
                ;;
            3)
                clean_data
                sleep 2
                ;;
            4)
                exit 0
                ;;
            *)
                echo "Invalid choice"
                sleep 1
                ;;
        esac
    done
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --install)
            INSTALL=true
            ;;
        --install-only)
            INSTALL_ONLY=true
            ;;
        --run)
            RUN_APP_ONLY=true
            ;;
        --clean)
            CLEAN=true
            ;;
        --verify)
            VERIFY=true
            ;;
        --fetch-model)
            FETCH_MODEL=true
            ;;
        -h|--help)
            show_usage
            exit 0
            ;;
        *)
            echo "[!] Unknown argument: $1" >&2
            exit 1
            ;;
    esac
    shift
done

if [[ "$CLEAN" == true ]]; then
    clean_data
fi

if [[ "$INSTALL_ONLY" == true ]]; then
    install_deps
    exit 0
fi

if [[ "$VERIFY" == true ]]; then
    run_verify
    exit 0
fi

if [[ "$INSTALL" == true ]]; then
    FETCH_MODEL=true
    install_deps
    run_app
    exit 0
fi

if [[ "$RUN_APP_ONLY" == true ]]; then
    run_app
    exit 0
fi

if [[ "$CLEAN" == true ]]; then
    exit 0
fi

run_menu

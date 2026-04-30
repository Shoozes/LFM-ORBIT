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
DEFAULT_MODEL_REPO_ID="Shoozes/lfm2.5-450m-vl-orbit-satellite"
DEFAULT_MODEL_REVISION="main"
SIMSAT_DIR="$BACKEND_DIR/SimSat-main"
UV_CMD=""
PYTHON_CMD=""

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
  ./run.sh --install       Install locked deps, then start backend + frontend
  ./run.sh --install-only  Install locked deps without starting the app
  ./run.sh --run           Start backend + frontend from existing deps
  ./run.sh --clean         Clear mutable runtime stores for a cold start
  ./run.sh --verify        Install deps and run backend, frontend, and E2E checks
  ./run.sh --install --fetch-model
                           Also fetch the trained Orbit GGUF bundle before startup
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
        echo "[!] uv not found. Install uv from https://docs.astral.sh/uv/ to honor source/backend/uv.lock." >&2
        exit 1
    fi

    require_command curl "Install curl or install uv manually from https://docs.astral.sh/uv/."
    echo "[*] uv not found; bootstrapping repo-local uv into runtime-data/tools/uv..."
    mkdir -p "$TOOLS_DIR/uv/bin"
    curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR="$TOOLS_DIR/uv/bin" sh

    if [[ ! -x "$UV_BOOTSTRAP_BIN" ]]; then
        echo "[!] uv bootstrap did not produce $UV_BOOTSTRAP_BIN" >&2
        exit 1
    fi
    UV_CMD="$UV_BOOTSTRAP_BIN"
}

ensure_python() {
    if [[ -n "$PYTHON_CMD" ]]; then
        return
    fi

    if PYTHON_CMD="$(resolve_command python python3 python.exe)"; then
        return
    fi

    echo "[!] Python 3.12+ not found. Install Python before fetching the optional GGUF model." >&2
    exit 1
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
        echo "[i] SimSat vendored source is missing. Orbit will still start with Sentinel/NASA/local fallback paths."
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
            echo "[i] Attempting optional llama-cpp model runtime install."
        else
            include_model_runtime=false
            echo "[i] Skipping optional llama-cpp model runtime install because no Linux C/C++ compiler was found."
            echo "    Install build-essential, gcc/g++, or clang, then rerun with LFM_ORBIT_INSTALL_MODEL_RUNTIME=1 if local GGUF inference is required."
        fi
    fi

    (
        cd "$BACKEND_DIR"
        if ! "$UV_CMD" "${sync_args[@]}"; then
            if [[ "$include_model_runtime" == true ]]; then
                echo "[!] Optional llama-cpp model runtime failed to install. Retrying core backend install without model runtime." >&2
                "$UV_CMD" sync --extra dev --locked
            else
                exit 1
            fi
        fi
    )
}

install_frontend_deps() {
    require_command npm "Install Node.js using the version pinned in .nvmrc."
    echo "[*] Installing frontend dependencies from package-lock.json..."
    (
        cd "$FRONTEND_DIR"
        npm ci
    )
}

ensure_optional_model() {
    if [[ "$FETCH_MODEL" != true ]]; then
        echo "[i] Skipping optional GGUF model download. Orbit still boots with the local fallback analysis path."
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
                echo "[i] Optional GGUF model already present."
                return
            fi
            echo "[i] Existing GGUF file is incomplete ($file_size bytes). Re-downloading..."
            needs_download=true
        else
            needs_download=true
        fi

        if [[ "$needs_download" == true ]]; then
            echo "[*] Fetching optional GGUF model from LFM_MODEL_URL..."
            echo "    Source: $LFM_MODEL_URL"
            echo "    Target: $MODEL_FILE"
            "$PYTHON_CMD" -c "import urllib.request, sys; print('Downloading optional model...', flush=True); urllib.request.urlretrieve(sys.argv[1], sys.argv[2])" "$LFM_MODEL_URL" "$MODEL_FILE"
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
    echo "[+] Optional trained GGUF model ready."
}

install_deps() {
    install_backend_deps
    write_simsat_status
    install_frontend_deps
    ensure_optional_model
    echo "[+] Install/repair complete."
}

install_playwright_browser() {
    require_command npm "Install Node.js using the version pinned in .nvmrc."
    echo "[*] Ensuring Playwright Chromium is installed..."
    (
        cd "$FRONTEND_DIR"
        npx playwright install chromium
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
        npm run lint
        echo "[*] Frontend production build..."
        npm run build
        echo "[*] Playwright E2E..."
        npm run test:e2e
    )

    echo "[+] Verification complete."
}

run_app() {
    require_command npm "Install Node.js using the version pinned in .nvmrc."
    echo "[*] Starting LFM Orbit..."
    write_simsat_status

    if [[ ! -f "$MODEL_FILE" ]]; then
        echo "[i] Optional GGUF model not found. Satellite-side reasoning will stay on safe fallback behavior."
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
        npm run dev -- --host 127.0.0.1
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
        echo "1. Install/Repair -> Run"
        echo "2. Install/Repair + Fetch optional GGUF model -> Run"
        echo "3. Install/Repair only"
        echo "4. Run"
        echo "5. Verify (backend + frontend + E2E)"
        echo "6. Clean (cold-start runtime reset)"
        echo "7. Exit"
        echo "======================================"

        read -r -p "Select an option: " choice
        case "$choice" in
            1)
                install_deps
                run_app
                exit 0
                ;;
            2)
                FETCH_MODEL=true
                install_deps
                run_app
                exit 0
                ;;
            3)
                install_deps
                exit 0
                ;;
            4)
                run_app
                exit 0
                ;;
            5)
                run_verify
                exit 0
                ;;
            6)
                clean_data
                sleep 2
                ;;
            7)
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

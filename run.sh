#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$REPO_ROOT/source/backend"
FRONTEND_DIR="$REPO_ROOT/source/frontend"
RUNTIME_DIR="$REPO_ROOT/runtime-data"
LEGACY_BACKEND_RUNTIME_DIR="$BACKEND_DIR/runtime-data"
MODEL_DIR="$RUNTIME_DIR/models/lfm2.5-vlm-450m"
MODEL_FILE="$MODEL_DIR/LFM2.5-VL-450M-Q4_0.gguf"
SIMSAT_DIR="$BACKEND_DIR/SimSat-main"

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
                           Also fetch the optional GGUF model before startup
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

write_simsat_status() {
    if [[ -d "$SIMSAT_DIR" ]]; then
        echo "[i] SimSat vendored source is present."
    else
        echo "[i] SimSat vendored source is missing. Orbit will still start with Sentinel/NASA/local fallback paths."
    fi
}

install_backend_deps() {
    require_command uv "Install uv from https://docs.astral.sh/uv/ to honor source/backend/uv.lock."
    echo "[*] Syncing backend dependencies from uv.lock..."
    (
        cd "$BACKEND_DIR"
        uv sync --extra dev --locked
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

    require_command python "Install Python 3.12 to fetch the optional GGUF model."
    mkdir -p "$MODEL_DIR"

    local model_url="${LFM_MODEL_URL:-https://huggingface.co/LiquidAI/LFM2.5-VL-450M-GGUF/resolve/main/LFM2.5-VL-450M-Q4_0.gguf?download=true}"
    local min_size_bytes=1048576
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
        echo "[*] Fetching optional GGUF model..."
        echo "    Source: $model_url"
        echo "    Target: $MODEL_FILE"
        python -c "import urllib.request, sys; print('Downloading optional model...', flush=True); urllib.request.urlretrieve(sys.argv[1], sys.argv[2])" "$model_url" "$MODEL_FILE"
        local file_size
        file_size=$(stat -c%s "$MODEL_FILE" 2>/dev/null || stat -f%z "$MODEL_FILE")
        if [[ "$file_size" -lt "$min_size_bytes" ]]; then
            echo "[!] Downloaded GGUF file is too small ($file_size bytes)." >&2
            exit 1
        fi
        echo "[+] Optional GGUF model ready."
    fi
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
        uv run --no-sync pytest -q
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
    if command -v uv >/dev/null 2>&1; then
        (
            cd "$BACKEND_DIR"
            uv run --no-sync uvicorn api.main:app --host 127.0.0.1 --port 8000
        ) &
        backend_pid=$!
    elif [[ -x "$BACKEND_DIR/.venv/bin/python" ]]; then
        (
            cd "$BACKEND_DIR"
            "$BACKEND_DIR/.venv/bin/python" -m uvicorn api.main:app --host 127.0.0.1 --port 8000
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

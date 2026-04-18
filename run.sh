#!/usr/bin/env bash
set -e

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_ROOT"

install_deps() {
    echo -e "\033[0;36m[*] Installing backend dependencies...\033[0m"
    cd "$REPO_ROOT/source/backend"
    if command -v uv &> /dev/null; then
        echo -e "\033[0;37m    Using uv...\033[0m"
        uv sync
    else
        echo -e "\033[0;37m    uv not found, using pip...\033[0m"
        pip install -e ".[dev]"
    fi

    echo -e "\033[0;36m[*] Vendoring SimSat...\033[0m"
    SIMSAT_DIR="$REPO_ROOT/source/backend/SimSat-main"
    if [ ! -d "$SIMSAT_DIR" ]; then
        echo -e "\033[0;37m    Downloading SimSat from GitHub...\033[0m"
        ZIP_PATH="$REPO_ROOT/source/backend/simsat.zip"
        curl -L "https://github.com/DPhi-Space/SimSat/archive/refs/heads/main.zip" -o "$ZIP_PATH"
        echo -e "\033[0;37m    Extracting SimSat...\033[0m"
        unzip -q -o "$ZIP_PATH" -d "$REPO_ROOT/source/backend"
        rm -f "$ZIP_PATH"
        echo -e "\033[0;37m    SimSat vendored successfully.\033[0m"
    else
        echo -e "\033[0;37m    SimSat already present.\033[0m"
    fi

    echo -e "\033[0;36m[*] Installing frontend dependencies (npm)...\033[0m"
    cd "$REPO_ROOT/source/frontend"
    npm install

    echo -e "\033[0;36m[*] Fetching LFM2.5 VLM 450m model...\033[0m"
    MODEL_DIR="$REPO_ROOT/runtime-data/models/lfm2.5-vlm-450m"
    MODEL_FILE="$MODEL_DIR/LFM2.5-VL-450M-Q4_0.gguf"
    MODEL_URL="${LFM_MODEL_URL:-https://huggingface.co/LiquidAI/LFM2.5-VL-450M-GGUF/resolve/main/LFM2.5-VL-450M-Q4_0.gguf?download=true}"
    MIN_SIZE_BYTES=1048576  # 1 MB sanity check

    mkdir -p "$MODEL_DIR"

    NEEDS_DOWNLOAD=false
    if [ -f "$MODEL_FILE" ]; then
        FILE_SIZE=$(stat -c%s "$MODEL_FILE" 2>/dev/null || stat -f%z "$MODEL_FILE" 2>/dev/null || echo 0)
        if [ "$FILE_SIZE" -ge "$MIN_SIZE_BYTES" ]; then
            SIZE_MB=$(echo "scale=1; $FILE_SIZE / 1048576" | bc 2>/dev/null || echo "$FILE_SIZE bytes")
            echo -e "\033[0;37m    Model already present and valid (${SIZE_MB} MB). Skipping download.\033[0m"
        else
            echo -e "\033[0;33m    Model file found but appears incomplete ($FILE_SIZE bytes). Re-downloading...\033[0m"
            NEEDS_DOWNLOAD=true
        fi
    else
        NEEDS_DOWNLOAD=true
    fi

    if [ "$NEEDS_DOWNLOAD" = true ]; then
        echo -e "\033[0;37m    Downloading from: $MODEL_URL\033[0m"
        echo -e "\033[0;37m    Destination: $MODEL_FILE\033[0m"
        if python -c "import urllib.request, sys; print('Downloading model...', flush=True); urllib.request.urlretrieve(sys.argv[1], sys.argv[2])" "$MODEL_URL" "$MODEL_FILE"; then
            FILE_SIZE=$(stat -c%s "$MODEL_FILE" 2>/dev/null || stat -f%z "$MODEL_FILE" 2>/dev/null || echo 0)
            if [ "$FILE_SIZE" -lt "$MIN_SIZE_BYTES" ]; then
                echo -e "\033[0;31m[!] Downloaded file is too small ($FILE_SIZE bytes). Download may be incomplete.\033[0m"
                echo -e "\033[0;31m[!] Recovery steps:\033[0m"
                echo "      1. Check your internet connection."
                echo "      2. Set LFM_MODEL_URL to a valid URL and re-run install."
                echo "      3. Or manually place LFM2.5-VL-450M-Q4_0.gguf in: $MODEL_DIR"
                exit 1
            fi
            SIZE_MB=$(echo "scale=1; $FILE_SIZE / 1048576" | bc 2>/dev/null || echo "$FILE_SIZE bytes")
            echo -e "\033[0;32m    Model downloaded successfully (${SIZE_MB} MB).\033[0m"
        else
            echo -e "\033[0;31m[!] Model download failed.\033[0m"
            echo -e "\033[0;31m[!] Recovery steps:\033[0m"
            echo "      1. Check your internet connection (required only at install time)."
            echo "      2. Override the URL: export LFM_MODEL_URL='<url>' && bash run.sh"
            echo "      3. Or manually place LFM2.5-VL-450M-Q4_0.gguf in: $MODEL_DIR"
            exit 1
        fi
    fi

    echo -e "\033[0;32m[+] Install complete. Transitioning to Run Phase...\033[0m"
    run_app
}

run_app() {
    echo -e "\033[0;36m[*] Starting LFM Orbit...\033[0m"

    SIMSAT_DIR="$REPO_ROOT/source/backend/SimSat-main"
    if [ -d "$SIMSAT_DIR" ] && command -v docker &> /dev/null; then
        echo -e "\033[0;36m[*] Launching SimSat (docker compose up)...\033[0m"
        cd "$SIMSAT_DIR"
        docker compose up -d || echo -e "\033[0;33m[!] Failed to start SimSat. Docker may not be running. (Backend will fallback automatically)\033[0m"
    elif [ -d "$SIMSAT_DIR" ]; then
        echo -e "\033[0;37m[i] Skipping SimSat integration -> Docker not found. Backend will seamlessly use NASA/Mock fallback.\033[0m"
    fi

    cd "$REPO_ROOT/source/backend"
    
    if command -v uv &> /dev/null; then
        echo -e "\033[0;36m[*] Launching FastAPI Backend (uv)...\033[0m"
        uv run uvicorn api.main:app --port 8000 &
    else
        echo -e "\033[0;36m[*] Launching FastAPI Backend (uvicorn)...\033[0m"
        uvicorn api.main:app --port 8000 &
    fi
    BACKEND_PID=$!

    echo -e "\033[0;36m[*] Waiting for backend to be ready...\033[0m"
    MAX_WAIT=30
    READY=false
    for ((i=1; i<=MAX_WAIT; i++)); do
        if curl -s http://127.0.0.1:8000/api/health > /dev/null; then
            READY=true
            break
        fi
        echo -e "\033[0;37m    Waiting... (${i}s)\033[0m"
        sleep 1
    done

    if [ "$READY" = false ]; then
        echo -e "\033[0;31m[!] Backend did not start within ${MAX_WAIT}s.\033[0m"
        kill $BACKEND_PID 2>/dev/null || true
        exit 1
    fi

    echo -e "\033[0;32m[+] Backend ready. Launching React Frontend...\033[0m"
    cd "$REPO_ROOT/source/frontend"
    npm run dev || true

    # Cleanup background process on exit
    kill $BACKEND_PID 2>/dev/null || true
}

clean_data() {
    echo -e "\033[0;33m[*] Cleaning runtime data for a cold start...\033[0m"
    BUS_PATH="$REPO_ROOT/runtime-data/agent_bus.sqlite"
    if [ -f "$BUS_PATH" ]; then
        rm -f "$BUS_PATH"
        echo -e "\033[0;37m    Deleted agent_bus.sqlite\033[0m"
    fi
    echo -e "\033[0;32m[+] Clean complete.\033[0m"
    sleep 2
}

show_banner() {
    if [ -f "$REPO_ROOT/docs/banner.txt" ]; then
        echo -e "\033[0;36m$(cat "$REPO_ROOT/docs/banner.txt")\033[0m"
    else
        echo -e "\033[0;36mLFM Orbit\033[0m"
    fi
}

while true; do
    clear
    show_banner
    echo -e "\033[0;33m======================================\033[0m"
    echo -e "\033[0;32m              LFM ORBIT               \033[0m"
    echo -e "\033[0;33m======================================\033[0m"
    echo "1. Install/Repair (fetches models) -> Run"
    echo "2. Run (if already installed)"
    echo "3. Clean (deletes runtime data for cold start)"
    echo "4. Exit"
    echo -e "\033[0;33m======================================\033[0m"
    
    read -p "Select an option: " choice
    case $choice in
        1) install_deps; exit 0 ;;
        2) run_app; exit 0 ;;
        3) clean_data ;;
        4) exit 0 ;;
        *) echo -e "\033[0;31mInvalid choice\033[0m"; sleep 1 ;;
    esac
done
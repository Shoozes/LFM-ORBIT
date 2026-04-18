$ErrorActionPreference = "Stop"
$RepoRoot = $PSScriptRoot
Set-Location -LiteralPath $RepoRoot

function Install-Deps {
    Write-Host "[*] Installing backend dependencies..." -ForegroundColor Cyan
    Push-Location "source\backend"
    try {
        $uvAvailable = Get-Command uv -ErrorAction SilentlyContinue
        if ($uvAvailable) {
            Write-Host "    Using uv..." -ForegroundColor Gray
            uv sync
        } else {
            Write-Host "    uv not found, using pip..." -ForegroundColor Gray
            pip install -e ".[dev]"
        }
    } catch {
        Write-Host "[!] Failed to install backend dependencies." -ForegroundColor Red
    }
    Write-Host "[*] Vendoring SimSat..." -ForegroundColor Cyan
    $simSatDir = "$RepoRoot\source\backend\SimSat-main"
    if (-not (Test-Path $simSatDir)) {
        Write-Host "    Downloading SimSat from GitHub..." -ForegroundColor Gray
        $zipPath = "$RepoRoot\source\backend\simsat.zip"
        Invoke-WebRequest -Uri "https://github.com/DPhi-Space/SimSat/archive/refs/heads/main.zip" -OutFile $zipPath
        Write-Host "    Extracting SimSat..." -ForegroundColor Gray
        Expand-Archive -Path $zipPath -DestinationPath "$RepoRoot\source\backend" -Force
        Remove-Item $zipPath
        Write-Host "    SimSat vendored successfully." -ForegroundColor Gray
    } else {
        Write-Host "    SimSat already present." -ForegroundColor Gray
    }

    Pop-Location

    Write-Host "[*] Installing frontend dependencies (npm)..." -ForegroundColor Cyan
    Push-Location "source\frontend"
    try {
        npm install
    } catch {
        Write-Host "[!] Failed to run npm. Make sure Node.js is installed." -ForegroundColor Red
    }
    Pop-Location

    Write-Host "[*] Fetching LFM2.5 VLM 450m model..." -ForegroundColor Cyan
    $modelDir = "$RepoRoot\runtime-data\models\lfm2.5-vlm-450m"
    $modelFile = "$modelDir\LFM2.5-VL-450M-Q4_0.gguf"
    $modelUrl = $env:LFM_MODEL_URL
    if (-not $modelUrl) {
        $modelUrl = "https://huggingface.co/LiquidAI/LFM2.5-VL-450M-GGUF/resolve/main/LFM2.5-VL-450M-Q4_0.gguf?download=true"
    }
    $minSizeBytes = 1MB

    New-Item -ItemType Directory -Force -Path $modelDir | Out-Null

    $needsDownload = $false
    if (Test-Path $modelFile) {
        $fileSize = (Get-Item $modelFile).Length
        if ($fileSize -ge $minSizeBytes) {
            Write-Host "    Model already present and valid ($([Math]::Round($fileSize / 1MB, 1)) MB). Skipping download." -ForegroundColor Gray
        } else {
            Write-Host "    Model file found but appears incomplete ($fileSize bytes). Re-downloading..." -ForegroundColor Yellow
            $needsDownload = $true
        }
    } else {
        $needsDownload = $true
    }

    if ($needsDownload) {
        Write-Host "    Downloading from: $modelUrl" -ForegroundColor Gray
        Write-Host "    Destination: $modelFile" -ForegroundColor Gray
        try {
            # Use python to download for reliability and better progress handling
            python -c "import urllib.request, sys; print('Downloading model...', flush=True); urllib.request.urlretrieve(sys.argv[1], sys.argv[2])" $modelUrl $modelFile
            $fileSize = (Get-Item $modelFile).Length
            if ($fileSize -lt $minSizeBytes) {
                Write-Host "[!] Downloaded file is too small ($fileSize bytes). The download may be incomplete." -ForegroundColor Red
                Write-Host "[!] Recovery steps:" -ForegroundColor Red
                Write-Host "      1. Check your internet connection." -ForegroundColor Red
                Write-Host "      2. Set LFM_MODEL_URL to a valid model URL and re-run Install." -ForegroundColor Red
                Write-Host "      3. Or manually place LFM2.5-VL-450M-Q4_0.gguf in: $modelDir" -ForegroundColor Red
                exit 1
            }
            Write-Host "    Model downloaded successfully ($([Math]::Round($fileSize / 1MB, 1)) MB)." -ForegroundColor Green
        } catch {
            Write-Host "[!] Model download failed: $_" -ForegroundColor Red
            Write-Host "[!] Recovery steps:" -ForegroundColor Red
            Write-Host "      1. Check your internet connection (required only at install time)." -ForegroundColor Red
            Write-Host "      2. Override the URL: `$env:LFM_MODEL_URL = '<url>'; .\run.ps1" -ForegroundColor Red
            Write-Host "      3. Or manually place LFM2.5-VL-450M-Q4_0.gguf in: $modelDir" -ForegroundColor Red
            exit 1
        }
    }

    Write-Host "[+] Install complete. Transitioning to Run Phase..." -ForegroundColor Green
    Run-App
}

function Run-App {
    Write-Host "[*] Starting LFM Orbit..." -ForegroundColor Cyan
    
    $simSatDir = "$RepoRoot\source\backend\SimSat-main"
    $dockerAvailable = Get-Command docker -ErrorAction SilentlyContinue
    
    if ((Test-Path $simSatDir) -and $dockerAvailable) {
        Write-Host "[*] Launching SimSat (docker compose up)..." -ForegroundColor Cyan
        Push-Location $simSatDir
        try {
            docker compose up -d
            Write-Host "    SimSat started in background." -ForegroundColor Green
        } catch {
            Write-Host "[!] Failed to start SimSat. Docker might not be running. (Backend will fallback automatically)" -ForegroundColor Yellow
        }
        Pop-Location
    } elseif (Test-Path $simSatDir) {
        Write-Host "[i] Skipping SimSat integration -> Docker not found. Backend will seamlessly use NASA/Mock fallback." -ForegroundColor Gray
    }
    
    $uvAvailable = Get-Command uv -ErrorAction SilentlyContinue
    if ($uvAvailable) {
        Write-Host "[*] Launching FastAPI Backend (uv)..." -ForegroundColor Cyan
        Start-Process -FilePath "uv" -ArgumentList "run", "uvicorn", "api.main:app", "--port", "8000" -WorkingDirectory "$RepoRoot\source\backend"
    } else {
        Write-Host "[*] Launching FastAPI Backend (uvicorn)..." -ForegroundColor Cyan
        Start-Process -FilePath "uvicorn" -ArgumentList "api.main:app", "--port", "8000" -WorkingDirectory "$RepoRoot\source\backend"
    }

    Write-Host "[*] Waiting for backend to be ready..." -ForegroundColor Cyan
    $maxWait = 30
    $ready = $false
    for ($i = 0; $i -lt $maxWait; $i++) {
        try {
            $resp = Invoke-WebRequest -Uri "http://127.0.0.1:8000/api/health" -UseBasicParsing -TimeoutSec 2 -ErrorAction Stop
            if ($resp.StatusCode -eq 200) {
                $ready = $true
                break
            }
        } catch {}
        Start-Sleep -Seconds 1
        Write-Host "    Waiting... ($($i+1)s)" -ForegroundColor Gray
    }

    if (-not $ready) {
        Write-Host "[!] Backend did not start within ${maxWait}s. Check for errors above." -ForegroundColor Red
        exit 1
    }

    Write-Host "[+] Backend ready. Launching React Frontend..." -ForegroundColor Green
    Push-Location "source\frontend"
    npm run dev
    Pop-Location
}

function Clean-Data {
    Write-Host "[*] Cleaning runtime data for a cold start..." -ForegroundColor Yellow
    $busPath = "$RepoRoot\runtime-data\agent_bus.sqlite"
    if (Test-Path $busPath) {
        Remove-Item -Force $busPath
        Write-Host "    Deleted agent_bus.sqlite" -ForegroundColor Gray
    }
    Write-Host "[+] Clean complete." -ForegroundColor Green
    Start-Sleep -Seconds 2
}

function Show-Banner {
    $bannerPath = Join-Path $PSScriptRoot 'docs\banner.txt'
    if (Test-Path $bannerPath) {
        Write-Host (Get-Content $bannerPath -Raw -Encoding UTF8) -ForegroundColor Cyan
    } else {
        Write-Host 'LFM Orbit' -ForegroundColor Cyan
    }
}

while ($true) {
    Clear-Host
    Show-Banner
    Write-Host "======================================" -ForegroundColor Yellow
    Write-Host "              LFM ORBIT               " -ForegroundColor Green
    Write-Host "======================================" -ForegroundColor Yellow
    Write-Host "1. Install/Repair (fetches models) -> Run"
    Write-Host "2. Run (if already installed)"
    Write-Host "3. Clean (deletes runtime data for cold start)"
    Write-Host "4. Exit"
    Write-Host "======================================" -ForegroundColor Yellow
    
    $choice = Read-Host "Select an option"
    
    switch ($choice) {
        '1' { Install-Deps; exit }
        '2' { Run-App; exit }
        '3' { Clean-Data }
        '4' { exit }
        default { Write-Host "Invalid choice" -ForegroundColor Red; Start-Sleep -Seconds 1 }
    }
}
param(
    [switch]$Install,
    [switch]$InstallOnly,
    [switch]$Run,
    [switch]$Clean,
    [switch]$Verify,
    [switch]$FetchModel,
    [switch]$Help
)

$ErrorActionPreference = "Stop"
$RepoRoot = $PSScriptRoot
$BackendDir = Join-Path $RepoRoot "source\backend"
$FrontendDir = Join-Path $RepoRoot "source\frontend"
$BackendVenvDir = $env:UV_PROJECT_ENVIRONMENT
if (-not $BackendVenvDir) {
    $BackendVenvDir = Join-Path $BackendDir ".venv-windows"
    [Environment]::SetEnvironmentVariable("UV_PROJECT_ENVIRONMENT", $BackendVenvDir, "Process")
}
$RuntimeDir = Join-Path $RepoRoot "runtime-data"
$LegacyBackendRuntimeDir = Join-Path $BackendDir "runtime-data"
$ModelDir = Join-Path $RuntimeDir "models\lfm2.5-vlm-450m"
$ModelFile = Join-Path $ModelDir "LFM2.5-VL-450M-Q4_0.gguf"
$ModelManifest = Join-Path $ModelDir "model_manifest.json"
$DefaultModelRepoId = "Shoozes/lfm2.5-450m-vl-orbit-satellite"
$DefaultModelRevision = "main"
$SimSatDir = Join-Path $BackendDir "SimSat-main"

Set-Location -LiteralPath $RepoRoot

function Import-DotEnv {
    $envPath = Join-Path $RepoRoot ".env"
    if (-not (Test-Path $envPath)) {
        return
    }

    foreach ($rawLine in Get-Content -LiteralPath $envPath -Encoding UTF8) {
        $line = $rawLine.Trim()
        if (-not $line -or $line.StartsWith("#") -or -not $line.Contains("=")) {
            continue
        }

        $parts = $line.Split("=", 2)
        $key = $parts[0].Trim()
        $value = $parts[1].Trim()
        if ($key -notmatch "^[A-Za-z_][A-Za-z0-9_]*$") {
            continue
        }

        if ($value.Length -ge 2) {
            $first = $value.Substring(0, 1)
            $last = $value.Substring($value.Length - 1, 1)
            if (($first -eq '"' -and $last -eq '"') -or ($first -eq "'" -and $last -eq "'")) {
                $value = $value.Substring(1, $value.Length - 2)
            }
        }

        [Environment]::SetEnvironmentVariable($key, $value, "Process")
    }

    Write-Host "[i] Loaded environment overrides from .env" -ForegroundColor Gray
}

Import-DotEnv
$BackendVenvDir = $env:UV_PROJECT_ENVIRONMENT

function Require-Command {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string]$Hint
    )

    $command = Get-Command $Name -ErrorAction SilentlyContinue
    if (-not $command) {
        throw "$Name not found. $Hint"
    }
}

function Show-Usage {
    Write-Host "LFM Orbit launcher" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Usage:"
    Write-Host "  .\run.ps1                 Open the interactive menu"
    Write-Host "  .\run.ps1 -Install        Install locked deps, then start backend + frontend"
    Write-Host "  .\run.ps1 -InstallOnly    Install locked deps without starting the app"
    Write-Host "  .\run.ps1 -Run            Start backend + frontend from existing deps"
    Write-Host "  .\run.ps1 -Clean          Clear mutable runtime stores for a cold start"
    Write-Host "  .\run.ps1 -Verify         Install deps and run backend, frontend, and E2E checks"
    Write-Host "  .\run.ps1 -Install -FetchModel"
    Write-Host "                            Also fetch the trained Orbit GGUF bundle before startup"
}

function Write-SimSatStatus {
    if (Test-Path $SimSatDir) {
        Write-Host "[i] SimSat vendored source is present." -ForegroundColor Gray
        return
    }

    Write-Host "[i] SimSat vendored source is missing. Orbit will still start with Sentinel/NASA/local fallback paths." -ForegroundColor Yellow
}

function Install-BackendDeps {
    Require-Command -Name "uv" -Hint "Install uv from https://docs.astral.sh/uv/ to honor source/backend/uv.lock."
    Write-Host "[*] Syncing backend dependencies from uv.lock..." -ForegroundColor Cyan

    $syncArgs = @("sync", "--extra", "dev", "--locked")
    $installModelRuntime = $FetchModel -or (Test-Path $ModelFile) -or ($env:LFM_ORBIT_INSTALL_MODEL_RUNTIME -match "^(1|true|yes|on)$")
    if ($installModelRuntime) {
        $syncArgs += @("--extra", "model")
        Write-Host "[i] Attempting optional llama-cpp model runtime install." -ForegroundColor Gray
    }

    Push-Location $BackendDir
    try {
        & uv @syncArgs
        $syncExit = $LASTEXITCODE
        if ($syncExit -ne 0) {
            if ($installModelRuntime) {
                Write-Host "[!] Optional llama-cpp model runtime failed to install. Retrying core backend install without model runtime." -ForegroundColor Yellow
                uv sync --extra dev --locked
                if ($LASTEXITCODE -ne 0) {
                    throw "Backend dependency sync failed with exit code $LASTEXITCODE."
                }
            } else {
                throw "Backend dependency sync failed with exit code $syncExit."
            }
        }
    } finally {
        Pop-Location
    }
}

function Install-FrontendDeps {
    Require-Command -Name "npm" -Hint "Install Node.js using the version pinned in .nvmrc."
    Write-Host "[*] Installing frontend dependencies from package-lock.json..." -ForegroundColor Cyan
    Push-Location $FrontendDir
    try {
        npm ci
    } finally {
        Pop-Location
    }
}

function Ensure-OptionalModel {
    if (-not $FetchModel) {
        Write-Host "[i] Skipping optional GGUF model download. Orbit still boots with the local fallback analysis path." -ForegroundColor Gray
        return
    }

    Require-Command -Name "python" -Hint "Install Python 3.12 to fetch the optional GGUF model."

    $minSizeBytes = 1MB

    New-Item -ItemType Directory -Force -Path $ModelDir | Out-Null

    if ($env:LFM_MODEL_URL) {
        $modelUrl = $env:LFM_MODEL_URL
        $needsDownload = $false
        if (Test-Path $ModelFile) {
            $fileSize = (Get-Item $ModelFile).Length
            if ($fileSize -ge $minSizeBytes) {
                Write-Host "    Optional GGUF model already present ($([Math]::Round($fileSize / 1MB, 1)) MB)." -ForegroundColor Gray
            } else {
                Write-Host "    Existing GGUF file is incomplete ($fileSize bytes). Re-downloading..." -ForegroundColor Yellow
                $needsDownload = $true
            }
        } else {
            $needsDownload = $true
        }

        if (-not $needsDownload) {
            return
        }

        Write-Host "[*] Fetching optional GGUF model from LFM_MODEL_URL..." -ForegroundColor Cyan
        Write-Host "    Source: $modelUrl" -ForegroundColor Gray
        Write-Host "    Target: $ModelFile" -ForegroundColor Gray

        python -c "import urllib.request, sys; print('Downloading optional model...', flush=True); urllib.request.urlretrieve(sys.argv[1], sys.argv[2])" $modelUrl $ModelFile
    } else {
        $modelRepoId = $env:LFM_MODEL_REPO_ID
        if (-not $modelRepoId) { $modelRepoId = $env:CANOPY_SENTINEL_MODEL_REPO_ID }
        if (-not $modelRepoId) { $modelRepoId = $DefaultModelRepoId }

        $modelRevision = $env:LFM_MODEL_REVISION
        if (-not $modelRevision) { $modelRevision = $env:CANOPY_SENTINEL_MODEL_REVISION }
        if (-not $modelRevision) { $modelRevision = $DefaultModelRevision }

        $installedRepoId = ""
        $installedRevision = ""
        if (Test-Path $ModelManifest) {
            try {
                $manifest = Get-Content -LiteralPath $ModelManifest -Raw -Encoding UTF8 | ConvertFrom-Json
                if ($manifest.source -and $manifest.source.repo_id) { $installedRepoId = [string]$manifest.source.repo_id }
                elseif ($manifest.repo_id) { $installedRepoId = [string]$manifest.repo_id }
                if ($manifest.source -and $manifest.source.revision) { $installedRevision = [string]$manifest.source.revision }
                elseif ($manifest.revision) { $installedRevision = [string]$manifest.revision }
            } catch {
                Write-Host "    Existing model manifest is unreadable. Refreshing model handoff." -ForegroundColor Yellow
            }
        }

        if (Test-Path $ModelFile) {
            $fileSize = (Get-Item $ModelFile).Length
            if ($fileSize -ge $minSizeBytes -and $installedRepoId -eq $modelRepoId -and $installedRevision -eq $modelRevision) {
                Write-Host "    Trained Orbit GGUF already present from $modelRepoId@$modelRevision ($([Math]::Round($fileSize / 1MB, 1)) MB)." -ForegroundColor Gray
                return
            }
            Write-Host "    Existing GGUF is missing or does not match the trained Orbit handoff. Refreshing..." -ForegroundColor Yellow
        }

        Write-Host "[*] Fetching trained Orbit GGUF bundle..." -ForegroundColor Cyan
        Write-Host "    Repo: $modelRepoId@$modelRevision" -ForegroundColor Gray
        Write-Host "    Target: $ModelDir" -ForegroundColor Gray
        Push-Location $BackendDir
        try {
            python scripts\fetch_satellite_model.py --repo-id $modelRepoId --revision $modelRevision --force
        } finally {
            Pop-Location
        }
    }

    if (-not (Test-Path $ModelFile)) {
        throw "Expected GGUF file was not written: $ModelFile"
    }

    $fileSize = (Get-Item $ModelFile).Length
    if ($fileSize -lt $minSizeBytes) {
        throw "Downloaded GGUF file is too small ($fileSize bytes). Remove it and retry with a valid model repo or LFM_MODEL_URL."
    }

    Write-Host "[+] Optional trained GGUF model ready ($([Math]::Round($fileSize / 1MB, 1)) MB)." -ForegroundColor Green
}

function Install-Deps {
    Install-BackendDeps
    Write-SimSatStatus
    Install-FrontendDeps
    Ensure-OptionalModel
    Write-Host "[+] Install/repair complete." -ForegroundColor Green
}

function Install-PlaywrightBrowser {
    Require-Command -Name "npm" -Hint "Install Node.js using the version pinned in .nvmrc."
    Write-Host "[*] Ensuring Playwright Chromium is installed..." -ForegroundColor Cyan
    Push-Location $FrontendDir
    try {
        npx playwright install chromium
    } finally {
        Pop-Location
    }
}

function Run-Verify {
    Write-Host "[*] Running full repo verification..." -ForegroundColor Cyan
    Install-BackendDeps
    Install-FrontendDeps
    Install-PlaywrightBrowser

    Push-Location $BackendDir
    try {
        Write-Host "[*] Backend tests..." -ForegroundColor Cyan
        uv run --no-sync pytest -q
    } finally {
        Pop-Location
    }

    Push-Location $FrontendDir
    try {
        Write-Host "[*] Frontend typecheck..." -ForegroundColor Cyan
        npm run lint
        Write-Host "[*] Frontend production build..." -ForegroundColor Cyan
        npm run build
        Write-Host "[*] Playwright E2E..." -ForegroundColor Cyan
        npm run test:e2e
    } finally {
        Pop-Location
    }

    Write-Host "[+] Verification complete." -ForegroundColor Green
}

function Start-BackendProcess {
    $uvCommand = Get-Command "uv" -ErrorAction SilentlyContinue
    $venvPython = Join-Path $BackendVenvDir "Scripts\python.exe"

    if ($uvCommand) {
        return Start-Process -FilePath $uvCommand.Source -ArgumentList "run", "--no-sync", "uvicorn", "api.main:app", "--host", "127.0.0.1", "--port", "8000" -WorkingDirectory $BackendDir -WindowStyle Hidden -PassThru
    }

    if (Test-Path $venvPython) {
        return Start-Process -FilePath $venvPython -ArgumentList "-m", "uvicorn", "api.main:app", "--host", "127.0.0.1", "--port", "8000" -WorkingDirectory $BackendDir -WindowStyle Hidden -PassThru
    }

    throw "Backend runtime is not installed. Run .\run.ps1 -Install first."
}

function Run-App {
    Require-Command -Name "npm" -Hint "Install Node.js using the version pinned in .nvmrc."

    Write-Host "[*] Starting LFM Orbit..." -ForegroundColor Cyan
    Write-SimSatStatus

    if (-not (Test-Path $ModelFile)) {
        Write-Host "[i] Optional GGUF model not found. Satellite-side reasoning will stay on safe fallback behavior." -ForegroundColor Gray
    }

    Write-Host "[*] Launching backend..." -ForegroundColor Cyan
    $backendProcess = Start-BackendProcess

    Write-Host "[*] Waiting for backend health check..." -ForegroundColor Cyan
    $ready = $false
    for ($i = 1; $i -le 30; $i++) {
        try {
            $response = Invoke-WebRequest -Uri "http://127.0.0.1:8000/api/health" -UseBasicParsing -TimeoutSec 2 -ErrorAction Stop
            if ($response.StatusCode -eq 200) {
                $ready = $true
                break
            }
        } catch {
        }
        Start-Sleep -Seconds 1
        Write-Host "    Waiting... (${i}s)" -ForegroundColor Gray
    }

    if (-not $ready) {
        if ($backendProcess -and -not $backendProcess.HasExited) {
            Stop-Process -Id $backendProcess.Id -Force
        }
        throw "Backend did not become healthy within 30 seconds."
    }

    Write-Host "[+] Backend ready on http://127.0.0.1:8000" -ForegroundColor Green
    Write-Host "[*] Launching frontend on http://127.0.0.1:5173 ..." -ForegroundColor Cyan

    try {
        Push-Location $FrontendDir
        try {
            npm run dev -- --host 127.0.0.1
        } finally {
            Pop-Location
        }
    } finally {
        if ($backendProcess -and -not $backendProcess.HasExited) {
            Write-Host "[*] Stopping backend process $($backendProcess.Id)..." -ForegroundColor Gray
            Stop-Process -Id $backendProcess.Id -Force
        }
    }
}

function Clean-Data {
    Write-Host "[*] Cleaning runtime data for a cold start..." -ForegroundColor Yellow
    $pathsToRemove = @(
        (Join-Path $RuntimeDir "agent_bus.sqlite"),
        (Join-Path $RuntimeDir "dtn_queue.sqlite"),
        (Join-Path $RuntimeDir "demo_metrics_summary.json"),
        (Join-Path $RuntimeDir "api_cache.sqlite"),
        (Join-Path $LegacyBackendRuntimeDir "api_cache.sqlite")
    )

    foreach ($path in $pathsToRemove) {
        if (Test-Path $path) {
            Remove-Item -LiteralPath $path -Force
            Write-Host "    Removed $path" -ForegroundColor Gray
        }
    }

    $ObservationStoreDir = Join-Path $BackendDir "assets\observation_store"
    if (Test-Path $ObservationStoreDir) {
        Get-ChildItem -LiteralPath $ObservationStoreDir -Filter "*.json" -File | ForEach-Object {
            Remove-Item -LiteralPath $_.FullName -Force
            Write-Host "    Removed $($_.FullName)" -ForegroundColor Gray
        }
    }

    Write-Host "[+] Clean complete." -ForegroundColor Green
}

function Show-Banner {
    $bannerPath = Join-Path $RepoRoot "docs\banner.txt"
    if (Test-Path $bannerPath) {
        Write-Host (Get-Content $bannerPath -Raw -Encoding UTF8) -ForegroundColor Cyan
    } else {
        Write-Host "LFM Orbit" -ForegroundColor Cyan
    }
}

function Run-InteractiveMenu {
    while ($true) {
        Clear-Host
        Show-Banner
        Write-Host "======================================" -ForegroundColor Yellow
        Write-Host "              LFM ORBIT               " -ForegroundColor Green
        Write-Host "======================================" -ForegroundColor Yellow
        Write-Host "1. Install/Repair -> Run"
        Write-Host "2. Install/Repair + Fetch optional GGUF model -> Run"
        Write-Host "3. Install/Repair only"
        Write-Host "4. Run"
        Write-Host "5. Verify (backend + frontend + E2E)"
        Write-Host "6. Clean (cold-start runtime reset)"
        Write-Host "7. Exit"
        Write-Host "======================================" -ForegroundColor Yellow

        $choice = Read-Host "Select an option"

        switch ($choice) {
            "1" {
                Install-Deps
                Run-App
                exit
            }
            "2" {
                $script:FetchModel = $true
                Install-Deps
                Run-App
                exit
            }
            "3" {
                Install-Deps
                exit
            }
            "4" {
                Run-App
                exit
            }
            "5" {
                Run-Verify
                exit
            }
            "6" {
                Clean-Data
                Start-Sleep -Seconds 2
            }
            "7" {
                exit
            }
            default {
                Write-Host "Invalid choice" -ForegroundColor Red
                Start-Sleep -Seconds 1
            }
        }
    }
}

if ($Help) {
    Show-Usage
    exit
}

if ($Clean) {
    Clean-Data
}

if ($InstallOnly) {
    Install-Deps
    exit
}

if ($Verify) {
    Run-Verify
    exit
}

if ($Install) {
    Install-Deps
    Run-App
    exit
}

if ($Run) {
    Run-App
    exit
}

if ($Clean) {
    exit
}

Run-InteractiveMenu

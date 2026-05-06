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
$ToolsDir = Join-Path $RuntimeDir "tools"
$UvVenvDir = Join-Path $ToolsDir "uv-venv"
$UvBootstrapExe = Join-Path $UvVenvDir "Scripts\uv.exe"
$ModelDir = Join-Path $RuntimeDir "models\lfm2.5-vlm-450m"
$ModelFile = Join-Path $ModelDir "LFM2.5-VL-450M-Q4_0.gguf"
$ModelManifest = Join-Path $ModelDir "model_manifest.json"
$DefaultModelRepoId = "Shoozes/lfm2.5-450m-vl-orbit-satellite"
$DefaultModelRevision = "main"
$SimSatDir = Join-Path $BackendDir "SimSat-main"
$script:UvCommand = $null
$script:PythonCommand = $null

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

function Set-ProductionRuntimeDefaults {
    if (-not $env:OBSERVATION_PROVIDER) {
        [Environment]::SetEnvironmentVariable("OBSERVATION_PROVIDER", "simsat_sentinel", "Process")
    }
    if (-not $env:SIMSAT_ENABLED) {
        [Environment]::SetEnvironmentVariable("SIMSAT_ENABLED", "true", "Process")
    }
    if (-not $env:SIMSAT_DATA_SOURCE) {
        [Environment]::SetEnvironmentVariable("SIMSAT_DATA_SOURCE", "sentinel", "Process")
    }
    if (-not $env:DISABLE_EXTERNAL_APIS) {
        [Environment]::SetEnvironmentVariable("DISABLE_EXTERNAL_APIS", "true", "Process")
    }
}

Set-ProductionRuntimeDefaults
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

function Ensure-Python {
    if ($script:PythonCommand) {
        return $script:PythonCommand
    }

    $command = Get-Command "python" -ErrorAction SilentlyContinue
    if (-not $command) {
        throw "Python 3.10+ not found. Install Python 3.10 or newer, then rerun the launcher."
    }

    & $command.Source -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)"
    if ($LASTEXITCODE -ne 0) {
        throw "Python 3.10+ is required. Found an older Python at $($command.Source)."
    }

    $script:PythonCommand = $command.Source
    return $script:PythonCommand
}

function Find-UvCommand {
    $command = Get-Command "uv" -ErrorAction SilentlyContinue
    if ($command) {
        return $command.Source
    }

    if (Test-Path $UvBootstrapExe) {
        return $UvBootstrapExe
    }

    return $null
}

function Add-ToolDirToPath {
    param([Parameter(Mandatory = $true)][string]$ToolPath)

    $toolDir = Split-Path -Parent $ToolPath
    if (-not $toolDir) {
        return
    }

    $pathEntries = @($env:PATH -split ";" | Where-Object { $_ })
    if ($pathEntries -notcontains $toolDir) {
        $env:PATH = "$toolDir;$env:PATH"
    }
}

function Ensure-Uv {
    if ($script:UvCommand) {
        Add-ToolDirToPath -ToolPath $script:UvCommand
        return $script:UvCommand
    }

    $uv = Find-UvCommand
    if ($uv) {
        $script:UvCommand = $uv
        Add-ToolDirToPath -ToolPath $script:UvCommand
        return $script:UvCommand
    }

    if ($env:LFM_ORBIT_SKIP_UV_BOOTSTRAP -eq "1") {
        throw "uv not found. Install uv or unset LFM_ORBIT_SKIP_UV_BOOTSTRAP so the launcher can bootstrap repo-local uv."
    }

    $python = Ensure-Python
    Write-Host "[*] uv not found; bootstrapping repo-local uv into runtime-data\tools\uv-venv..." -ForegroundColor Cyan
    New-Item -ItemType Directory -Force -Path $ToolsDir | Out-Null

    & $python -m venv $UvVenvDir
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to create uv bootstrap virtualenv at $UvVenvDir."
    }

    $venvPython = Join-Path $UvVenvDir "Scripts\python.exe"
    if (-not (Test-Path $venvPython)) {
        throw "uv bootstrap virtualenv did not contain $venvPython."
    }

    $pipOutput = & $venvPython -m pip install --upgrade pip uv 2>&1
    if ($LASTEXITCODE -ne 0) {
        if ($pipOutput) {
            Write-Host ($pipOutput -join "`n") -ForegroundColor Red
        }
        throw "Failed to install uv into $UvVenvDir."
    }

    if (-not (Test-Path $UvBootstrapExe)) {
        throw "uv bootstrap did not produce $UvBootstrapExe."
    }

    $script:UvCommand = $UvBootstrapExe
    Add-ToolDirToPath -ToolPath $script:UvCommand
    return $script:UvCommand
}

function Ensure-Node {
    Require-Command -Name "node" -Hint "Install Node.js 20.19.0 or newer 22.12.0+; .nvmrc pins 20.19.0."
    Require-Command -Name "npm" -Hint "Install Node.js 20.19.0 or newer 22.12.0+; npm ships with Node.js."

    node -e "const [maj,min,patch]=process.versions.node.split('.').map(Number); const ok=(maj===20 && (min>19 || (min===19 && patch>=0))) || (maj>22) || (maj===22 && min>=12); process.exit(ok?0:1);"
    if ($LASTEXITCODE -ne 0) {
        throw "Unsupported Node.js version $(node --version). Use Node.js 20.19.0, or Node.js 22.12.0 or newer."
    }
}

function Get-FileTail {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [int]$Count = 40
    )

    if (-not (Test-Path $Path)) {
        return ""
    }

    try {
        return (Get-Content -LiteralPath $Path -Tail $Count -ErrorAction Stop) -join "`n"
    } catch {
        return ""
    }
}

function Invoke-RequiredCommand {
    param(
        [Parameter(Mandatory = $true)][scriptblock]$Command,
        [Parameter(Mandatory = $true)][string]$Description
    )

    & $Command
    if ($LASTEXITCODE -ne 0) {
        throw "$Description failed with exit code $LASTEXITCODE."
    }
}

function Get-ListeningPortProcesses {
    param([Parameter(Mandatory = $true)][int]$Port)

    $connections = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    if (-not $connections) {
        return @()
    }

    $processIds = $connections |
        Where-Object { $_.OwningProcess -and $_.OwningProcess -gt 0 } |
        Select-Object -ExpandProperty OwningProcess -Unique

    $items = @()
    foreach ($processId in $processIds) {
        $processInfo = Get-CimInstance Win32_Process -Filter "ProcessId=$processId" -ErrorAction SilentlyContinue
        if ($processInfo) {
            $items += $processInfo
        }
    }
    return $items
}

function Get-ChildProcessIds {
    param([Parameter(Mandatory = $true)][int]$ProcessId)

    $children = Get-CimInstance Win32_Process -Filter "ParentProcessId=$ProcessId" -ErrorAction SilentlyContinue
    $ids = @()
    foreach ($child in $children) {
        $childId = [int]$child.ProcessId
        $ids += Get-ChildProcessIds -ProcessId $childId
        $ids += $childId
    }
    return $ids
}

function Stop-OrbitProcessTree {
    param(
        [Parameter(Mandatory = $true)][int]$ProcessId,
        [string]$Label = "process"
    )

    if ($ProcessId -eq $PID) {
        throw "Refusing to stop the current launcher process while cleaning up $Label."
    }

    $ids = @()
    $ids += Get-ChildProcessIds -ProcessId $ProcessId
    $ids += $ProcessId
    $ids = $ids | Select-Object -Unique

    foreach ($id in $ids) {
        if ($id -eq $PID) {
            continue
        }
        $process = Get-Process -Id $id -ErrorAction SilentlyContinue
        if (-not $process) {
            continue
        }
        Stop-Process -Id $id -Force -ErrorAction SilentlyContinue
    }

    foreach ($id in $ids) {
        if ($id -eq $PID) {
            continue
        }
        Wait-Process -Id $id -Timeout 5 -ErrorAction SilentlyContinue
    }
}

function Test-IsOrbitOwnedProcess {
    param(
        [Parameter(Mandatory = $true)]$ProcessInfo,
        [Parameter(Mandatory = $true)][int]$Port
    )

    $commandLine = [string]$ProcessInfo.CommandLine
    if (-not $commandLine) {
        return $false
    }

    $normalizedCommand = $commandLine.ToLowerInvariant()
    $repoNeedle = $RepoRoot.ToLowerInvariant()
    $backendNeedle = $BackendDir.ToLowerInvariant()
    $frontendNeedle = $FrontendDir.ToLowerInvariant()

    return (
        $normalizedCommand.Contains($repoNeedle) -or
        $normalizedCommand.Contains($backendNeedle) -or
        $normalizedCommand.Contains($frontendNeedle) -or
        ($Port -eq 8000 -and $normalizedCommand.Contains("api.main:app") -and $normalizedCommand.Contains("--port 8000")) -or
        ($Port -eq 5173 -and $normalizedCommand.Contains("vite") -and $normalizedCommand.Contains("5173"))
    )
}

function Ensure-OrbitPortAvailable {
    param(
        [Parameter(Mandatory = $true)][int]$Port,
        [Parameter(Mandatory = $true)][string]$Role
    )

    $listeners = @(Get-ListeningPortProcesses -Port $Port)
    if ($listeners.Count -eq 0) {
        return
    }

    foreach ($listener in $listeners) {
        $listenerPid = [int]$listener.ProcessId
        if (Test-IsOrbitOwnedProcess -ProcessInfo $listener -Port $Port) {
            Write-Host "[i] Stopping stale LFM Orbit $Role on port $Port (PID $listenerPid)..." -ForegroundColor Yellow
            Stop-OrbitProcessTree -ProcessId $listenerPid -Label "$Role on port $Port"
            continue
        }

        $name = (Get-Process -Id $listenerPid -ErrorAction SilentlyContinue).ProcessName
        if (-not $name) { $name = "unknown" }
        throw "Port $Port is already in use by $name (PID $listenerPid). Close that process, then rerun .\run.ps1 option 1."
    }

    Start-Sleep -Milliseconds 500
    $remaining = @(Get-ListeningPortProcesses -Port $Port)
    if ($remaining.Count -gt 0) {
        $pids = ($remaining | ForEach-Object { $_.ProcessId }) -join ", "
        throw "Port $Port is still in use after cleanup (PID $pids). Close the process manually, then rerun .\run.ps1 option 1."
    }
}

function Show-Usage {
    Write-Host "LFM Orbit launcher" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Usage:"
    Write-Host "  .\run.ps1                 Open the interactive menu"
    Write-Host "  .\run.ps1 -Install        Install locked deps, fetch the trained GGUF, then start backend + frontend"
    Write-Host "  .\run.ps1 -InstallOnly    Advanced/dev: install locked deps without starting the app"
    Write-Host "  .\run.ps1 -Run            Advanced/dev: start backend + frontend from existing deps"
    Write-Host "  .\run.ps1 -Clean          Clear mutable runtime stores for a cold start"
    Write-Host "  .\run.ps1 -Verify         Install deps and run backend, frontend, and E2E checks"
}

function Write-SimSatStatus {
    if (Test-Path $SimSatDir) {
        Write-Host "[i] SimSat vendored source is present." -ForegroundColor Gray
        return
    }

    Write-Host "[i] SimSat vendored source is missing. Orbit stays on the SimSat/local path; direct providers require explicit OBSERVATION_PROVIDER overrides." -ForegroundColor Yellow
}

function Install-BackendDeps {
    $uv = Ensure-Uv
    Write-Host "[*] Syncing backend dependencies from uv.lock..." -ForegroundColor Cyan

    $syncArgs = @("sync", "--extra", "dev", "--locked")
    $installModelRuntime = $FetchModel -or (Test-Path $ModelFile) -or ($env:LFM_ORBIT_INSTALL_MODEL_RUNTIME -match "^(1|true|yes|on)$")
    if ($installModelRuntime) {
        $syncArgs += @("--extra", "model")
        Write-Host "[i] Attempting llama-cpp model runtime install for GGUF inference." -ForegroundColor Gray
    }

    Push-Location $BackendDir
    try {
        & $uv @syncArgs
        $syncExit = $LASTEXITCODE
        if ($syncExit -ne 0) {
            if ($installModelRuntime) {
                throw "llama-cpp model runtime failed to install. The production/hackathon path requires the trained GGUF runtime; repair compiler/Python wheel support and rerun option 1."
            } else {
                throw "Backend dependency sync failed with exit code $syncExit."
            }
        }
    } finally {
        Pop-Location
    }
}

function Install-FrontendDeps {
    Ensure-Node
    Write-Host "[*] Installing frontend dependencies from package-lock.json..." -ForegroundColor Cyan
    Push-Location $FrontendDir
    try {
        Invoke-RequiredCommand -Description "Frontend dependency install" -Command { npm ci }
    } finally {
        Pop-Location
    }
}

function Ensure-TrainedModel {
    if (-not $FetchModel) {
        Write-Host "[i] Skipping trained GGUF fetch. Use -FetchModel for production/hackathon runs; fallback analysis is development-only." -ForegroundColor Gray
        return
    }

    $python = Ensure-Python

    $minSizeBytes = 1MB

    New-Item -ItemType Directory -Force -Path $ModelDir | Out-Null

    if ($env:LFM_MODEL_URL) {
        $modelUrl = $env:LFM_MODEL_URL
        $needsDownload = $false
        if (Test-Path $ModelFile) {
            $fileSize = (Get-Item $ModelFile).Length
            if ($fileSize -ge $minSizeBytes) {
                Write-Host "    Trained Orbit GGUF already present ($([Math]::Round($fileSize / 1MB, 1)) MB)." -ForegroundColor Gray
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

        Write-Host "[*] Fetching trained Orbit GGUF from LFM_MODEL_URL..." -ForegroundColor Cyan
        Write-Host "    Source: $modelUrl" -ForegroundColor Gray
        Write-Host "    Target: $ModelFile" -ForegroundColor Gray

        Invoke-RequiredCommand -Description "Trained Orbit GGUF download" -Command {
            & $python -c "import urllib.request, sys; print('Downloading trained Orbit model...', flush=True); urllib.request.urlretrieve(sys.argv[1], sys.argv[2])" $modelUrl $ModelFile
        }
    } else {
        $modelRepoId = $env:LFM_MODEL_REPO_ID
        if (-not $modelRepoId) { $modelRepoId = $env:CANOPY_SENTINEL_MODEL_REPO_ID }
        if (-not $modelRepoId) { $modelRepoId = $DefaultModelRepoId }

        $modelRevision = $env:LFM_MODEL_REVISION
        if (-not $modelRevision) { $modelRevision = $env:CANOPY_SENTINEL_MODEL_REVISION }
        if (-not $modelRevision) { $modelRevision = $DefaultModelRevision }
        $movingModelRevision = ([string]$modelRevision).ToLowerInvariant() -in @("main", "master", "latest")

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
                if (-not $movingModelRevision) {
                    Write-Host "    Trained Orbit GGUF already present from $modelRepoId@$modelRevision ($([Math]::Round($fileSize / 1MB, 1)) MB)." -ForegroundColor Gray
                    return
                }
                Write-Host "    Moving Hugging Face revision '$modelRevision' requested. Refreshing trained Orbit GGUF..." -ForegroundColor Yellow
            } else {
                Write-Host "    Existing GGUF is missing or does not match the trained Orbit handoff. Refreshing..." -ForegroundColor Yellow
            }
        }

        Write-Host "[*] Fetching trained Orbit GGUF bundle..." -ForegroundColor Cyan
        Write-Host "    Repo: $modelRepoId@$modelRevision" -ForegroundColor Gray
        Write-Host "    Target: $ModelDir" -ForegroundColor Gray
        Push-Location $BackendDir
        try {
            $uv = Ensure-Uv
            Invoke-RequiredCommand -Description "Trained Orbit GGUF fetch" -Command {
                & $uv run --no-sync python scripts\fetch_satellite_model.py --repo-id $modelRepoId --revision $modelRevision --force
            }
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

    Write-Host "[+] Trained Orbit GGUF model ready ($([Math]::Round($fileSize / 1MB, 1)) MB)." -ForegroundColor Green
}

function Assert-TrainedModelRuntime {
    if (-not (Test-Path $ModelFile)) {
        throw "Trained GGUF model is required for this path but was not found: $ModelFile"
    }

    $uv = Ensure-Uv
    Write-Host "[*] Verifying trained GGUF runtime..." -ForegroundColor Cyan
    Push-Location $BackendDir
    try {
        & $uv run --no-sync python scripts\smoke_satellite_model.py --require-present --max-tokens 8
        if ($LASTEXITCODE -ne 0) {
            throw "Trained GGUF runtime smoke failed. Confirm llama-cpp-python is installed in $BackendVenvDir."
        }
    } finally {
        Pop-Location
    }
}

function Install-Deps {
    Install-BackendDeps
    Write-SimSatStatus
    Install-FrontendDeps
    Ensure-TrainedModel
    if ($FetchModel) {
        Assert-TrainedModelRuntime
    }
    Write-Host "[+] Install/repair complete." -ForegroundColor Green
}

function Install-PlaywrightBrowser {
    Ensure-Node
    Write-Host "[*] Ensuring Playwright Chromium is installed..." -ForegroundColor Cyan
    Push-Location $FrontendDir
    try {
        Invoke-RequiredCommand -Description "Playwright Chromium install" -Command { npx playwright install chromium }
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
        $uv = Ensure-Uv
        Invoke-RequiredCommand -Description "Backend tests" -Command { & $uv run --no-sync pytest -q }
        if (Test-Path $ModelFile) {
            Assert-TrainedModelRuntime
        }
    } finally {
        Pop-Location
    }

    Push-Location $FrontendDir
    try {
        Write-Host "[*] Frontend typecheck..." -ForegroundColor Cyan
        Invoke-RequiredCommand -Description "Frontend typecheck" -Command { npm run lint }
        Write-Host "[*] Frontend production build..." -ForegroundColor Cyan
        Invoke-RequiredCommand -Description "Frontend production build" -Command { npm run build }
        Write-Host "[*] Playwright E2E..." -ForegroundColor Cyan
        Invoke-RequiredCommand -Description "Playwright E2E" -Command { npm run test:e2e }
    } finally {
        Pop-Location
    }

    Write-Host "[+] Verification complete." -ForegroundColor Green
}

function Start-BackendProcess {
    $uvCommand = Find-UvCommand
    $venvPython = Join-Path $BackendVenvDir "Scripts\python.exe"
    $LogDir = Join-Path $RuntimeDir "logs"
    New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
    $BackendOutLog = Join-Path $LogDir "backend-run.out.log"
    $BackendErrLog = Join-Path $LogDir "backend-run.err.log"

    if ($uvCommand) {
        return Start-Process -FilePath $uvCommand -ArgumentList "run", "--no-sync", "uvicorn", "api.main:app", "--host", "127.0.0.1", "--port", "8000" -WorkingDirectory $BackendDir -WindowStyle Hidden -RedirectStandardOutput $BackendOutLog -RedirectStandardError $BackendErrLog -PassThru
    }

    if (Test-Path $venvPython) {
        return Start-Process -FilePath $venvPython -ArgumentList "-m", "uvicorn", "api.main:app", "--host", "127.0.0.1", "--port", "8000" -WorkingDirectory $BackendDir -WindowStyle Hidden -RedirectStandardOutput $BackendOutLog -RedirectStandardError $BackendErrLog -PassThru
    }

    throw "Backend runtime is not installed. Run .\run.ps1 -Install first."
}

function Run-App {
    Ensure-Node

    Write-Host "[*] Starting LFM Orbit..." -ForegroundColor Cyan
    Write-SimSatStatus

    if (-not (Test-Path $ModelFile)) {
        Write-Host "[!] Trained GGUF model not found. Run .\run.ps1 -Install for the production/hackathon path; continuing with development fallback behavior." -ForegroundColor Yellow
    }

    Write-Host "[*] Launching backend..." -ForegroundColor Cyan
    Ensure-OrbitPortAvailable -Port 8000 -Role "backend"
    $backendProcess = Start-BackendProcess

    Write-Host "[*] Waiting for backend health check..." -ForegroundColor Cyan
    $ready = $false
    for ($i = 1; $i -le 30; $i++) {
        if ($backendProcess -and $backendProcess.HasExited) {
            $errLog = Join-Path $RuntimeDir "logs\backend-run.err.log"
            $tail = Get-FileTail -Path $errLog
            if ($tail) {
                throw "Backend exited before becoming healthy. Last backend error log:`n$tail"
            }
            throw "Backend exited before becoming healthy."
        }
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
            Stop-OrbitProcessTree -ProcessId $backendProcess.Id -Label "unhealthy backend"
        }
        throw "Backend did not become healthy within 30 seconds."
    }

    Write-Host "[+] Backend ready on http://127.0.0.1:8000" -ForegroundColor Green
    Write-Host "[*] Launching frontend on http://127.0.0.1:5173 ..." -ForegroundColor Cyan

    try {
        Ensure-OrbitPortAvailable -Port 5173 -Role "frontend"
        Push-Location $FrontendDir
        try {
            npm run dev -- --host 127.0.0.1 --port 5173 --strictPort
            if ($LASTEXITCODE -ne 0) {
                throw "Frontend dev server failed with exit code $LASTEXITCODE."
            }
        } finally {
            Pop-Location
        }
    } finally {
        if ($backendProcess -and -not $backendProcess.HasExited) {
            Write-Host "[*] Stopping backend process $($backendProcess.Id)..." -ForegroundColor Gray
            Stop-OrbitProcessTree -ProcessId $backendProcess.Id -Label "backend"
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
        Write-Host "1. Install/Repair + Fetch trained Orbit GGUF -> Run"
        Write-Host "2. Verify (backend + frontend + E2E)"
        Write-Host "3. Clean (cold-start runtime reset)"
        Write-Host "4. Exit"
        Write-Host "======================================" -ForegroundColor Yellow

        $choice = Read-Host "Select an option"

        switch ($choice) {
            "1" {
                $script:FetchModel = $true
                Install-Deps
                Run-App
                exit
            }
            "2" {
                Run-Verify
                exit
            }
            "3" {
                Clean-Data
                Start-Sleep -Seconds 2
            }
            "4" {
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
    $script:FetchModel = $true
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

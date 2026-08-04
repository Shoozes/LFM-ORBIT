param (
    [Parameter(Position=0, Mandatory=$false, HelpMessage="Group name from summary_bank.json")]
    [Alias("Group")]
    [string]$ContextGroup = "",

    [switch]$List,
    [switch]$Audit,
    [switch]$Save,
    [switch]$Open,
    [switch]$NoTree,
    [switch]$IncludeArchived,
    [int]$BudgetKb = 0,
    [string]$PythonPath = ""
)

$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$ContextDir = Join-Path $RepoRoot "runtime-data\context"
$GenScript = Join-Path $RepoRoot ".tools\_gen_struct.py"
$BankScript = Join-Path $RepoRoot ".tools\_gen_bank.py"

function Get-SafeName([string]$Value) {
    if ([string]::IsNullOrWhiteSpace($Value)) { return "default" }
    return ($Value -replace '[^A-Za-z0-9_.-]', '_')
}

function Get-PythonCommand {
    if (-not [string]::IsNullOrWhiteSpace($PythonPath)) {
        if (-not (Test-Path -LiteralPath $PythonPath -PathType Leaf)) {
            throw "PythonPath does not exist: $PythonPath"
        }
        return @((Resolve-Path -LiteralPath $PythonPath).Path)
    }

    if (-not [string]::IsNullOrWhiteSpace($env:GEN_UNI_PYTHON)) {
        if (-not (Test-Path -LiteralPath $env:GEN_UNI_PYTHON -PathType Leaf)) {
            throw "GEN_UNI_PYTHON does not exist: $($env:GEN_UNI_PYTHON)"
        }
        return @((Resolve-Path -LiteralPath $env:GEN_UNI_PYTHON).Path)
    }

    $verifierPython = Join-Path $RepoRoot "runtime-data\verify\backend\.venv\Scripts\python.exe"
    if (Test-Path -LiteralPath $verifierPython -PathType Leaf) {
        return @($verifierPython)
    }

    $python = Get-Command python -ErrorAction SilentlyContinue
    if ($python) { return @($python.Source) }

    $py = Get-Command py -ErrorAction SilentlyContinue
    if ($py) { return @($py.Source, "-3") }

    throw "Python was not found. Pass -PythonPath, set GEN_UNI_PYTHON, or run the verifier setup."
}

function Invoke-Python {
    param([string[]]$ArgsList)

    if ($pythonCmd.Length -gt 1) {
        & $pythonCmd[0] $pythonCmd[1] @ArgsList
    } else {
        & $pythonCmd[0] @ArgsList
    }
}

Set-Location -LiteralPath $RepoRoot

$pythonCmd = @(Get-PythonCommand)

if ($Audit) {
    Invoke-Python @($BankScript, "--audit")
    exit $LASTEXITCODE
}

$argsList = @($GenScript)

if ($List) {
    Invoke-Python ($argsList + "--list-groups")
    exit $LASTEXITCODE
}

if (-not [string]::IsNullOrWhiteSpace($ContextGroup)) {
    $argsList += @("--group", $ContextGroup)
}

if ($NoTree) {
    $argsList += "--no-tree"
}

if ($IncludeArchived) {
    $argsList += "--include-archived"
}

if ($BudgetKb -gt 0) {
    $argsList += @("--budget-kb", [string]$BudgetKb)
}

if ($Save) {
    if (-not (Test-Path -LiteralPath $ContextDir)) {
        New-Item -ItemType Directory -Path $ContextDir | Out-Null
    }

    $safeName = Get-SafeName $ContextGroup
    $outFile = Join-Path $ContextDir "$safeName-context.txt"
    $argsList += @("--out", $outFile)
    Invoke-Python $argsList
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    Write-Host "Saved context to $outFile"
    if ($Open) {
        if ($IsWindows -or $env:OS -eq "Windows_NT") {
            Start-Process -FilePath $outFile
        } elseif ($IsMacOS) {
            & open $outFile
        } else {
            & xdg-open $outFile
        }
    }
    exit 0
}

$argsList += @("--out", "-")
Invoke-Python $argsList
exit $LASTEXITCODE

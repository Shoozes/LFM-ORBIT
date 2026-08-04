# File: .tools/gitpush.ps1
param(
    [string]$Remote = "",
    [string]$Message,
    [switch]$StageAll,
    [switch]$Yes,
    [switch]$ImportOnly
)

$ErrorActionPreference = "Stop"
$env:GIT_TERMINAL_PROMPT = "0"

function Read-FirstLine([string]$path) {
    if (!(Test-Path -LiteralPath $path)) { throw "Missing $path" }
    $line = (Get-Content -LiteralPath $path -TotalCount 1)
    $line = $line -replace ([string][char]0xFEFF),""
    $line = $line.Trim()
    if ([string]::IsNullOrWhiteSpace($line)) { throw "$path is empty" }
    return $line
}

function Read-JsonFile([string]$path) {
    if (!(Test-Path -LiteralPath $path)) { return $null }
    try {
        $raw = Get-Content -LiteralPath $path -Raw -Encoding UTF8
        if ([string]::IsNullOrWhiteSpace($raw)) { return $null }
        return ($raw | ConvertFrom-Json)
    } catch {
        throw "Failed to read JSON: $path"
    }
}

function Get-RelPathPosix([string]$BaseDir, [string]$FullPath) {
    $base = (Resolve-Path -LiteralPath $BaseDir).Path.TrimEnd('\')
    $full = (Resolve-Path -LiteralPath $FullPath).Path
    if ($full.Length -ge $base.Length -and $full.Substring(0, $base.Length).Equals($base, [System.StringComparison]::OrdinalIgnoreCase)) {
        $rel = $full.Substring($base.Length).TrimStart('\')
        return ($rel -replace '\\','/')
    }
    return ($FullPath -replace '\\','/')
}

function Resolve-TokenInfo {
    param(
        [string]$RepoRoot,
        [string]$SecretsDir,
        [string]$TokenFile
    )

    $candidates = @()

    if (-not [string]::IsNullOrWhiteSpace($SecretsDir)) {
        $candidates += (Join-Path $RepoRoot (Join-Path $SecretsDir $TokenFile))
    }

    $candidates += (Join-Path $RepoRoot (Join-Path (Join-Path ".tools" ".secrets") $TokenFile))
    $candidates += (Join-Path $RepoRoot (Join-Path ".secrets" $TokenFile))

    $candidates = $candidates | Select-Object -Unique

    foreach ($p in $candidates) {
        if (Test-Path -LiteralPath $p) {
            $rel = Get-RelPathPosix -BaseDir $RepoRoot -FullPath $p
            $dirRel = ($rel -replace '/[^/]+$','')
            return [pscustomobject]@{
                TokenPath     = $p
                TokenRel      = $rel
                SecretsDirRel = $dirRel
            }
        }
    }

    $msg = "Missing token file. Looked for:`n"
    foreach ($p in $candidates) { $msg += " - $p`n" }
    $msg += "Fix: put gt.txt under .tools/.secrets/ or set .tools/project.json paths.secretsDir to '.tools/.secrets'."
    throw $msg
}

function Confirm-OrExit {
    param([string]$Prompt, [string]$Expected = "YES")
    if ($Yes) { return }
    $ans = Read-Host "$Prompt Type $Expected to continue"
    if ($ans -ne $Expected) {
        Write-Host "Canceled."
        exit 0
    }
}

function Get-ProjectDefaultBranch {
    param([object]$Project)
    if ($Project -and $Project.git -and $Project.git.defaultBranch) {
        $value = [string]$Project.git.defaultBranch
        if (-not [string]::IsNullOrWhiteSpace($value)) { return $value.Trim() }
    }
    return "main"
}

function Get-CurrentGitBranch {
    try {
        $value = (& git rev-parse --abbrev-ref HEAD 2>$null).Trim()
        if (-not [string]::IsNullOrWhiteSpace($value)) { return $value }
    } catch {}
    return ""
}

function Ensure-ConcreteBranch {
    param([object]$Project)

    $branch = Get-CurrentGitBranch
    if (-not [string]::IsNullOrWhiteSpace($branch) -and $branch -ne "HEAD") {
        return $branch
    }

    $branch = Get-ProjectDefaultBranch -Project $Project
    throw "Detached HEAD detected; '$branch' was not moved automatically. Inspect with 'git branch --contains HEAD', then run 'git switch <branch>' or 'git switch -c <new-branch>' explicitly."
}

function Set-UpstreamIfRemoteBranchExists {
    param([string]$Branch)
    & git show-ref --verify --quiet "refs/remotes/origin/$Branch"
    if ($LASTEXITCODE -eq 0) {
        & git branch --set-upstream-to="origin/$Branch" $Branch *>$null
    }
}

function Invoke-Git {
    param([scriptblock]$Command)
    $backup = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    $out = & $Command 2>&1
    $code = $LASTEXITCODE
    $ErrorActionPreference = $backup
    if ($null -eq $out) { $out = [string[]]@() } else { $out = [string[]]@($out | ForEach-Object { "$_" }) }
    if ($null -eq $code) { $code = 0 }
    [pscustomobject]@{ Output = $out; ExitCode = $code }
}

function Assert-NoGitOperationInProgress {
    $states = @()
    $statePaths = @{
        'rebase-merge' = 'rebase'
        'rebase-apply' = 'rebase'
        'MERGE_HEAD' = 'merge'
        'CHERRY_PICK_HEAD' = 'cherry-pick'
        'REVERT_HEAD' = 'revert'
    }
    foreach ($entry in $statePaths.GetEnumerator()) {
        $path = Invoke-Git { git @('rev-parse', '--git-path', $entry.Key) }
        $resolved = [string]($path.Output | Select-Object -First 1)
        if ($path.ExitCode -eq 0 -and -not [string]::IsNullOrWhiteSpace($resolved) -and (Test-Path -LiteralPath $resolved)) {
            $states += $entry.Value
        }
    }

    # Git may emit benign environment warnings (for example, an unreadable
    # global excludes file) on stderr. They are not unresolved paths.
    $unmerged = Invoke-Git { git @('diff', '--name-only', '--diff-filter=U') 2>$null }
    if ($unmerged.ExitCode -ne 0) {
        throw "Could not inspect the index for unresolved conflicts: $($unmerged.Output -join [Environment]::NewLine)"
    }
    $unmergedPaths = @($unmerged.Output | Where-Object { -not [string]::IsNullOrWhiteSpace([string]$_) })
    if ($unmergedPaths.Count -gt 0) { $states += 'unresolved index conflicts' }

    $states = @($states | Sort-Object -Unique)
    if ($states.Count -gt 0) {
        throw "Existing Git state was left unchanged: $($states -join ', '). Run 'git status', then continue or abort that operation explicitly before syncing."
    }
}

function Invoke-RequestedStaging {
    param([switch]$StageAll)

    if ($StageAll) {
        $add = Invoke-Git { git add -A }
        if ($add.ExitCode -ne 0) {
            throw "Could not stage all working-tree changes: $($add.Output -join [Environment]::NewLine)"
        }
        return
    }

    $status = Invoke-Git { git status --porcelain }
    if ($status.ExitCode -ne 0) {
        throw "Could not inspect the working tree: $($status.Output -join [Environment]::NewLine)"
    }
    $hasUnstaged = @($status.Output | Where-Object {
        $line = [string]$_
        $line.StartsWith('??') -or ($line.Length -gt 1 -and $line[1] -ne ' ')
    }).Count -gt 0
    if ($hasUnstaged) {
        Write-Warning "Unstaged or untracked changes are not included. Stage reviewed paths explicitly or rerun with -StageAll."
    }
}

function Invoke-SafeRebase {
    param(
        [Parameter(Mandatory = $true)][string]$Upstream,
        [string[]]$GitConfig = @(),
        [switch]$AutoStash
    )

    $gitArgs = @()
    foreach ($config in $GitConfig) {
        if (-not [string]::IsNullOrWhiteSpace($config)) {
            $gitArgs += @('-c', $config)
        }
    }
    $gitArgs += 'rebase'
    if ($AutoStash) { $gitArgs += '--autostash' }
    $gitArgs += $Upstream

    $rebase = Invoke-Git { git @gitArgs }
    if ($rebase.ExitCode -eq 0) { return }

    if ((Test-Path ".git/rebase-merge") -or (Test-Path ".git/rebase-apply")) {
        Invoke-Git { git rebase --abort } | Out-Null
    }
    $details = $rebase.Output -join [Environment]::NewLine
    throw "Rebase failed and was aborted without moving branch refs or choosing a conflict side. Review with 'git log --left-right --graph HEAD...$Upstream', resolve deliberately, then rerun.`n$details"
}

function Assert-NoOversizedTrackedFiles {
    param(
        [string]$RepoRoot,
        [int64]$LimitBytes = 95MB
    )

    $tracked = & git ls-files -z 2>$null
    if (-not $tracked) {
        return
    }

    $oversized = New-Object System.Collections.Generic.List[object]

    foreach ($path in ($tracked -split "`0" | Where-Object { $_ })) {
        $fullPath = Join-Path $RepoRoot ($path -replace '/', '\')
        if (-not (Test-Path -LiteralPath $fullPath)) {
            continue
        }

        $item = Get-Item -LiteralPath $fullPath -ErrorAction SilentlyContinue
        if ($null -eq $item -or $item.PSIsContainer) {
            continue
        }

        if ($item.Length -ge $LimitBytes) {
            [void]$oversized.Add([pscustomobject]@{
                Path = $path
                SizeMB = [math]::Round($item.Length / 1MB, 2)
            })
        }
    }

    if ($oversized.Count -gt 0) {
        $details = ($oversized | ForEach-Object { " - $($_.Path) [$($_.SizeMB) MB]" }) -join [Environment]::NewLine
        throw "Tracked files exceed the GitHub-safe size threshold (${LimitBytes} bytes). Remove them from git or ignore them before pushing:`n$details"
    }
}

if ($ImportOnly) { return }

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location -Path $RepoRoot

$ProjectPath = Join-Path $RepoRoot ".tools\project.json"
$Project = Read-JsonFile $ProjectPath

if ([string]::IsNullOrWhiteSpace($Remote)) {
    $cfgRemote = $null
    if ($Project -and $Project.git -and $Project.git.remote) { $cfgRemote = [string]$Project.git.remote }
    if (-not [string]::IsNullOrWhiteSpace($cfgRemote)) {
        $Remote = $cfgRemote
    } else {
        throw "Remote not provided and .tools/project.json missing git.remote"
    }
}

$secretsDir = ".secrets"
$tokenFile = "gt.txt"
if ($Project -and $Project.paths) {
    if ($Project.paths.secretsDir) { $secretsDir = [string]$Project.paths.secretsDir }
    if ($Project.paths.tokenFile) { $tokenFile = [string]$Project.paths.tokenFile }
}

Confirm-OrExit -Prompt "Proceed with git commit/sync/push?" -Expected "YES"

$tokenInfo = Resolve-TokenInfo -RepoRoot $RepoRoot -SecretsDir $secretsDir -TokenFile $tokenFile
$tokenPath = $tokenInfo.TokenPath
$tokenRel = $tokenInfo.TokenRel
$secretsDirRel = $tokenInfo.SecretsDirRel

$token = Read-FirstLine $tokenPath

if (!(Test-Path ".git")) {
    try { & git init -b main | Out-Null } catch { & git init | Out-Null; & git checkout -b main | Out-Null }
}

$branch = Ensure-ConcreteBranch -Project $Project
Write-Host "Using branch '$branch' for commit/sync/push."
Assert-NoGitOperationInProgress

$gitDir = ((git rev-parse --git-dir).Trim())
if (-not (Test-Path $gitDir)) { throw "git dir not found: $gitDir" }
$excludePath = Join-Path $gitDir "info/exclude"
if (!(Test-Path $excludePath)) {
    New-Item -ItemType Directory -Path (Split-Path $excludePath) -Force | Out-Null
    New-Item -ItemType File -Path $excludePath | Out-Null
}
$excludeLines = Get-Content $excludePath -ErrorAction SilentlyContinue
$need = @("$secretsDirRel/", "$secretsDirRel/$tokenFile", ".gtignore", "*.gtignore")
$toAppend = $need | Where-Object { $_ -notin $excludeLines }
if ($toAppend.Count -gt 0) { Add-Content -Path $excludePath -Value ($toAppend -join [Environment]::NewLine) }

$tracked = & git ls-files -z -- "$tokenRel" '.gtignore' '*.gtignore' 2>$null
if ($tracked) {
    $trackedPaths = ($tracked -split "`0" | Where-Object { $_ }) -join ', '
    throw "Sensitive helper files are tracked and were left unchanged: $trackedPaths. Review them, then run 'git rm --cached -- <path>' and commit that removal explicitly before syncing."
}

Invoke-RequestedStaging -StageAll:$StageAll
Assert-NoOversizedTrackedFiles -RepoRoot $RepoRoot
$pending = (& git diff --cached --name-only | Out-String).Trim()
$didCommit = $false

if ([string]::IsNullOrWhiteSpace($pending)) {
    Write-Host "Nothing to commit. Proceeding to sync with remote."
} else {
    if (-not $Message) { $Message = "chore: update $(Get-Date -Format s)" }
    & git commit -m $Message
    if ($LASTEXITCODE -ne 0) { throw "Commit failed. Fix errors above and retry." }
    $didCommit = $true
}

$pair = "x-access-token:$token"
$basic = [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes($pair))
$authCfg = "http.https://github.com/.extraheader=Authorization: Basic $basic"
$noCredHelper = "credential.helper="

$originUrl = ""
try { $originUrl = (& git remote get-url origin).Trim() } catch {}
if ([string]::IsNullOrWhiteSpace($originUrl)) { & git remote add origin $Remote | Out-Null }
elseif ($originUrl -ne $Remote) { & git remote set-url origin $Remote | Out-Null }

if ($Remote -notmatch "github\.com[:/](?<owner>[^/]+)/(?<repo>[^\.]+)(?:\.git)?$") {
    throw "Remote is not a valid GitHub HTTPS URL: $Remote"
}
$owner = $Matches.owner
$repo = $Matches.repo

$ghHeaders = @{
    "Authorization"        = "Bearer $token"
    "Accept"               = "application/vnd.github+json"
    "X-GitHub-Api-Version" = "2022-11-28"
    "User-Agent"           = "gitpush.ps1"
}

$authUser = $null
try {
    $authUser = Invoke-RestMethod -Method GET -Headers $ghHeaders -Uri "https://api.github.com/user"
} catch {
    throw "GitHub auth failed (401). Fix $tokenPath and retry."
}

$repoExists = $false
try {
    Invoke-RestMethod -Method GET -Headers $ghHeaders -Uri "https://api.github.com/repos/$owner/$repo" | Out-Null
    $repoExists = $true
} catch { $repoExists = $false }

if (-not $repoExists) {
    $ownerMeta = Invoke-RestMethod -Method GET -Uri "https://api.github.com/users/$owner"
    $isOrg = ($ownerMeta.type -eq "Organization")

    if (-not $isOrg -and $authUser.login -ne $owner) {
        throw "Token user '$($authUser.login)' does not match remote owner '$owner'. Use a token from '$owner' or change Remote."
    }

    $body = @{ name = $repo; private = $true } | ConvertTo-Json
    if ($isOrg) {
        Invoke-RestMethod -Method POST -Headers $ghHeaders -ContentType 'application/json' -Uri "https://api.github.com/orgs/$owner/repos" -Body $body | Out-Null
    } else {
        Invoke-RestMethod -Method POST -Headers $ghHeaders -ContentType 'application/json' -Uri "https://api.github.com/user/repos" -Body $body | Out-Null
    }
    Write-Host "Created repo $owner/$repo"
}

& git @('-c', $authCfg, '-c', $noCredHelper, 'fetch', '--prune', 'origin') | Out-Null

$remoteHasBranch = $false
& git -c $authCfg -c $noCredHelper ls-remote --exit-code --heads origin $branch *>$null
if ($LASTEXITCODE -eq 0) {
    $remoteHasBranch = $true
    Set-UpstreamIfRemoteBranchExists -Branch $branch
}

$syncMsg = if ($didCommit -and $Message) { $Message } else { "no new commit" }

if (-not $remoteHasBranch) {
    & git @('-c', $authCfg, '-c', $noCredHelper, 'push', '-u', 'origin', $branch)
    if ($LASTEXITCODE -ne 0) { throw "Initial push failed. Check token/permissions/remote." }
    Write-Host "Pushed initial $branch to origin (message: $syncMsg)"
} else {
    Invoke-SafeRebase -Upstream "origin/$branch" -GitConfig @($authCfg, $noCredHelper) -AutoStash

    & git @('-c', $authCfg, '-c', $noCredHelper, 'push', '-u', 'origin', $branch)
    if ($LASTEXITCODE -ne 0) { throw "Push failed after sync. Check branch protections or permissions." }
    Write-Host "Synced $branch with origin (message: $syncMsg)"
}

Write-Host "Connector review branch: $branch"
& git status --short --branch

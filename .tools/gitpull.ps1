# File: .tools/gitpull.ps1
param(
    [string]$Remote = "",
    [switch]$Force,
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

    $unmerged = Invoke-Git { git @('diff', '--name-only', '--diff-filter=U') }
    if ($unmerged.ExitCode -ne 0) {
        throw "Could not inspect the index for unresolved conflicts: $($unmerged.Output -join [Environment]::NewLine)"
    }
    if ($unmerged.Output.Count -gt 0) { $states += 'unresolved index conflicts' }

    $states = @($states | Sort-Object -Unique)
    if ($states.Count -gt 0) {
        throw "Existing Git state was left unchanged: $($states -join ', '). Run 'git status', then continue or abort that operation explicitly before syncing."
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

function New-GitSyncStash {
    param([Parameter(Mandatory = $true)][string]$Message)

    $stash = Invoke-Git { git @('stash', 'push', '-m', $Message) }
    if ($stash.ExitCode -ne 0) {
        throw "Could not preserve local changes before pull: $($stash.Output -join [Environment]::NewLine)"
    }
    if ($stash.Output -join ' ' -match 'No local changes to save') { return $null }

    $object = Invoke-Git { git @('rev-parse', '--verify', 'stash@{0}') }
    if ($object.ExitCode -ne 0 -or $object.Output.Count -eq 0) {
        throw "Git reported a successful stash but its object could not be verified."
    }
    $objectId = [string]($object.Output | Select-Object -First 1)
    [pscustomobject]@{
        Ref = 'stash@{0}'
        ObjectId = $objectId.Trim()
    }
}

function Restore-GitSyncStash {
    param([Parameter(Mandatory = $true)][object]$Stash)

    $current = Invoke-Git { git @('rev-parse', '--verify', $Stash.Ref) }
    $currentObjectId = [string]($current.Output | Select-Object -First 1)
    if ($current.ExitCode -ne 0 -or [string]::IsNullOrWhiteSpace($currentObjectId) -or $currentObjectId.Trim() -ne $Stash.ObjectId) {
        throw "The safety stash is no longer at $($Stash.Ref); it was not applied or dropped. Restore object $($Stash.ObjectId) manually."
    }

    $pop = Invoke-Git { git stash pop $Stash.Ref }
    if ($pop.ExitCode -ne 0) {
        $preserved = Invoke-Git { git @('cat-file', '-e', "$($Stash.ObjectId)^{commit}") }
        if ($preserved.ExitCode -ne 0) {
            throw "Stash restore conflicted and the safety object could not be verified. Stop and inspect the repository before continuing."
        }
        throw "Stash restore conflicted. Safety stash $($Stash.ObjectId) was preserved and both index sides remain available. Run 'git status', resolve and stage reviewed files, then verify '$($Stash.Ref)' still resolves to that object before dropping it manually."
    }
}

function Restore-RemoteMissingFiles {
    param([string]$Branch)

    $remoteFiles = (& git ls-tree -r --name-only "origin/$Branch" 2>$null) | Where-Object { $_ }
    if (-not $remoteFiles) { return }

    $repoRoot = (Get-Location).ProviderPath
    $missing = @()

    foreach ($rf in $remoteFiles) {
        $localRel = $rf -replace '/', '\'
        $fullPath = Join-Path $repoRoot $localRel
        if (-not (Test-Path -LiteralPath $fullPath)) {
            $missing += [pscustomobject]@{ Remote = $rf; LocalRel = $localRel; FullPath = $fullPath }
        }
    }

    if ($missing.Count -eq 0) { return }

    Write-Host "Restoring $($missing.Count) missing tracked file(s) from origin/$Branch"
    foreach ($m in $missing) {
        $dir = Split-Path -Parent $m.FullPath
        if ($dir -and -not (Test-Path -LiteralPath $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
        $res = Invoke-Git { git @('checkout', "origin/$Branch", '--', $m.Remote) }
        if ($res.ExitCode -ne 0) { Write-Warning ("Failed to restore {0}: {1}" -f $m.Remote, ($res.Output -join ' ')) }
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

if ($Force) {
    Confirm-OrExit -Prompt "Force pull will discard local changes and untracked files." -Expected "FORCE"
} else {
    Confirm-OrExit -Prompt "Proceed with git pull/rebase/merge?" -Expected "YES"
}

$tokenInfo = Resolve-TokenInfo -RepoRoot $RepoRoot -SecretsDir $secretsDir -TokenFile $tokenFile
$tokenPath = $tokenInfo.TokenPath
$tokenRel = $tokenInfo.TokenRel
$secretsDirRel = $tokenInfo.SecretsDirRel

$token = Read-FirstLine $tokenPath

if (!(Test-Path ".git")) { throw "No local git repo found. Initialize or clone first." }

$branch = Ensure-ConcreteBranch -Project $Project
Write-Host "Using branch '$branch' for pull/sync."
Assert-NoGitOperationInProgress

$excludePath = ".git/info/exclude"
if (!(Test-Path $excludePath)) { New-Item -ItemType File -Path $excludePath | Out-Null }
$excludeLines = Get-Content $excludePath -ErrorAction SilentlyContinue
$need = @("$secretsDirRel/", "$secretsDirRel/$tokenFile", ".gtignore", "*.gtignore")
$toAppend = $need | Where-Object { $_ -notin $excludeLines }
if ($toAppend.Count -gt 0) { Add-Content -Path $excludePath -Value ($toAppend -join [Environment]::NewLine) }

$tracked = & git ls-files -z -- "$tokenRel" '.gtignore' '*.gtignore' 2>$null
if ($tracked) {
    $trackedPaths = ($tracked -split "`0" | Where-Object { $_ }) -join ', '
    throw "Sensitive helper files are tracked and were left unchanged: $trackedPaths. Review them, then run 'git rm --cached -- <path>' and commit that removal explicitly before syncing."
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
    "User-Agent"           = "gitpull.ps1"
}

$apiOk = $true
try {
    Invoke-RestMethod -Method GET -Headers $ghHeaders -Uri "https://api.github.com/user" | Out-Null
    Invoke-RestMethod -Method GET -Headers $ghHeaders -Uri "https://api.github.com/repos/$owner/$repo" | Out-Null
} catch {
    Write-Warning "GitHub API check failed (likely 401). We will try pure git using the token header."
    $apiOk = $false
}

$fetch = Invoke-Git { git @('-c', $authCfg, '-c', $noCredHelper, 'fetch', '--prune', 'origin') }
if ($fetch.ExitCode -ne 0) { throw "Fetch failed with exit code $($fetch.ExitCode): $($fetch.Output -join [Environment]::NewLine)" }

if ($Force) {
    $reset = Invoke-Git { git @('reset', '--hard', "origin/$branch") }
    if ($reset.ExitCode -ne 0) { throw "Force reset failed: $($reset.Output -join [Environment]::NewLine)" }
    $clean = Invoke-Git { git @('clean', '-fdx') }
    if ($clean.ExitCode -ne 0) { throw "Force clean failed: $($clean.Output -join [Environment]::NewLine)" }
    Restore-RemoteMissingFiles -Branch $branch
    Write-Host "Force-synced $branch from origin (reset --hard + clean -fdx)."
    return
}

$remoteBranch = Invoke-Git { git @('-c', $authCfg, '-c', $noCredHelper, 'ls-remote', '--exit-code', '--heads', 'origin', $branch) }
if ($remoteBranch.ExitCode -ne 0) {
    if ($apiOk) { throw "Remote branch $branch does not exist. Cannot pull." }
    throw "Remote branch $branch not visible to this token. Regenerate PAT with access to $owner/$repo."
}
Set-UpstreamIfRemoteBranchExists -Branch $branch

$stashMsg = "auto-stash before pull $(Get-Date -Format o)"
$safetyStash = New-GitSyncStash -Message $stashMsg

try {
    Invoke-SafeRebase -Upstream "origin/$branch" -GitConfig @($authCfg, $noCredHelper)
} catch {
    if ($null -ne $safetyStash) {
        throw "$($_.Exception.Message)`nLocal edits remain in safety stash $($safetyStash.ObjectId). After resolving the divergence, restore them with 'git stash apply $($safetyStash.Ref)' and do not drop the stash until the result is reviewed."
    }
    throw
}

if ($null -ne $safetyStash) { Restore-GitSyncStash -Stash $safetyStash }

Restore-RemoteMissingFiles -Branch $branch
Write-Host "Pulled and synced $branch from origin"
Write-Host "Connector review branch: $branch"
& git status --short --branch

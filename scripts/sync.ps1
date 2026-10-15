param([ValidateSet('pull','push','status')][string]$Action = 'status', [string]$Message = 'Update personal workspace')
$ErrorActionPreference='Stop'
Set-Location -LiteralPath (Split-Path -Parent $PSScriptRoot)
function Check-Exit { if ($LASTEXITCODE -ne 0) { throw "同步中止，退出码 $LASTEXITCODE。" } }
git status --short
Check-Exit
if ($Action -eq 'status') { exit 0 }
$repositoryJson = gh repo view --json nameWithOwner,visibility
Check-Exit
$repository = $repositoryJson | ConvertFrom-Json
if ($repository.nameWithOwner -ne 'sunjinhui0902/scys_jh' -or $repository.visibility -ne 'PUBLIC') { throw '仓库身份或公开状态与用户约定不符，停止同步。' }
if ($Action -eq 'pull') {
    if (git status --porcelain) { throw '有未提交改动，请先保存并推送，避免覆盖。' }
    git pull --ff-only
    Check-Exit
} else {
    git add -A
    Check-Exit
    $syncPython = Join-Path (Get-Location) '.venv\Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $syncPython)) { $syncPython='python' }
    & $syncPython scripts/check_secrets.py --staged
    Check-Exit
    git diff --cached --quiet
    if ($LASTEXITCODE -eq 1) { git commit -m $Message; Check-Exit }
    elseif ($LASTEXITCODE -ne 0) { throw '无法检查暂存改动。' }
    git pull --ff-only
    Check-Exit
    git push
    Check-Exit
}

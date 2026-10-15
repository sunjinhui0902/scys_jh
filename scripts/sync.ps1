param([ValidateSet('pull','push','status')][string]$Action = 'status', [string]$Message = 'Update personal workspace')
$ErrorActionPreference='Stop'
Set-Location -LiteralPath (Split-Path -Parent $PSScriptRoot)
function Check-Exit { if ($LASTEXITCODE -ne 0) { throw "同步中止，退出码 $LASTEXITCODE。" } }
git status --short
Check-Exit
if ($Action -eq 'status') { exit 0 }
$privacy = gh repo view --json isPrivate --jq '.isPrivate'
Check-Exit
if ($privacy -ne 'true') { throw '仓库不是私有状态，停止同步。' }
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

param([switch]$InstallSoftware, [switch]$RestoreAssets, [switch]$Full, [switch]$Analysis)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
function Check-Exit { if ($LASTEXITCODE -ne 0) { throw "上一步操作失败，退出码 $LASTEXITCODE。" } }
if ($InstallSoftware) {
    foreach ($packageId in @('Git.Git','GitHub.cli','Python.Python.3.10')) {
        winget install --id $packageId --exact --source winget --accept-package-agreements --accept-source-agreements --disable-interactivity
        if ($LASTEXITCODE -ne 0 -and $LASTEXITCODE -ne -1978335189) { throw "安装 $packageId 失败，请重新打开终端后重试。" }
    }
    $env:Path = [Environment]::GetEnvironmentVariable('Path','Machine') + ';' + [Environment]::GetEnvironmentVariable('Path','User')
}
if (-not (Get-Command git -ErrorAction SilentlyContinue)) { throw '缺少 Git，请先运行：powershell -ExecutionPolicy Bypass -File scripts/setup.ps1 -InstallSoftware' }
if (-not (Get-Command gh -ErrorAction SilentlyContinue)) { throw '缺少 GitHub CLI，请先用 -InstallSoftware 安装。' }
$venvPython = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $venvPython)) {
    if (Get-Command py -ErrorAction SilentlyContinue) { py -3.10 -m venv .venv; Check-Exit }
    else { throw '缺少 Python 3.10，请先用 -InstallSoftware 安装。' }
}
& $venvPython -m pip install -r requirements-core.lock.txt
Check-Exit
if ($Analysis) {
    & $venvPython -m pip install -r requirements-analysis.txt
    Check-Exit
}
if (-not (Test-Path -LiteralPath '.env')) { Copy-Item -LiteralPath '.env.example' -Destination '.env' }
if ($RestoreAssets -or $Full) {
    gh auth status 2>$null
    if ($LASTEXITCODE -ne 0) { gh auth login --web --git-protocol https; Check-Exit }
    if ($Full) { & $venvPython scripts/bundle.py restore --group all }
    else { & $venvPython scripts/bundle.py restore --group core --group software }
    Check-Exit
}
# Independent downloader config, never copy the previous machine's login state.
$wxDir = Join-Path $projectRoot '00_对标与采集工具\wx_channel'
if ((Test-Path -LiteralPath $wxDir) -and -not (Test-Path -LiteralPath (Join-Path $wxDir 'config.yaml'))) {
    "cloud_enabled: false`nauto_open_channels: false`ncloud_secret: ''`nmachine_id: ''`n" | Set-Content -LiteralPath (Join-Path $wxDir 'config.yaml') -Encoding UTF8
}
& $venvPython scripts/relocate.py
Check-Exit
& $venvPython scripts/doctor.py --strict
Check-Exit
Write-Host '准备完成。运行 工作台.bat，或在 Codex 中打开本目录。'

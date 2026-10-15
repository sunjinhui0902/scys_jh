<#
.SYNOPSIS
    同步个人知识库内容到云端硬盘。
.DESCRIPTION
    读取 .env 或环境变量 SCYS_GDRIVE_TARGET，增量同步知识库文档并更新索引清单。
.PARAMETER Target
    可选。手动指定目标云端硬盘路径。
.PARAMETER DryRun
    可选。试运行模式，不实际写入。
.PARAMETER VerboseOutput
    可选。输出详细复制信息。
#>
param(
    [string]$Target,
    [switch]$DryRun,
    [switch]$VerboseOutput,
    [switch]$IncludeBooks
)

$ErrorActionPreference = 'Stop'
$ScriptDir = $PSScriptRoot
$ProjectRoot = Split-Path -Parent $ScriptDir
Set-Location -LiteralPath $ProjectRoot

# Set UTF-8 encoding for output
$env:PYTHONIOENCODING = 'utf-8'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::InputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8


$PythonExe = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $PythonExe)) {
    $PythonExe = 'python'
}

$PyScript = Join-Path $ScriptDir 'sync_to_gdrive.py'
$PyArgs = @($PyScript)

if ($Target) {
    $PyArgs += @('--target', $Target)
}
if ($DryRun) {
    $PyArgs += '--dry-run'
}
if ($VerboseOutput) {
    $PyArgs += '--verbose'
}
if ($IncludeBooks) {
    $PyArgs += '--include-books'
}

& $PythonExe @PyArgs
exit $LASTEXITCODE

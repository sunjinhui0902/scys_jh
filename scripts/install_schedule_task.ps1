<#
.SYNOPSIS
    管理每天早上 7 点自动同步知识库到云端硬盘的 Windows 计划任务。
.DESCRIPTION
    创建、查看、运行或卸载 Windows 任务计划程序中的同步任务。
.PARAMETER Action
    操作：install（安装/更新）、uninstall（卸载）、status（状态检查）、run（立即触发一次）。
.PARAMETER Time
    计划触发时间，默认为 '07:00'（早上7点）。
.PARAMETER TaskName
    计划任务名称，默认为 'scys_jh_sync_knowledge_gdrive'。
#>
param(
    [ValidateSet('install', 'uninstall', 'status', 'run')]
    [string]$Action = 'install',

    [string]$Time = '07:00',

    [string]$TaskName = 'scys_jh_sync_knowledge_gdrive'
)

$ErrorActionPreference = 'Stop'
$ScriptDir = $PSScriptRoot
$ProjectRoot = Split-Path -Parent $ScriptDir
Set-Location -LiteralPath $ProjectRoot

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

$SyncPs1 = Join-Path $ScriptDir 'sync_to_gdrive.ps1'

switch ($Action) {
    'install' {
        Write-Host "正在注册 Windows 每日定时计划任务 [$TaskName]..." -ForegroundColor Cyan
        
        $actionObj = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-WindowStyle Hidden -NoProfile -ExecutionPolicy Bypass -File `"$SyncPs1`""
        $triggerObj = New-ScheduledTaskTrigger -Daily -At $Time
        $settingsObj = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
        $desc = "每天 $Time 自动增量同步 scys_jh 项目知识库内容到云端硬盘 (Google Drive)"

        Register-ScheduledTask -TaskName $TaskName -Action $actionObj -Trigger $triggerObj -Settings $settingsObj -Description $desc -Force | Out-Null
        
        Write-Host "成功注册计划任务！" -ForegroundColor Green
        Write-Host "任务名称:   $TaskName"
        Write-Host "执行时间:   每天 $Time"
        Write-Host "执行脚本:   $SyncPs1"
        Write-Host "特性设置:   支持电池供电运行、关机错过后开机自动补跑 (StartWhenAvailable)"
        
        $task = Get-ScheduledTask -TaskName $TaskName
        $info = Get-ScheduledTaskInfo -TaskName $TaskName
        Write-Host "`n当前任务状态:" -ForegroundColor Cyan
        Write-Host "状态:       $($task.State)"
        Write-Host "下次运行:   $($info.NextRunTime)"
    }

    'status' {
        $task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
        if (-not $task) {
            Write-Host "计划任务 [$TaskName] 尚未注册。" -ForegroundColor Yellow
            exit 0
        }
        $info = Get-ScheduledTaskInfo -TaskName $TaskName
        Write-Host "计划任务 [$TaskName] 当前状态:" -ForegroundColor Cyan
        Write-Host "任务状态:   $($task.State)"
        Write-Host "描述:       $($task.Description)"
        Write-Host "下次运行:   $($info.NextRunTime)"
        Write-Host "上次运行:   $($info.LastRunTime)"
        Write-Host "上次结果:   $($info.LastTaskResult)"
    }

    'run' {
        Write-Host "正在立即触发计划任务 [$TaskName]..." -ForegroundColor Cyan
        Start-ScheduledTask -TaskName $TaskName
        Start-Sleep -Seconds 2
        $info = Get-ScheduledTaskInfo -TaskName $TaskName
        Write-Host "任务已触发！" -ForegroundColor Green
        Write-Host "上次运行时间: $($info.LastRunTime)"
        Write-Host "上次结果代码: $($info.LastTaskResult)"
    }

    'uninstall' {
        $task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
        if ($task) {
            Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
            Write-Host "计划任务 [$TaskName] 已成功卸载。" -ForegroundColor Green
        } else {
            Write-Host "计划任务 [$TaskName] 不存在，无需卸载。" -ForegroundColor Yellow
        }
    }
}

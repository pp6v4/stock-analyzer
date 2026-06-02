# Windows计划任务配置脚本 - 以管理员身份运行
# 用法: 右键 → 使用PowerShell运行，或管理员终端执行

$projectDir = "C:\Users\10353\Desktop\stock-analyzer"
$pythonExe = (Get-Command python).Source

Write-Host "=== 配置选股系统计划任务 ===" -ForegroundColor Green
Write-Host ""
Write-Host "项目目录: $projectDir"
Write-Host "Python: $pythonExe"
Write-Host ""

# 任务1: 每日选股 - 14:30
$task1Name = "StockPick_Daily_1430"
$task1Action = New-ScheduledTaskAction -Execute $pythonExe `
    -Argument "daily_pick.py" `
    -WorkingDirectory $projectDir
$task1Trigger = New-ScheduledTaskTrigger -Daily -At "14:30"
$task1Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -MultipleInstances IgnoreNew

try {
    Register-ScheduledTask -TaskName $task1Name -Action $task1Action -Trigger $task1Trigger -Settings $task1Settings -Description "每日14:30 A股选股(选5只标的)" -Force
    Write-Host "[OK] 每日选股 14:30" -ForegroundColor Green
} catch {
    Write-Host "[FAIL] 每日选股: $_" -ForegroundColor Red
}

# 任务2: T+1回测 - 15:05 (收盘后5分钟)
$task2Name = "StockPick_Backtest_1505"
$task2Action = New-ScheduledTaskAction -Execute $pythonExe `
    -Argument "daily_backtest.py" `
    -WorkingDirectory $projectDir
$task2Trigger = New-ScheduledTaskTrigger -Daily -At "15:05"
$task2Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -MultipleInstances IgnoreNew

try {
    Register-ScheduledTask -TaskName $task2Name -Action $task2Action -Trigger $task2Trigger -Settings $task2Settings -Description "每日15:05 T+1回测" -Force
    Write-Host "[OK] T+1回测 15:05" -ForegroundColor Green
} catch {
    Write-Host "[FAIL] T+1回测: $_" -ForegroundColor Red
}

# 任务3: 周复盘 - 每周五 15:30
$task3Name = "StockPick_WeeklyReview_Fri1530"
$task3Action = New-ScheduledTaskAction -Execute $pythonExe `
    -Argument "weekly_review.py" `
    -WorkingDirectory $projectDir
$task3Trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Friday -At "15:30"
$task3Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -MultipleInstances IgnoreNew

try {
    Register-ScheduledTask -TaskName $task3Name -Action $task3Action -Trigger $task3Trigger -Settings $task3Settings -Description "每周五15:30 周复盘" -Force
    Write-Host "[OK] 周复盘 周五15:30" -ForegroundColor Green
} catch {
    Write-Host "[FAIL] 周复盘: $_" -ForegroundColor Red
}

Write-Host ""
Write-Host "=== 配置完成 ===" -ForegroundColor Green
Write-Host ""
Write-Host "查看计划任务: taskschd.msc" -ForegroundColor Yellow
Write-Host "手动运行选股: cd $projectDir; python daily_pick.py" -ForegroundColor Yellow
Write-Host "手动运行回测: cd $projectDir; python daily_backtest.py" -ForegroundColor Yellow
Write-Host ""
Write-Host "按任意键退出..."
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")

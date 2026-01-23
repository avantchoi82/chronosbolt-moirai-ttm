# Setup Windows Task Scheduler for GitQuickUpdate
# Run as: powershell -ExecutionPolicy Bypass -File setup_scheduler.ps1

$pythonw = "C:\Users\user\PycharmProjects\enssanble\.venv\Scripts\pythonw.exe"
$script = "C:\Users\user\PycharmProjects\enssanble\run_quick_update.py"
$workDir = "C:\Users\user\PycharmProjects\enssanble"

# Hours to schedule (9:03 to 16:03)
$hours = @(9, 10, 11, 12, 13, 14, 15, 16)

foreach ($hour in $hours) {
    $taskName = "GitQuickUpdate_{0:D2}" -f $hour
    $time = "{0:D2}:03" -f $hour

    # Delete existing task if exists
    schtasks /delete /tn $taskName /f 2>$null

    # Create new task
    $action = New-ScheduledTaskAction -Execute $pythonw -Argument "`"$script`"" -WorkingDirectory $workDir
    $trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday,Tuesday,Wednesday,Thursday,Friday -At $time
    $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable

    Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Force

    Write-Host "Created task: $taskName at $time (weekdays)"
}

Write-Host ""
Write-Host "All tasks registered successfully!"
Write-Host "Tasks: GitQuickUpdate_09 ~ GitQuickUpdate_16"

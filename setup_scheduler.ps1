# Setup Windows Task Scheduler for GitQuickUpdate
# Run as: powershell -ExecutionPolicy Bypass -File setup_scheduler.ps1

$pythonw = "C:\Users\user\PycharmProjects\enssanble\.venv\Scripts\pythonw.exe"
$script = "C:\Users\user\PycharmProjects\enssanble\run_quick_update.py"
$workDir = "C:\Users\user\PycharmProjects\enssanble"

# Delete existing tasks
Write-Host "Removing existing GitQuickUpdate tasks..."
Get-ScheduledTask -TaskName "GitQuickUpdate*" -ErrorAction SilentlyContinue | Unregister-ScheduledTask -Confirm:$false

# Hours to schedule (9:08 to 16:08)
$hours = @(9, 10, 11, 12, 13, 14, 15, 16)

foreach ($hour in $hours) {
    $taskName = "GitQuickUpdate_{0:D2}" -f $hour
    $time = "{0:D2}:08" -f $hour

    # Create new task
    $action = New-ScheduledTaskAction -Execute $pythonw -Argument "`"$script`"" -WorkingDirectory $workDir
    $trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday,Tuesday,Wednesday,Thursday,Friday -At $time
    $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable

    Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Force

    Write-Host "Created task: $taskName at $time (weekdays)"
}

Write-Host ""
Write-Host "All tasks registered successfully!"
Write-Host "Tasks: GitQuickUpdate_09 ~ GitQuickUpdate_16 (every hour at :08)"

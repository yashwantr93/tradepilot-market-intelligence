# Wrapper invoked by Windows Task Scheduler to run the daily pipeline unattended.
# Logs full output (with start/end timestamps) to logs\scheduled_run.log so the
# run can be audited even though Task Scheduler runs it with no visible console.
#
# Phase 11 fix: $root previously pointed at the pre-migration
# C:\Users\User\Downloads\market_intelligence_dashboard path, which no longer
# exists (the project moved to D:\Projects\Market-Intelligence-Dashboard).
# The registered "SwingTradingIntelligence_DailyRun" Task Scheduler entry's
# own Action still points at the OLD path too (this .ps1 file is a separate,
# in-repo copy) — that entry's WorkingDirectory being invalid is what has
# been causing every scheduled run to fail immediately (Task Scheduler
# LastTaskResult 2147942667 = HRESULT-wrapped Win32 error 267 "The directory
# name is invalid") since the migration, with ZERO trace of the failure in
# job_runs (PowerShell never got far enough to invoke Python at all). See
# the Phase 11 report's SCHEDULER AUDIT section — fixing the Task Scheduler
# entry itself is a system-settings change, done separately with your
# explicit approval, not by this file edit alone.
#
# Phase 11: also switched from run_daily.py (V1 only) to run_daily_all.py,
# which chains V1 -> V2 -> Event Intelligence — the three-layer refresh
# documented in the Phase 11 report's DEPENDENCY FLOW section. Before this,
# even a working scheduled task would only ever have refreshed V1.

$ErrorActionPreference = "Continue"
$root = "D:\Projects\Market-Intelligence-Dashboard"
$python = "C:\Users\User\AppData\Local\Programs\Python\Python312\python.exe"

Set-Location $root
$logDir = Join-Path $root "logs"
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir | Out-Null }
$logFile = Join-Path $logDir "scheduled_run.log"

"===== Run started: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') =====" | Add-Content -Path $logFile

& $python "run_daily_all.py" *>> $logFile
$exitCode = $LASTEXITCODE

"===== Run finished: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') (exit code $exitCode) =====`n" | Add-Content -Path $logFile

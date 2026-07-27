# Wrapper invoked by Windows Task Scheduler to run the daily pipeline unattended.
# Logs full output (with start/end timestamps) to logs\scheduled_run.log so the
# run can be audited even though Task Scheduler runs it with no visible console.

$ErrorActionPreference = "Continue"
$root = "C:\Users\User\Downloads\market_intelligence_dashboard"
$python = "C:\Users\User\AppData\Local\Programs\Python\Python312\python.exe"

Set-Location $root
$logDir = Join-Path $root "logs"
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir | Out-Null }
$logFile = Join-Path $logDir "scheduled_run.log"

"===== Run started: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') =====" | Add-Content -Path $logFile

& $python "run_daily.py" *>> $logFile
$exitCode = $LASTEXITCODE

"===== Run finished: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') (exit code $exitCode) =====`n" | Add-Content -Path $logFile

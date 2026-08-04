# launch_antigravity.ps1 — Antigravity Core Launcher
# Usage:
#   .\scripts\launch_antigravity.ps1            — start (or open browser if running)
#   .\scripts\launch_antigravity.ps1 -Restart   — kill & restart cleanly
#   .\scripts\launch_antigravity.ps1 -Stop      — kill daemon
#   .\scripts\launch_antigravity.ps1 -InstallTask  — register at Windows login
#   .\scripts\launch_antigravity.ps1 -Page gym  — open specific page

param (
    [switch]$InstallTask,
    [switch]$UninstallTask,
    [switch]$Stop,
    [switch]$Restart,
    [string]$Page = ""
)

$ProjectRoot = "c:\Users\sboopathi\projects\CryoSoftWare\antigravity_core"
$VenvPath    = "$ProjectRoot\venv"
$PythonPath  = "$VenvPath\Scripts\python.exe"
$MainScript  = "$ProjectRoot\main.py"
$Requirements = "$ProjectRoot\requirements.txt"
$TaskName    = "AntigravityCoreDaemon"

if (-not (Test-Path $ProjectRoot)) {
    Write-Host "ERROR: Project root not found at $ProjectRoot" -ForegroundColor Red
    exit 1
}

# ─── Helper: Kill process holding port 8000 ─────────────────────────────────
function Stop-DaemonOnPort {
    $pids = (Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue |
             Select-Object -ExpandProperty OwningProcess | Sort-Object -Unique)
    $killed = 0
    foreach ($p in $pids) {
        if ($p -gt 4) {
            try {
                Stop-Process -Id $p -Force -ErrorAction Stop
                Write-Host "  Stopped PID $p" -ForegroundColor Green
                $killed++
            } catch {
                cmd /c "taskkill /F /PID $p" | Out-Null
                Write-Host "  Terminated PID $p via taskkill" -ForegroundColor Green
                $killed++
            }
        }
    }
    if ($killed -eq 0) { Write-Host "  No process found on port 8000" -ForegroundColor Yellow }
    return $killed
}

# ─── InstallTask ─────────────────────────────────────────────────────────────
if ($InstallTask) {
    Write-Host "Registering '$TaskName' in Windows Task Scheduler..." -ForegroundColor Cyan
    $identity  = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        Write-Host "ERROR: Needs Administrator. Run: Start-Process powershell -Verb RunAs" -ForegroundColor Red
        exit 1
    }
    $Action   = New-ScheduledTaskAction -Execute "powershell.exe" `
                  -Argument "-WindowStyle Hidden -ExecutionPolicy Bypass -File `"$ProjectRoot\scripts\launch_antigravity.ps1`""
    $Trigger  = New-ScheduledTaskTrigger -AtLogon
    $Prin     = New-ScheduledTaskPrincipal -UserId $env:USERNAME -RunLevel Highest
    $Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
                  -ExecutionTimeLimit (New-TimeSpan -Days 365)
    Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Principal $Prin -Settings $Settings -Force
    Write-Host "Registered '$TaskName' to auto-start at Windows login." -ForegroundColor Green
    exit 0
}

# ─── UninstallTask ───────────────────────────────────────────────────────────
if ($UninstallTask) {
    Write-Host "Removing '$TaskName' from Task Scheduler..." -ForegroundColor Cyan
    try { Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false; Write-Host "Done." -ForegroundColor Green }
    catch { Write-Host "Error: $_" -ForegroundColor Yellow }
    exit 0
}

# ─── Stop ────────────────────────────────────────────────────────────────────
if ($Stop) {
    Write-Host "Stopping Antigravity daemon on port 8000..." -ForegroundColor Cyan
    Stop-DaemonOnPort
    exit 0
}

# ─── Restart ─────────────────────────────────────────────────────────────────
if ($Restart) {
    Write-Host "Restarting Antigravity daemon..." -ForegroundColor Cyan
    Stop-DaemonOnPort
    Start-Sleep -Seconds 2
}

# ─── Ensure venv ────────────────────────────────────────────────────────────
if (-not (Test-Path $VenvPath)) {
    Write-Host "Creating virtual environment..." -ForegroundColor Yellow
    python -m venv $VenvPath
}

# ─── Install deps ────────────────────────────────────────────────────────────
if (Test-Path $Requirements) {
    Write-Host "Installing/verifying dependencies..." -ForegroundColor Yellow
    & "$VenvPath\Scripts\pip.exe" install -r $Requirements --quiet
}

# ─── Check if already running ────────────────────────────────────────────────
$portInUse = Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue
if ($portInUse -and -not $Restart) {
    Write-Host "Daemon already running. Opening browser..." -ForegroundColor Green
    $url = if ($Page) { "http://127.0.0.1:8000/$Page" } else { "http://127.0.0.1:8000/" }
    Start-Process $url
    exit 0
}

# ─── Launch daemon ────────────────────────────────────────────────────────────
Write-Host "Launching Antigravity Daemon (background)..." -ForegroundColor Cyan
Start-Process -FilePath $PythonPath -ArgumentList "`"$MainScript`"" `
              -WorkingDirectory $ProjectRoot -WindowStyle Hidden

Write-Host "Waiting for server to start..." -ForegroundColor Yellow
Start-Sleep -Seconds 4

$url = if ($Page) { "http://127.0.0.1:8000/$Page" } else { "http://127.0.0.1:8000/" }
Write-Host "Opening $url" -ForegroundColor Green
Start-Process $url
Write-Host "Antigravity is live!" -ForegroundColor Green

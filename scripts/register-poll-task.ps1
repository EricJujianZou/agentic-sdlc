<#
.SYNOPSIS
  Register (or replace) the Windows Scheduled Task that runs one poll_once pass
  on an interval — the harness's OS-level trigger.

.DESCRIPTION
  The agentic-sdlc engine has no daemon: poll_once.py does ONE pass (sync GitHub
  issues -> work the backlog once) and exits. Recurrence is supplied from outside
  by this scheduled task. See README "Phone-facing backlog".

  Design choices baked in (and why):
    * Runs as the current user, LogonType=Interactive ("only when logged on"):
      `git credential fill` reads the GitHub token from the per-user Windows
      Credential vault in your interactive session. Running in Session 0
      ("whether logged on or not") is the classic "works when I click Run, fails
      at 3am" trap — different environment, no UI to answer a credential prompt.
    * RunLevel=Limited: poll_once needs no admin (least privilege).
    * MultipleInstances=IgnoreNew: a pass can outlast the interval; never overlap.
    * RunOnlyIfNetworkAvailable: it calls api.github.com.
    * Output is appended to a log OUTSIDE the repo, so an unattended run can never
      dirty the working tree (the Stop-checklist hook fails a dirty tree, and the
      autocommit hook could otherwise sweep a stray log into a commit).

  Idempotent: -Force replaces an existing task of the same name.

.PARAMETER RepoRoot
  The engine checkout to run from. Defaults to this script's parent directory.

.PARAMETER UvPath
  Full path to uv.exe. Defaults to whatever `uv` resolves to on PATH.

.PARAMETER IntervalMinutes
  Poll interval. Idle polls are nearly free (one HTTPS GET), so this is a
  pickup-latency knob, not a cost knob. Default 30.

.PARAMETER MaxTickets
  Upper bound on tickets worked per pass. Default 1.

.PARAMETER LogPath
  Where to append run output. Default %LOCALAPPDATA%\adw\poll.log.

.PARAMETER TaskName
  Scheduled task name. Default "adw-poll-once" under the \ADW\ folder.

.EXAMPLE
  pwsh -File scripts\register-poll-task.ps1
  Registers the task with all defaults.

.EXAMPLE
  pwsh -File scripts\register-poll-task.ps1 -IntervalMinutes 15 -MaxTickets 2
#>
[CmdletBinding()]
param(
    [string]$RepoRoot        = (Split-Path -Parent $PSScriptRoot),
    [string]$UvPath          = (Get-Command uv -ErrorAction SilentlyContinue).Source,
    [int]   $IntervalMinutes = 30,
    [int]   $MaxTickets      = 1,
    [string]$LogPath         = (Join-Path $env:LOCALAPPDATA "adw\poll.log"),
    [string]$TaskName        = "adw-poll-once",
    [string]$TaskPath        = "\ADW\"
)

$ErrorActionPreference = "Stop"

if (-not $UvPath)              { throw "uv.exe not found on PATH; pass -UvPath explicitly." }
if (-not (Test-Path $UvPath))  { throw "uv not found at: $UvPath" }
if (-not (Test-Path (Join-Path $RepoRoot "workflows\poll_once.py"))) {
    throw "RepoRoot does not look like the engine (no workflows\poll_once.py): $RepoRoot"
}

# Ensure the log directory exists (outside the repo).
New-Item -ItemType Directory -Force (Split-Path $LogPath) | Out-Null

# Task Scheduler runs no shell, so redirection goes through cmd /c. The nested
# quoting: cmd strips the outermost quote pair, leaving "uv.exe" run ... >> "log".
$inner    = "`"$UvPath`" run python workflows\poll_once.py --max-tickets $MaxTickets >> `"$LogPath`" 2>&1"
$action   = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c `"$inner`"" -WorkingDirectory $RepoRoot

# A one-time start + a repetition interval = the cron equivalent (Task Scheduler
# has no native "every N minutes" begin).
$trigger  = New-ScheduledTaskTrigger -Once -At (Get-Date) `
    -RepetitionInterval (New-TimeSpan -Minutes $IntervalMinutes)

$settings = New-ScheduledTaskSettingsSet `
    -MultipleInstances IgnoreNew `
    -RunOnlyIfNetworkAvailable `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Hours 2)

$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited

Register-ScheduledTask -TaskName $TaskName -TaskPath $TaskPath `
    -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Force | Out-Null

Write-Host "Registered $TaskPath$TaskName"
Write-Host "  every $IntervalMinutes min  |  --max-tickets $MaxTickets  |  log -> $LogPath"
Write-Host "  repo: $RepoRoot"
Write-Host "Test it now:  Start-ScheduledTask -TaskPath '$TaskPath' -TaskName '$TaskName'"
Write-Host "Then check:   Get-ScheduledTaskInfo -TaskPath '$TaskPath' -TaskName '$TaskName'"

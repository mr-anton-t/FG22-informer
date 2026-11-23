# One official device-erase unlock. Does not flash a new image.
param(
  [ValidateSet("status", "unlock")]
  [string]$Action = "status",
  [int]$Tries = 5,
  [int]$Pause = 5
)

$proj = Split-Path -Parent $PSScriptRoot
$openocd = Join-Path $proj "tools\openocd\xpack-openocd-0.12.0-7\bin\openocd.exe"
$scripts = Join-Path $proj "tools\openocd\xpack-openocd-0.12.0-7\openocd\scripts"
$cfg = Join-Path $proj "tools\efr32_dci.cfg"

if (-not (Test-Path $openocd)) {
  Write-Output "OpenOCD missing: $openocd"
  exit 1
}

foreach ($n in 1..$Tries) {
  try { [System.Media.SystemSounds]::Asterisk.Play() } catch {}
  Write-Output "===== try $n of $Tries ($Action) ====="
  $log = cmd /c "`"$openocd`" -s `"$scripts`" -c `"set ACTION $Action`" -f `"$cfg`" 2>&1"
  $log = $log | Out-String
  Write-Output $log
  if ($log -match "RESULT ERASE_OK" -or $log -match "RESULT STATUS") {
    Write-Output "Done. No more tries."
    exit 0
  }
  if ($n -lt $Tries) { Start-Sleep -Seconds $Pause }
}

Write-Output "No DCI answer."
exit 1

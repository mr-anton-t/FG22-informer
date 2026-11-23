# Five tries. Each one sends the official Series 2 device erase.
# That wipes main flash and opens debug. It does not write a new image.
# Stops on the first success.
param(
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

function Play-SystemSound {
  try {
    [System.Media.SystemSounds]::Asterisk.Play()
  } catch {
    cmd /c "rundll32 user32.dll,MessageBeep 64" | Out-Null
  }
}

foreach ($n in 1..$Tries) {
  Play-SystemSound
  Write-Output "===== try $n of $Tries ====="
  $log = cmd /c "`"$openocd`" -s `"$scripts`" -c `"set ACTION unlock`" -f `"$cfg`" 2>&1"
  $log = $log | Out-String
  Write-Output $log
  if ($log -match "RESULT ERASE_OK") {
    Write-Output "Erased and unlocked. No more tries."
    exit 0
  }
  if ($n -lt $Tries) { Start-Sleep -Seconds $Pause }
}

Write-Output "Erase did not happen. Chip did not answer."
exit 1

# Five SWD tries. A Windows system sound plays at the start of each try.
param(
  [int]$Tries = 5,
  [int]$Pause = 5
)

$proj = Split-Path -Parent $PSScriptRoot
$openocd = Join-Path $proj "tools\openocd\xpack-openocd-0.12.0-7\bin\openocd.exe"
$scripts = Join-Path $proj "tools\openocd\xpack-openocd-0.12.0-7\openocd\scripts"
$cfg = Join-Path $proj "tools\efr32_try.cfg"
$dump = Join-Path $proj "dumps\flash.bin"
$dumpTcl = ($dump -replace '\\', '/')

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
  $log = cmd /c "`"$openocd`" -s `"$scripts`" -c `"set DUMPPATH {$dumpTcl}`" -f `"$cfg`" 2>&1"
  $log = $log | Out-String
  Write-Output $log
  if ($log -match "RESULT DUMP_OK" -or $log -match "RESULT MEM " -or $log -match "RESULT FLASH_OK") {
    Write-Output "Got data. No more tries."
    exit 0
  }
  if ($n -lt $Tries) { Start-Sleep -Seconds $Pause }
}

Write-Output "Done. Five tries."
exit 1

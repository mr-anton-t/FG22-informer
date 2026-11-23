# Retry an EFR32 SWD read through the Pico debugprobe.
# Does not erase and does not unlock. A dump, if any, goes to dumps\ and is not committed.
param(
  [int]$Tries = 5,
  [int]$Pause = 5
)

$proj = Split-Path -Parent $PSScriptRoot
$openocd = Join-Path $proj "tools\openocd\xpack-openocd-0.12.0-7\bin\openocd.exe"
$scripts = Join-Path $proj "tools\openocd\xpack-openocd-0.12.0-7\openocd\scripts"
$cfg = Join-Path $proj "tools\efr32_try.cfg"
$dumpDir = Join-Path $proj "dumps"
$dump = Join-Path $dumpDir "flash.bin"

if (-not (Test-Path $openocd)) {
  Write-Output "OpenOCD missing: $openocd"
  exit 1
}
New-Item -ItemType Directory -Path $dumpDir -Force | Out-Null
$dumpTcl = ($dump -replace '\\', '/')

foreach ($n in 1..$Tries) {
  Write-Output "===== try $n of $Tries ====="
  $log = cmd /c "`"$openocd`" -s `"$scripts`" -c `"set DUMPPATH {$dumpTcl}`" -f `"$cfg`" 2>&1"
  $log = $log | Out-String
  Write-Output $log
  $code = $LASTEXITCODE
  if ($code -eq 0 -and (Test-Path $dump)) {
    $len = (Get-Item $dump).Length
    Write-Output "Dump written: $dump ($len bytes)"
    exit 0
  }
  if ($code -eq 2 -or $log -match "RESULT MEM_FAIL" -or $log -match "Failed to read memory") {
    Write-Output "Chip answered, but memory was not readable. Looks locked. This script does not unlock."
    exit 2
  }
  if ($n -lt $Tries) { Start-Sleep -Seconds $Pause }
}

Write-Output "No link. Pico must be plugged in, the chip powered, green on pin 22, yellow on pin 23."
exit 1

# Flash firmware/bootloader/stub.hex through the Pico debugprobe.
# Retries like read-swd. Stops on the first successful write.
# Does not unlock and does not mass-erase.
param(
  [int]$Tries = 5,
  [int]$Pause = 5
)

$proj = Split-Path -Parent $PSScriptRoot
$openocd = Join-Path $proj "tools\openocd\xpack-openocd-0.12.0-7\bin\openocd.exe"
$scripts = Join-Path $proj "tools\openocd\xpack-openocd-0.12.0-7\openocd\scripts"
$cfg = Join-Path $proj "tools\efr32_flash.cfg"
$image = Join-Path $proj "firmware\bootloader\stub.hex"

if (-not (Test-Path $openocd)) {
  Write-Output "OpenOCD missing: $openocd"
  exit 1
}
if (-not (Test-Path $image)) {
  Write-Output "Image missing: $image"
  exit 1
}
$imageTcl = ($image -replace '\\', '/')

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
  $log = cmd /c "`"$openocd`" -s `"$scripts`" -c `"set IMAGE {$imageTcl}`" -f `"$cfg`" 2>&1"
  $log = $log | Out-String
  Write-Output $log
  if ($log -match "RESULT FLASH_OK") {
    Write-Output "Flash ok. No more tries."
    exit 0
  }
  if ($log -match "RESULT MEM_FAIL" -or $log -match "Failed to read memory" -or $log -match "Examination failed") {
    Write-Output "Chip answered, but flash is not writable. Looks locked. This script does not unlock."
    exit 2
  }
  if ($n -lt $Tries) { Start-Sleep -Seconds $Pause }
}

Write-Output "Flash failed. Pico must be plugged in, the chip powered, green on pin 22, yellow on pin 23."
exit 1

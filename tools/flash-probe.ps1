# Flash stub.hex with probe-rs. Five tries, beep at the start of each.
# Stops on the first successful verify. Does not unlock.
param(
  [int]$Tries = 5,
  [int]$Pause = 5,
  [string]$Image = ""
)

$proj = Split-Path -Parent $PSScriptRoot
$probe = Join-Path $proj "tools\probe-rs\probe-rs.exe"
if ($Image -eq "") {
  $hex = Join-Path $proj "firmware\bootloader\stub.hex"
} elseif ([System.IO.Path]::IsPathRooted($Image)) {
  $hex = $Image
} else {
  $hex = Join-Path $proj $Image
}

if (-not (Test-Path $probe)) {
  Write-Output "probe-rs missing: $probe"
  exit 1
}
if (-not (Test-Path $hex)) {
  Write-Output "Image missing: $hex"
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
  $log = cmd /c "`"$probe`" download --chip EFR32FG22C121F512 --protocol swd --speed 100 --non-interactive --binary-format hex --verify --disable-progressbars `"$hex`" 2>&1"
  $log = $log | Out-String
  Write-Output $log
  $code = $LASTEXITCODE
  if ($code -eq 0 -and $log -notmatch "Error:") {
    Write-Output "Flash ok. No more tries."
    exit 0
  }
  if ($n -lt $Tries) { Start-Sleep -Seconds $Pause }
}

Write-Output "Flash failed."
exit 1

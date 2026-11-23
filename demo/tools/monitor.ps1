# Watches RAM progress marks on the tag: 30 = display started, 31 = refresh
# started, 32 = refresh done.
# Usage: powershell -NoProfile -ExecutionPolicy Bypass -File monitor.ps1 [MaxTicks]
param([int]$MaxTicks = 80)

$exe = "C:\Users\anton\Documents\ii\e-ink\tools\probe-rs\probe-rs.exe"
$common = @("--chip","EFR32FG22C121F512","--protocol","swd","--speed","100","--non-interactive")

& $exe reset @common 2>&1 | Out-Null

function Beep-N([int]$n) {
  for ($i = 1; $i -le $n; $i++) {
    [System.Media.SystemSounds]::Exclamation.Play()
    Start-Sleep -Milliseconds 400
  }
}

$seen = @{}
for ($t = 0; $t -lt $MaxTicks; $t++) {
  $mark = -1
  $raw = & $exe read @common b32 0x20000000 1 2>$null | Out-String
  if ($raw -match ":\s*([0-9a-fA-F]+)") { $mark = [Convert]::ToInt32($Matches[1], 16) }
  Write-Output ("t={0} mark={1}" -f $t, $mark)
  if ($mark -ge 30 -and -not $seen["30"]) { $seen["30"] = $true; Write-Output "DISPLAY started"; Beep-N 1 }
  if ($mark -ge 32 -and -not $seen["32"]) {
    $seen["32"] = $true
    Write-Output "DONE"
    Beep-N 3
    break
  }
  Start-Sleep -Seconds 4
}

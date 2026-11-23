$exe = "C:\Users\anton\Documents\ii\e-ink\tools\probe-rs\probe-rs.exe"
$common = @("--chip","EFR32FG22C121F512","--protocol","swd","--speed","100","--non-interactive")

function Read-Word([string]$addr) {
  $r = & $exe read @common b32 $addr 1 2>$null | Out-String
  if ($r -match ":\s*([0-9a-fA-F]+)") { return [Convert]::ToInt32($Matches[1], 16) }
  return -1
}

"MARK before: 0x{0:X}" -f (Read-Word 0x20000000)
"flag before:  0x{0:X}" -f (Read-Word 0x20000100)

# Write a test pattern into the card planes (tag polls REQ_FLAG only).
& $exe write @common b32 0x20001000 0xDEADBEEF 0x12345678 2>$null | Out-Null
& $exe write @common b32 0x20002600 0x0F0F0F0F 0xA5A5A5A5 2>$null | Out-Null
Write-Output "card RAM written: 0x{0:X} 0x{1:X}" -f (Read-Word 0x20001000) (Read-Word 0x20002600)

# Simulate the Pico: set REQ_FLAG, then watch the tag display.
& $exe write @common b32 0x20000100 0xDEADBEEF 2>$null | Out-Null
for ($i = 0; $i -lt 8; $i++) {
  Start-Sleep -Milliseconds 3000
  Write-Output ("t={0} MARK=0x{1:X} flag=0x{2:X}" -f $i, (Read-Word 0x20000000), (Read-Word 0x20000100))
}

# Clear the flag.
& $exe write @common b32 0x20000100 0 2>$null | Out-Null
Write-Output "MARK now: 0x{0:X}, flag now: 0x{1:X}" -f (Read-Word 0x20000000) (Read-Word 0x20000100)

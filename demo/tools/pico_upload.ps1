# Uploads demo\pico\*.py + main.py to the MicroPython Pico W over its
# serial REPL (the Pico W CDC port) and runs an import test.
#
# Usage:
#   powershell -File demo\tools\pico_upload.ps1 -Port COM8
#
# The uploader sends the four files + main.py through the REPL using
# binascii.unhexlify chunks (no base64 module needed on the Pico).
#
# Expected output on the Pico:
#   MicroPython v1.29.0 on RP2-A ... >>>
#   Pico Weather Gateway: boot
#   WiFi: connected
#   OK Warsaw +3C облачно · 86%          (every hour)

param([string]$Port = "")

$ErrorActionPreference = "Stop"
$root = Join-Path (Split-Path $PSCommandPath) ".."
$pico = Join-Path $root "pico"

$ports = [System.IO.Ports.SerialPort]::GetPortNames() | Sort-Object
if (-not $Port) {
  Write-Output "Usage: powershell -File demo\tools\pico_upload.ps1 -Port COM8"
  if ($ports) { Write-Output ("Ports: " + ($ports -join ", ")) }
  exit 1
}

$sp = New-Object System.IO.Ports.SerialPort($Port, 115200)
$sp.Handshake = [System.IO.Ports.Handshake]::None
$sp.Encoding = New-Object System.Text.UTF8Encoding($false)
$sp.ReadTimeout = 100
$sp.WriteTimeout = 1000
$sp.NewLine = "`n"
$sp.Open()

$log = New-Object System.Text.StringBuilder
$sw = [System.Diagnostics.Stopwatch]::StartNew()

function Recv([int]$ms) {
  $end = $sw.ElapsedMilliseconds + $ms
  while ($sw.ElapsedMilliseconds -lt $end) {
    try { $d = $sp.ReadExisting() } catch { $d = "" }
    if ($d) { [void]$log.Append($d) }
  }
}

function Wait-Log([string]$pat, [int]$ms, [int]$base) {
  $end = $sw.ElapsedMilliseconds + $ms
  while ($sw.ElapsedMilliseconds -lt $end) {
    Recv 150
    $s = $log.ToString().Substring([Math]::Max(0, $base - 60))
    if ($s.Contains($pat)) { return $true }
  }
  $s = $log.ToString().Substring([Math]::Max(0, $base - 60))
  return $s.Contains($pat)
}

function Send-Cmd([string]$line, [int]$ms) {
  $base = $log.Length
  $sp.WriteLine($line)
  [void](Wait-Log ">>>" $ms $base)
}

Write-Output "Connecting to $Port ..."

# Stop a running main.py (Ctrl-C) and ask for a fresh prompt.
$sp.Write([string][char]3); Start-Sleep -Milliseconds 200
$sp.Write([string][char]3); Start-Sleep -Milliseconds 200
$sp.Write("`r`n")

# Wait for the REPL prompt.
if (-not (Wait-Log ">>>" 4000 0)) {
  Write-Output "No REPL prompt on $Port. Unplug the Pico, plug it back in (no button) and re-run. See demo\README.md."
  $sp.Close()
  exit 1
}

# --- upload ---------------------------------------------------------------

Send-Cmd "import binascii" 500

function Put-File([string]$name) {
  # Raw bytes, so binary files (card_assets.bin) upload unchanged too.
  $start = $log.Length
  $hex = [BitConverter]::ToString([System.IO.File]::ReadAllBytes((Join-Path $pico $name))).Replace("-", "")
  Send-Cmd ('f = open("' + $name + '", "wb")') 400
  $n = $hex.Length
  for ($i = 0; $i -lt $n; $i += 400) {
    $seg = $hex.Substring($i, [Math]::Min(400, $n - $i))
    Send-Cmd ('f.write(binascii.unhexlify("' + $seg + '"))') 400
  }
  Send-Cmd "f.close()" 400
  # Only what this file's upload printed; the echoed hex never contains it.
  $err = $log.ToString().Substring($start).Contains("Traceback")
  if ($err) {
    Write-Output ("Uploaded " + $name + ": FAIL")
  } else {
    Write-Output ("Uploaded " + $name + ": OK")
  }
}

if (-not (Test-Path (Join-Path $pico "secrets.py"))) {
  Write-Output "demo\pico\secrets.py is missing: copy secrets_example.py to secrets.py and fill in the Wi-Fi SSID and password."
  exit 1
}
Put-File "secrets.py"
Put-File "pico_json.py"
Put-File "pico_ha.py"
Put-File "pico_weather.py"
Put-File "pico_canvas.py"
Put-File "pico_card.py"
Put-File "card_assets.py"
Put-File "card_assets.bin"
Put-File "pico_swd.py"
Put-File "main.py"

# --- test: import pico_weather and wait for the send_card status ------------

Send-Cmd "import pico_weather"

$end = $sw.ElapsedMilliseconds + 90000
$sent = $false
while ($sw.ElapsedMilliseconds -lt $end) {
  Recv 300
  if ($log.ToString().Contains("send_card:")) { $sent = $true; break }
  if ($log.ToString().Contains("ERROR:")) { break }
}

Write-Output ""
Write-Output "=== Serial log (tail) ==="
$lines = $log.ToString().Split(@("`r", "`n"), [System.StringSplitOptions]::RemoveEmptyEntries)
$start = [Math]::Max(0, $lines.Length - 30)
for ($i = $start; $i -lt $lines.Length; $i++) {
  Write-Output $lines[$i]
}
if ($sent) {
  Write-Output "=== send_card seen: check the tag for the card ==="
} else {
  Write-Output "=== TIMEOUT waiting for 'send_card:' ==="
}

$sp.Close()
exit $(if ($sent) { 0 } else { 1 })

# Decodes demo\tag\card.h (CARD_BLACK / CARD_RED planes, 152x296, stride 19)
# and prints a text map of the card: '#' = black, 'R' = red, '.' = white.
param([string]$Header = (Join-Path (Split-Path $PSCommandPath) "..\tag\card.h"))

$txt = Get-Content $Header -Raw

function Get-Plane([string]$name) {
  $m = [regex]::Match($txt, "static const unsigned char $name\[5624\] = \{(.*?)\}", [System.Text.RegularExpressions.RegexOptions]::Singleline)
  if (-not $m.Success) { Write-Output "MISSING $name"; return @(1) * 5624 }
  return $m.Groups[1] -split ',' | Where-Object { $_ -match '0x' } | ForEach-Object { [Convert]::ToByte($_.Trim(), 16) }
}

$black = Get-Plane "CARD_BLACK"
$red = Get-Plane "CARD_RED"

for ($y = 0; $y -lt 296; $y++) {
  $row = New-Object System.Text.StringBuilder
  for ($x = 0; $x -lt 152; $x++) {
    $idx = $y * 19 + [math]::Floor($x / 8)
    $bit = 0x80 -shr ($x % 8)
    $isRed = ($red[$idx] -band $bit) -ne 0
    $isBlack = ($black[$idx] -band $bit) -ne 0
    $ch = if ($isRed -and $isBlack) { '?' } elseif ($isRed) { 'R' } elseif ($isBlack) { '#' } else { '.' }
    [void]$row.Append($ch)
  }
  Write-Output $row.ToString()
}

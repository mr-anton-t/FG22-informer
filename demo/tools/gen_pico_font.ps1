# Generates demo\pico\fonts_w.py — a 6x8 glyph table in Arial Regular + Bold.
# Each glyph is a tuple of 6 ints: glyph[c] bits 0..7 = pixels row 0..7 of column c.
# Glyphs are cropped to 6x8 (left-aligned, rows top-aligned, bit0 = top row).

$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Drawing
$Out = (Join-Path (Split-Path $PSCommandPath) "..\pico\fonts_w.py")

$Codes = @(
  0x20, 0x2B, 0x2D, 0x2E, 0x2C, 0x3A, 0x3B, 0x2F, 0x28, 0x29, 0x3F, 0xB0, 0xB7, 0x25
)
$Codes += 0x30..0x39
$Codes += 0x41..0x5A
$Codes += 0x61..0x7A
$Codes += 0x410..0x42F
$Codes += 0x430..0x44F
$Codes += @(0x401, 0x451)

function Rasterize([string]$ch, $font) {
  $bmp = New-Object System.Drawing.Bitmap(12, 12)
  $g = [System.Drawing.Graphics]::FromImage($bmp)
  $g.TextRenderingHint = [System.Drawing.Text.TextRenderingHint]::AntiAliasGridFit
  $brush = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::Black)
  $g.DrawString($ch, $font, $brush, 1, 1)
  $set = @{}
  $minx = 99; $miny = 99; $maxx = -1; $maxy = -1
  for ($x = 0; $x -lt 12; $x++) {
    for ($y = 0; $y -lt 12; $y++) {
      $px = $bmp.GetPixel($x, $y)
      if ($px.A -gt 0 -and $px.GetBrightness() -lt 0.55) {
        $set["$x,$y"] = $true
        if ($x -lt $minx) { $minx = $x }
        if ($x -gt $maxx) { $maxx = $x }
        if ($y -lt $miny) { $miny = $y }
        if ($y -gt $maxy) { $maxy = $y }
      }
    }
  }
  $g.Dispose()
  $bmp.Dispose()
  $cols = New-Object int[](6)
  for ($c = 0; $c -lt 6; $c++) {
    $ax = $minx + $c
    $v = 0
    for ($r = 0; $r -lt 8; $r++) {
      $ay = $miny + $r
      if ($set.ContainsKey("$ax,$ay")) { $v = $v -bor (1 -shl $r) }
    }
    $cols[$c] = $v
  }
  return $cols
}

function EmitTable($tableName, $glyphs) {
  $out = New-Object System.Text.StringBuilder
  [void]$out.AppendLine($tableName + " = {")
  foreach ($code in $glyphs.Keys) {
    $cols = $glyphs[$code]
    $lit = if ($code -lt 0x80) { "'" + $code + "'" } else { "'" + [char]92 + "u" + ([int]$code).ToString("X4") + "'" }
    $nums = ""
    for ($c = 0; $c -lt 6; $c++) {
      $nums += ("0x{0:X2}" -f $cols[$c]) + ","
    }
    [void]$out.AppendLine("    " + $lit + ": (" + $nums + "),")
  }
  [void]$out.AppendLine("}")
  [void]$out.AppendLine("")
  return $out.ToString()
}

$bold = New-Object System.Drawing.Font "Arial", 8, ([System.Drawing.FontStyle]::Bold), ([System.Drawing.GraphicsUnit]::Point)
$reg = New-Object System.Drawing.Font "Arial", 8, ([System.Drawing.FontStyle]::Regular), ([System.Drawing.GraphicsUnit]::Point)

$gB = @{}
$gR = @{}
foreach ($code in $Codes) {
  $ch = [char]$code
  $g = Rasterize $ch.ToString() $bold
  $gB[[char]$code] = $g
  $g = Rasterize $ch.ToString() $reg
  $gR[[char]$code] = $g
}
$g2 = EmitTable "F_BOLD" $gB
$g3 = EmitTable "F_REG" $gR
$text = $g2 + $g3
[System.IO.File]::WriteAllText($Out, $text, (New-Object System.Text.UTF8Encoding($false)))
Write-Output "Wrote $Out"

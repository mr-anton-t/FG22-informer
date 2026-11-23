# Renders a card for the SE2266 panel (152x296, 1bpp black + 1bpp red) and
# writes it as a C header with the two planes the COG expects.
# Keep this file pure ASCII: Windows PowerShell 5.1 reads .ps1 as ANSI unless
# it starts with a BOM, so every non-ASCII glyph is built from character codes.
param(
  [ValidateSet("alphabet", "weather")]
  [string]$Layout = "alphabet",
  [string]$City = "Moscow",
  [string]$OutFile = ""
)

$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Drawing

if ($OutFile -eq "") {
  $OutFile = Join-Path $PSScriptRoot "..\tag\card.h"
}
$PreviewFile = Join-Path (Split-Path $OutFile) "card-preview.png"

$W = 152
$H = 296
$STRIDE = 19
$PLANE = $STRIDE * $H

function RU { param([int[]]$codes) -join ($codes | ForEach-Object { [char]$_ }) }
function Chars { param([int]$from, [int]$to) -join ($from..$to | ForEach-Object { [char]$_ }) }
$DEG = [string][char]0x00B0

$F_TITLE   = New-Object System.Drawing.Font "Arial", 15, ([System.Drawing.FontStyle]::Bold), ([System.Drawing.GraphicsUnit]::Pixel)
$F_BIG     = New-Object System.Drawing.Font "Arial", 24, ([System.Drawing.FontStyle]::Bold), ([System.Drawing.GraphicsUnit]::Pixel)
$F_UPPER   = New-Object System.Drawing.Font "Arial", 14, ([System.Drawing.FontStyle]::Regular), ([System.Drawing.GraphicsUnit]::Pixel)
$F_LOWER   = New-Object System.Drawing.Font "Arial", 13, ([System.Drawing.FontStyle]::Regular), ([System.Drawing.GraphicsUnit]::Pixel)
$F_DIGITS  = New-Object System.Drawing.Font "Arial", 12, ([System.Drawing.FontStyle]::Regular), ([System.Drawing.GraphicsUnit]::Pixel)
$F_LATIN   = New-Object System.Drawing.Font "Arial", 11, ([System.Drawing.FontStyle]::Regular), ([System.Drawing.GraphicsUnit]::Pixel)
$F_LABEL   = New-Object System.Drawing.Font "Arial", 8, ([System.Drawing.FontStyle]::Bold), ([System.Drawing.GraphicsUnit]::Pixel)
$F_FOOT    = New-Object System.Drawing.Font "Arial", 8, ([System.Drawing.FontStyle]::Regular), ([System.Drawing.GraphicsUnit]::Pixel)
# Weather card fonts. Nothing below 24 px: the panel is 152 px wide.
$F_CITY    = New-Object System.Drawing.Font "Arial", 24, ([System.Drawing.FontStyle]::Bold), ([System.Drawing.GraphicsUnit]::Pixel)
$F_COND    = New-Object System.Drawing.Font "Arial", 24, ([System.Drawing.FontStyle]::Regular), ([System.Drawing.GraphicsUnit]::Pixel)
$F_DAY     = New-Object System.Drawing.Font "Arial", 24, ([System.Drawing.FontStyle]::Bold), ([System.Drawing.GraphicsUnit]::Pixel)
$F_HI      = New-Object System.Drawing.Font "Arial", 24, ([System.Drawing.FontStyle]::Bold), ([System.Drawing.GraphicsUnit]::Pixel)
$F_LO      = New-Object System.Drawing.Font "Arial", 24, ([System.Drawing.FontStyle]::Regular), ([System.Drawing.GraphicsUnit]::Pixel)

$sfTypo = [System.Drawing.StringFormat]::GenericTypographic
$sfMid = New-Object System.Drawing.StringFormat
$sfMid.Alignment = [System.Drawing.StringAlignment]::Center
$sfMid.LineAlignment = [System.Drawing.StringAlignment]::Center
$sfRight = New-Object System.Drawing.StringFormat
$sfRight.Alignment = [System.Drawing.StringAlignment]::Far
$sfRight.LineAlignment = [System.Drawing.StringAlignment]::Center

$bmp = New-Object System.Drawing.Bitmap $W, $H
$g = [System.Drawing.Graphics]::FromImage($bmp)
$g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
$g.TextRenderingHint = [System.Drawing.Text.TextRenderingHint]::AntiAliasGridFit
$g.Clear([System.Drawing.Color]::White)

$blackBrush = New-Object System.Drawing.SolidBrush ([System.Drawing.Color]::Black)
$redBrush = New-Object System.Drawing.SolidBrush ([System.Drawing.Color]::FromArgb(190, 20, 20))

function Draw-Line($g, [string]$text, $font, $brush, [double]$x, [double]$y) {
  $g.DrawString($text, $font, $brush, [float]$x, [float]$y, $sfTypo)
}

function Measure-W($g, [string]$text, $font) {
  return $g.MeasureString($text, $font, [int]::MaxValue, $sfTypo).Width
}

# Draw without a layout rectangle: GDI+ otherwise wraps and clips the last glyph.
function Draw-TextRight($g, [string]$text, $font, $brush, [double]$right, [double]$top, [double]$height) {
  $w = Measure-W $g $text $font
  $h = $font.GetHeight($g)
  $g.DrawString($text, $font, $brush, [float]($right - $w), [float]($top + ($height - $h) / 2), $sfTypo)
}

function Draw-TextCenter($g, [string]$text, $font, $brush, [double]$cx, [double]$top, [double]$height) {
  $w = Measure-W $g $text $font
  $h = $font.GetHeight($g)
  $g.DrawString($text, $font, $brush, [float]($cx - $w / 2), [float]($top + ($height - $h) / 2), $sfTypo)
}

function Wrap-Text($g, [string]$text, $font, [double]$maxW) {
  $lines = @()
  $cur = ""
  foreach ($ch in $text.ToCharArray()) {
    $try = $cur + $ch
    if ((Measure-W $g $try $font) -gt $maxW -and $cur.Length -gt 0) {
      $lines += $cur
      $cur = [string]$ch
    } else {
      $cur = $try
    }
  }
  if ($cur.Length -gt 0) { $lines += $cur }
  return $lines
}

function Draw-Block($g, [string]$label, [string]$text, $font, [double]$y, [double]$lineH, $labelBrush, $textBrush) {
  Draw-Line $g $label $F_LABEL $labelBrush 4 $y
  $y += 10
  foreach ($ln in (Wrap-Text $g $text $font ($W - 8))) {
    Draw-Line $g $ln $font $textBrush 4 $y
    $y += $lineH
  }
  return $y + 5
}

# ---------------------------------------------------------------- alphabet
if ($Layout -eq "alphabet") {
  $upper = (Chars 0x0410 0x042F)
  $upper = $upper.Substring(0, 6) + [string][char]0x0401 + $upper.Substring(6)
  $lower = (Chars 0x0430 0x044F)
  $lower = $lower.Substring(0, 6) + [string][char]0x0451 + $lower.Substring(6)
  $digits = "0123456789"
  $punct = ".,:;!?()[]{}-+=*/%$#@&" + (RU 0x2116) + (RU 0x00AB) + (RU 0x00BB) + $DEG
  $latUp = (Chars 0x41 0x5A)
  $latLo = (Chars 0x61 0x7A)
  $title = RU 0x410, 0x43B, 0x444, 0x430, 0x432, 0x438, 0x442

  $y = 2
  $r = New-Object System.Drawing.RectangleF 0, 0, $W, 20
  $g.DrawString($title, $F_TITLE, $blackBrush, $r, $sfMid)
  $y = 24
  $g.FillRectangle($redBrush, 4, $y, $W - 8, 2)
  $y += 6

  Draw-Line $g ((RU 0x410) + (RU 0x430) + "  " + (RU 0x411) + (RU 0x431) + "  " + "123" + $DEG) $F_BIG $blackBrush 6 $y
  $y += 30

  $y = Draw-Block $g (RU 0x417,0x410,0x413,0x41B,0x410,0x412,0x41D,0x42B,0x415) $upper $F_UPPER $y 16 $redBrush $blackBrush
  $y = Draw-Block $g (RU 0x421,0x422,0x420,0x41E,0x427,0x41D,0x42B,0x415) $lower $F_LOWER $y 15 $redBrush $blackBrush
  $y = Draw-Block $g (RU 0x426,0x418,0x424,0x420,0x42B,0x20,0x418,0x20,0x417,0x41D,0x410,0x41A,0x418) ($digits + "  " + $punct) $F_DIGITS $y 14 $redBrush $blackBrush
  $y = Draw-Block $g (RU 0x41B,0x410,0x422,0x418,0x41D,0x418,0x426,0x410) ($latUp + "  " + $latLo) $F_LATIN $y 13 $redBrush $blackBrush

  Draw-Line $g "1:1  152x296  1bpp" $F_FOOT $blackBrush 6 285
}

# ----------------------------------------------------------------- weather
if ($Layout -eq "weather") {
  $DAYS = @(
    (RU 0x41F, 0x43D), (RU 0x412, 0x442), (RU 0x421, 0x440), (RU 0x427, 0x442),
    (RU 0x41F, 0x442), (RU 0x421, 0x431), (RU 0x412, 0x441)
  )

  function GetIcon([int]$ww) {
    if ($ww -eq 113) { return "sun" }
    if ($ww -eq 116) { return "part" }
    if ($ww -eq 119 -or $ww -eq 122) { return "cloud" }
    if ($ww -eq 143 -or $ww -eq 248 -or $ww -eq 260) { return "fog" }
    if ($ww -eq 200 -or $ww -eq 386 -or $ww -eq 389 -or $ww -eq 392 -or $ww -eq 395) { return "storm" }
    if ($ww -in @(179, 182, 185, 227, 230, 320, 323, 326, 329, 332, 335, 338, 368, 371, 374, 377)) { return "snow" }
    if ($ww -in @(176, 263, 266, 293, 296, 299, 302, 305, 308, 353, 356, 359, 362, 365)) { return "rain" }
    return "cloud"
  }

  function Get-Cond([int]$ww) {
    if ($ww -eq 113) { return (RU 0x44F, 0x441, 0x43D, 0x43E) }
    if ($ww -eq 143 -or $ww -eq 248 -or $ww -eq 260) { return (RU 0x442, 0x443, 0x43C, 0x430, 0x43D) }
    if ($ww -eq 200 -or $ww -eq 386 -or $ww -eq 389 -or $ww -eq 392 -or $ww -eq 395) { return (RU 0x433, 0x440, 0x43E, 0x437, 0x430) }
    if ($ww -in @(179, 182, 185, 227, 230, 320, 323, 326, 329, 332, 335, 338, 368, 371, 374, 377)) { return (RU 0x441, 0x43D, 0x435, 0x433) }
    if ($ww -in @(176, 263, 266, 293, 296, 299, 302, 305, 308, 353, 356, 359, 362, 365)) { return (RU 0x434, 0x43E, 0x436, 0x434, 0x44C) }
    return (RU 0x43E, 0x431, 0x43B, 0x430, 0x447, 0x43D, 0x43E)
  }

  function Draw-Cloud($g, $b, [double]$x, [double]$y, [double]$s) {
    $g.FillEllipse($b, $x + $s * 0.16, $y + $s * 0.42, $s * 0.42, $s * 0.42)
    $g.FillEllipse($b, $x + $s * 0.36, $y + $s * 0.26, $s * 0.50, $s * 0.56)
    $g.FillEllipse($b, $x + $s * 0.60, $y + $s * 0.46, $s * 0.36, $s * 0.38)
    $g.FillRectangle($b, $x + $s * 0.18, $y + $s * 0.60, $s * 0.76, $s * 0.24)
  }

  function Draw-Sun($g, $b, [double]$x, [double]$y, [double]$s) {
    $cx = $x + $s / 2
    $cy = $y + $s / 2
    $r = $s * 0.26
    $g.FillEllipse($b, $cx - $r, $cy - $r, 2 * $r, 2 * $r)
    $pen = New-Object System.Drawing.Pen $b.Color, ($s * 0.08)
    for ($i = 0; $i -lt 8; $i++) {
      $a = $i * [math]::PI / 4
      $g.DrawLine($pen, [float]($cx + $r * 1.45 * [math]::Cos($a)), [float]($cy + $r * 1.45 * [math]::Sin($a)),
                       [float]($cx + $r * 1.95 * [math]::Cos($a)), [float]($cy + $r * 1.95 * [math]::Sin($a)))
    }
    $pen.Dispose()
  }

  function Draw-Icon($g, [string]$kind, [double]$x, [double]$y, [double]$s) {
    $b = New-Object System.Drawing.SolidBrush ([System.Drawing.Color]::Black)
    switch ($kind) {
      "sun"   { Draw-Sun $g $b $x $y $s }
      "part"  { Draw-Sun $g $b ($x + $s * 0.02) ($y + $s * 0.02) ($s * 0.62); Draw-Cloud $g $b $x ($y + $s * 0.26) ($s * 0.80) }
      "cloud" { Draw-Cloud $g $b $x ($y + $s * 0.18) $s }
      "rain"  {
        Draw-Cloud $g $b $x $y ($s * 0.92)
        $pen = New-Object System.Drawing.Pen ([System.Drawing.Color]::Black), ($s * 0.07)
        for ($i = 0; $i -lt 3; $i++) {
          $dx = $x + $s * (0.28 + 0.22 * $i)
          $g.DrawLine($pen, [float]$dx, [float]($y + $s * 0.78), [float]($dx - $s * 0.07), [float]($y + $s * 0.98))
        }
        $pen.Dispose()
      }
      "snow"  {
        Draw-Cloud $g $b $x $y ($s * 0.92)
        for ($i = 0; $i -lt 3; $i++) {
          $cx = $x + $s * (0.28 + 0.22 * $i)
          $cy = $y + $s * 0.90
          $r = $s * 0.07
          $g.FillEllipse($b, [float]($cx - $r), [float]($cy - $r), [float](2 * $r), [float](2 * $r))
        }
      }
      "storm" {
        Draw-Cloud $g $b $x $y ($s * 0.92)
        $pts = @(
          (New-Object System.Drawing.PointF ([float]($x + $s * 0.56), [float]($y + $s * 0.72))),
          (New-Object System.Drawing.PointF ([float]($x + $s * 0.40), [float]($y + $s * 0.94))),
          (New-Object System.Drawing.PointF ([float]($x + $s * 0.56), [float]($y + $s * 0.94))),
          (New-Object System.Drawing.PointF ([float]($x + $s * 0.46), [float]($y + $s * 1.10))),
          (New-Object System.Drawing.PointF ([float]($x + $s * 0.74), [float]($y + $s * 0.86))),
          (New-Object System.Drawing.PointF ([float]($x + $s * 0.58), [float]($y + $s * 0.86)))
        )
        $g.FillPolygon($b, [System.Drawing.PointF[]]$pts)
      }
      "fog"   {
        $pen = New-Object System.Drawing.Pen ([System.Drawing.Color]::Black), ($s * 0.09)
        for ($i = 0; $i -lt 4; $i++) {
          $yy = $y + $s * (0.28 + 0.16 * $i)
          $g.DrawLine($pen, [float]($x + $s * 0.10), [float]$yy, [float]($x + $s * 0.90), [float]$yy)
        }
        $pen.Dispose()
      }
    }
    $b.Dispose()
  }

  $url = "https://wttr.in/" + [uri]::EscapeDataString($City) + "?format=j1"
  try {
    $j = Invoke-RestMethod -Uri $url -TimeoutSec 40 -Headers @{ "User-Agent" = "curl/8.5.0" }
  } catch {
    Write-Output ("WEATHER FETCH FAILED: " + $_.Exception.Message)
    exit 1
  }

  $cur = $j.current_condition[0]
  $area = [string]$j.nearest_area[0].areaName[0].value
  $temp = [int]$cur.temp_C
  $feels = [int]$cur.FeelsLikeC
  $hum = [int]$cur.humidity
  $wind = [math]::Round(([double]$cur.windspeedKmph / 3.6), 1)
  $press = [int]$cur.pressure
  $code = [int]$cur.weatherCode

  # --- layout: every line of text is at least 24 px high ---------------
  $cityText = $area.ToUpper()
  while ($cityText.Length -gt 2 -and (Measure-W $g $cityText $F_CITY) -gt 146) {
    $cityText = $cityText.Substring(0, $cityText.Length - 1)
  }
  Draw-TextCenter $g $cityText $F_CITY $blackBrush 76 0 30

  $g.FillRectangle($redBrush, 6, 31, $W - 12, 2)

  Draw-Icon $g (GetIcon $code) 3 34 54

  $tText = [string]$temp
  if ($temp -ge 0) { $tText = "+" + $tText }
  $tText = $tText + $DEG
  $tSize = 54
  $tFont = New-Object System.Drawing.Font "Arial", $tSize, ([System.Drawing.FontStyle]::Bold), ([System.Drawing.GraphicsUnit]::Pixel)
  while ($tSize -gt 38 -and (Measure-W $g $tText $tFont) -gt 92) {
    $tFont.Dispose()
    $tSize -= 4
    $tFont = New-Object System.Drawing.Font "Arial", $tSize, ([System.Drawing.FontStyle]::Bold), ([System.Drawing.GraphicsUnit]::Pixel)
  }
  Draw-TextRight $g $tText $tFont $redBrush 150 32 62
  $tFont.Dispose()

  $condLine = Get-Cond $code
  $condLine = $condLine + " " + [string][char]0x00B7 + " " + $hum + "%"
  if ((Measure-W $g $condLine $F_COND) -gt 148) { $condLine = Get-Cond $code }
  Draw-TextCenter $g $condLine $F_COND $blackBrush 76 95 28

  $g.FillRectangle($redBrush, 6, 127, $W - 12, 2)

  $today = [int](Get-Date).DayOfWeek
  for ($i = 0; $i -lt 3; $i++) {
    $y = 133 + $i * 51
    $dow = $DAYS[($today + $i) % 7]
    Draw-TextCenter $g $dow $F_DAY $redBrush 20 ($y + 11) 28
    if ($i -lt $j.weather.Count) {
      $day = $j.weather[$i]
      Draw-Icon $g (GetIcon ([int]$day.hourly[4].weatherCode)) 40 ($y + 8) 30
      $hi = [int]$day.maxtempC
      $lo = [int]$day.mintempC
      $hiText = [string]$hi
      $loText = [string]$lo
      if ($hi -ge 0) { $hiText = "+" + $hiText }
      if ($lo -ge 0) { $loText = "+" + $loText }
      Draw-TextRight $g ($hiText + $DEG) $F_HI $blackBrush 150 ($y + 2) 24
      Draw-TextRight $g ($loText + $DEG) $F_LO $blackBrush 150 ($y + 26) 24
    }
  }
}

$g.Dispose()

$prev = New-Object System.Drawing.Bitmap ($W * 3), ($H * 3)
$pg = [System.Drawing.Graphics]::FromImage($prev)
$pg.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::NearestNeighbor
$pg.DrawImage($bmp, 0, 0, $W * 3, $H * 3)
$pg.Dispose()
$prev.Save($PreviewFile, [System.Drawing.Imaging.ImageFormat]::Png)
$prev.Dispose()

# Pack pixels into the two planes. 1 = black / 1 = red, MSB is the left pixel.
$black = New-Object byte[] $PLANE
$red = New-Object byte[] $PLANE
$blackPixels = 0
$redPixels = 0
for ($y = 0; $y -lt $H; $y++) {
  for ($x = 0; $x -lt $W; $x++) {
    $c = $bmp.GetPixel($x, $y)
    $idx = $y * $STRIDE + [int]([math]::Floor($x / 8))
    $bit = 0x80 -shr ($x % 8)
    if ($c.R -gt 110 -and $c.R - $c.G -gt 60 -and $c.R - $c.B -gt 60) {
      $red[$idx] = $red[$idx] -bor $bit
      $redPixels++
    } elseif (($c.R + $c.G + $c.B) -lt 400) {
      $black[$idx] = $black[$idx] -bor $bit
      $blackPixels++
    }
  }
}
$bmp.Dispose()

$sb = New-Object System.Text.StringBuilder
[void]$sb.AppendLine("/* Generated by tools/make-card.ps1. Do not edit. */")
[void]$sb.AppendLine("/* Layout: $Layout */")
[void]$sb.AppendLine("#ifndef CARD_H")
[void]$sb.AppendLine("#define CARD_H")
[void]$sb.AppendLine("")
function Append-Array($sb, [string]$name, [byte[]]$data) {
  [void]$sb.AppendLine("static const unsigned char $name[$PLANE] = {")
  $line = "  "
  for ($i = 0; $i -lt $data.Length; $i++) {
    $line += ("0x{0:X2}," -f $data[$i])
    if ((($i + 1) % 24) -eq 0) {
      [void]$sb.AppendLine($line)
      $line = "  "
    }
  }
  if ($line.Trim().Length -gt 0) { [void]$sb.AppendLine($line) }
  [void]$sb.AppendLine("};")
  [void]$sb.AppendLine("")
}
Append-Array $sb "CARD_BLACK" $black
Append-Array $sb "CARD_RED" $red
[void]$sb.AppendLine("#endif")

[System.IO.File]::WriteAllText($OutFile, $sb.ToString(), (New-Object System.Text.UTF8Encoding($false)))
Write-Output ("Wrote   " + $OutFile)
Write-Output ("Preview " + $PreviewFile)
Write-Output ("black pixels " + $blackPixels + ", red pixels " + $redPixels)

# Renders a 152x296 weather card for the SE2266 panel and writes it as a
# C header with the two 1bpp planes the COG expects (0x10 black, 0x13 red).
# Keep this file pure ASCII: Windows PowerShell 5.1 reads .ps1 as ANSI unless
# it starts with a BOM, so any non-ASCII glyph is built from character codes.
param(
  [string]$City = "Moscow",
  [string]$OutFile = ""
)

$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Drawing

if ($OutFile -eq "") {
  $OutFile = Join-Path $PSScriptRoot "..\tag\weather.h"
}
$PreviewFile = Join-Path (Split-Path $OutFile) "weather-preview.png"

$W = 152
$H = 296
$STRIDE = 19
$PLANE = $STRIDE * $H

function RU { param([int[]]$codes) -join ($codes | ForEach-Object { [char]$_ }) }
$DEG = [string][char]0x00B0
$DAYS = @(
  (RU 0x41F, 0x43D),                                            # Mon
  (RU 0x412, 0x442),                                            # Tue
  (RU 0x421, 0x440),                                            # Wed
  (RU 0x427, 0x442),                                            # Thu
  (RU 0x41F, 0x442),                                            # Fri
  (RU 0x421, 0x431),                                            # Sat
  (RU 0x412, 0x441)                                             # Sun
)

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
    $r1 = $r * 1.45
    $r2 = $r * 1.95
    $g.DrawLine($pen, [float]($cx + $r1 * [math]::Cos($a)), [float]($cy + $r1 * [math]::Sin($a)),
                     [float]($cx + $r2 * [math]::Cos($a)), [float]($cy + $r2 * [math]::Sin($a)))
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
      $pen = New-Object System.Drawing.Pen ([System.Drawing.Color]::Black), ($s * 0.06)
      for ($i = 0; $i -lt 3; $i++) {
        $cx = $x + $s * (0.28 + 0.22 * $i)
        $cy = $y + $s * 0.88
        $r = $s * 0.09
        $g.DrawLine($pen, [float]($cx - $r), [float]$cy, [float]($cx + $r), [float]$cy)
        $g.DrawLine($pen, [float]$cx, [float]($cy - $r), [float]$cx, [float]($cy + $r))
      }
      $pen.Dispose()
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

$bmp = New-Object System.Drawing.Bitmap $W, $H
$g = [System.Drawing.Graphics]::FromImage($bmp)
$g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
$g.TextRenderingHint = [System.Drawing.Text.TextRenderingHint]::AntiAliasGridFit
$g.Clear([System.Drawing.Color]::White)

$blackBrush = New-Object System.Drawing.SolidBrush ([System.Drawing.Color]::Black)
$redBrush = New-Object System.Drawing.SolidBrush ([System.Drawing.Color]::FromArgb(190, 20, 20))

$fCity = New-Object System.Drawing.Font "Arial", 10, ([System.Drawing.FontStyle]::Bold), ([System.Drawing.GraphicsUnit]::Pixel)
$fBig = New-Object System.Drawing.Font "Arial", 42, ([System.Drawing.FontStyle]::Bold), ([System.Drawing.GraphicsUnit]::Pixel)
$fSmall = New-Object System.Drawing.Font "Arial", 9, ([System.Drawing.FontStyle]::Regular), ([System.Drawing.GraphicsUnit]::Pixel)
$fDay = New-Object System.Drawing.Font "Arial", 11, ([System.Drawing.FontStyle]::Bold), ([System.Drawing.GraphicsUnit]::Pixel)
$fHi = New-Object System.Drawing.Font "Arial", 20, ([System.Drawing.FontStyle]::Bold), ([System.Drawing.GraphicsUnit]::Pixel)
$fLo = New-Object System.Drawing.Font "Arial", 11, ([System.Drawing.FontStyle]::Regular), ([System.Drawing.GraphicsUnit]::Pixel)

$sfMid = New-Object System.Drawing.StringFormat
$sfMid.Alignment = [System.Drawing.StringAlignment]::Center
$sfMid.LineAlignment = [System.Drawing.StringAlignment]::Center
$sfRight = New-Object System.Drawing.StringFormat
$sfRight.Alignment = [System.Drawing.StringAlignment]::Far
$sfRight.LineAlignment = [System.Drawing.StringAlignment]::Center

function Draw-Text($g, [string]$text, $font, $brush, [double]$x, [double]$y, [double]$w, [double]$h, $sf) {
  $r = New-Object System.Drawing.RectangleF ([float]$x), ([float]$y), ([float]$w), ([float]$h)
  $g.DrawString($text, $font, $brush, $r, $sf)
}

# City
Draw-Text $g $area.ToUpper() $fCity $blackBrush 0 1 $W 14 $sfMid

# Current icon and temperature
Draw-Icon $g (GetIcon $code) 4 20 50
Draw-Text $g ("+" + $temp + $DEG) $fBig $redBrush 56 16 92 54 $sfRight

# Details
Draw-Text $g ($hum.ToString() + "%  " + $wind.ToString() + "m/s") $fSmall $blackBrush 4 72 84 12 $sfRight
Draw-Text $g (">" + $feels + $DEG) $fSmall $blackBrush 92 72 56 12 $sfRight
Draw-Text $g ($press.ToString() + "mm") $fSmall $blackBrush 4 84 84 12 $sfRight
Draw-Text $g $cur.observation_time[0] $fSmall $blackBrush 92 84 56 12 $sfRight

# Red separator
$g.FillRectangle($redBrush, 4, 100, $W - 8, 2)

# Three day forecast
$rows = @()
$today = (Get-Date).DayOfWeek
for ($i = 0; $i -lt 3; $i++) {
  if ($i -lt $j.weather.Count) { $rows += $j.weather[$i] } else { $rows += $null }
}
$baseY = 108
for ($i = 0; $i -lt 3; $i++) {
  $y = $baseY + $i * 62
  $dow = $DAYS[(([int]$today + $i) % 7)]
  Draw-Text $g $dow $fDay $blackBrush 2 ($y + 6) 38 16 $sfMid
  if ($rows[$i] -ne $null) {
    $ww = [int]$rows[$i].hourly[4].weatherCode
    Draw-Icon $g (GetIcon $ww) 38 ($y + 2) 34
    $hi = [int]$rows[$i].maxtempC
    $lo = [int]$rows[$i].mintempC
    Draw-Text $g ("+" + $hi + $DEG) $fHi $blackBrush 74 ($y + 2) 46 26 $sfRight
    Draw-Text $g ("+" + $lo + $DEG) $fLo $blackBrush 120 ($y + 2) 30 26 $sfRight
  }
}

$g.Dispose()

# 3x preview so the layout can be checked before flashing
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
for ($y = 0; $y -lt $H; $y++) {
  for ($x = 0; $x -lt $W; $x++) {
    $c = $bmp.GetPixel($x, $y)
    $idx = $y * $STRIDE + [int]([math]::Floor($x / 8))
    $bit = 0x80 -shr ($x % 8)
    if ($c.R -gt 120 -and $c.G -lt 110 -and $c.B -lt 110) {
      $red[$idx] = $red[$idx] -bor $bit
    } elseif (($c.R + $c.G + $c.B) -lt 330) {
      $black[$idx] = $black[$idx] -bor $bit
    }
  }
}
$bmp.Dispose()

$sb = New-Object System.Text.StringBuilder
[void]$sb.AppendLine("/* Generated by tools/make-weather.ps1. Do not edit. */")
[void]$sb.AppendLine("/* City: $($area)  temp $($temp)C  code $code */")
[void]$sb.AppendLine("#ifndef WEATHER_H")
[void]$sb.AppendLine("#define WEATHER_H")
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
Append-Array $sb "WEATHER_BLACK" $black
Append-Array $sb "WEATHER_RED" $red
[void]$sb.AppendLine("#endif")

[System.IO.File]::WriteAllText($OutFile, $sb.ToString(), (New-Object System.Text.UTF8Encoding($false)))
Write-Output ("Wrote " + $OutFile)
Write-Output ("Preview " + $PreviewFile)
Write-Output ("$area  +$temp$DEG  feels +$feels$DEG  " + $hum + "%  " + $wind + "m/s  " + $press + "mm  code=" + $code)

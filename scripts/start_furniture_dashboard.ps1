param([int]$Port = 8003)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
$day1 = @(Get-ChildItem -LiteralPath (Join-Path $projectRoot 'source') -Directory | Where-Object Name -Like '*_day1')
if ($day1.Count -ne 1) { throw 'Expected exactly one day1 source directory' }
$weights = Join-Path $day1[0].FullName 'runs/furniture_spec1_20261022/weights/best.pt'
if (-not (Test-Path -LiteralPath $weights)) { throw "Furniture weights missing: $weights" }
$env:CORE_YOLO_MODEL = $weights
Set-Location $projectRoot
& "$projectRoot/.venv/Scripts/python.exe" -m uvicorn main:app --host 127.0.0.1 --port $Port

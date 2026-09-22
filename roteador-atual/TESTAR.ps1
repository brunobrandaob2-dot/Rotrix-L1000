# Testa gatilhos contra a base, sem precisar do Handy.
$ErrorActionPreference = "Stop"
$OutputEncoding = [Console]::OutputEncoding = [Text.Encoding]::UTF8
$pasta = $PSScriptRoot; if (-not $pasta) { $pasta = "$env:USERPROFILE\Documents\laudo-router" }
$py = $null
foreach ($c in @("$env:LOCALAPPDATA\Programs\Python\Python313\python.exe",
                 "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
                 "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe")) {
  if (Test-Path $c) { $py = $c; break } }
if (-not $py) { Write-Host "Python nao encontrado." -ForegroundColor Red; Read-Host; exit 1 }
Push-Location $pasta
& $py testar.py $args
Pop-Location
Write-Host ""
Read-Host "Enter para fechar"

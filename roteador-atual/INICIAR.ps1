# Sobe o roteador. Feche esta janela para parar.
$ErrorActionPreference = "Stop"
$OutputEncoding = [Console]::OutputEncoding = [Text.Encoding]::UTF8
$pasta = $PSScriptRoot
if (-not $pasta) { $pasta = "$env:USERPROFILE\Documents\laudo-router" }
$py = $null
foreach ($c in @("$env:LOCALAPPDATA\Programs\Python\Python313\python.exe",
                 "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
                 "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe")) {
  if (Test-Path $c) { $py = $c; break } }
if (-not $py) { Write-Host "Python nao encontrado." -ForegroundColor Red; Read-Host; exit 1 }

Get-Process python, pythonw -ErrorAction SilentlyContinue |
  Where-Object { $_.Path -like "*Python*" } | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Milliseconds 300

Write-Host ""
Write-Host "  ROTEADOR DE LAUDOS   127.0.0.1:8123" -ForegroundColor Cyan
Write-Host "  Nao feche esta janela enquanto estiver laudando." -ForegroundColor Yellow
Write-Host ""
Set-Location -Path $pasta
& $py roteador.py
Write-Host ""
Write-Host "  O roteador parou." -ForegroundColor Red
Read-Host "Enter para fechar"

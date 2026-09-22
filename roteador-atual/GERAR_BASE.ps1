# Rode depois de acrescentar ou editar mascaras em dados\mascaras
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

Write-Host ""
Write-Host "  Reconstruindo a base de mascaras" -ForegroundColor Cyan
Write-Host ""
Push-Location $pasta
& $py construir_base.py
$ok = ($LASTEXITCODE -eq 0)
Pop-Location

if ($ok) {
  Write-Host ""
  Write-Host "  Reiniciando o roteador para carregar a base nova..." -ForegroundColor Cyan
  Get-Process python, pythonw -ErrorAction SilentlyContinue |
    Where-Object { $_.Path -like "*Python*" } | Stop-Process -Force -ErrorAction SilentlyContinue
  Start-Sleep -Milliseconds 400
  $pyw = $py -replace "python\.exe$", "pythonw.exe"
  if (-not (Test-Path $pyw)) { $pyw = $py }
  Start-Process -FilePath $pyw -ArgumentList "roteador.py" -WorkingDirectory $pasta
  Write-Host "  [ok] roteador rodando com a base nova" -ForegroundColor Green
} else {
  Write-Host "  [X] a base nao foi gerada. O roteador continua com a base anterior." -ForegroundColor Red
}
Write-Host ""
Read-Host "Enter para fechar"

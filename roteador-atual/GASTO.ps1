# Mostra quanto a rota de nuvem gastou neste mes.
$ErrorActionPreference = "Stop"
$OutputEncoding = [Console]::OutputEncoding = [Text.Encoding]::UTF8
$pasta = "$env:USERPROFILE\Documents\laudo-router"
$py = $null
foreach ($c in @("$env:LOCALAPPDATA\Programs\Python\Python313\python.exe",
                 "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
                 "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe")) {
  if (Test-Path $c) { $py = $c; break }
}
if (-not $py) { Write-Host "Python nao encontrado." -ForegroundColor Red; Read-Host; exit 1 }
Push-Location $pasta
& $py nuvem.py
Write-Host "  ----------------------------------------"
Write-Host "  ultimas chamadas (nuvem.log):" -ForegroundColor Cyan
if (Test-Path "$pasta\nuvem.log") {
  Get-Content "$pasta\nuvem.log" -Tail 10 | ForEach-Object { Write-Host "  $_" -ForegroundColor DarkGray }
} else {
  Write-Host "  (nenhuma chamada ainda)" -ForegroundColor DarkGray
}
Pop-Location
Write-Host ""
Write-Host "  O valor oficial esta em console.anthropic.com/settings/usage" -ForegroundColor DarkCyan
Write-Host ""
Read-Host "Enter para fechar"

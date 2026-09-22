# ============================================================
#  ATUALIZAR o Roteador de Laudos a partir do zip em pacote\
#  Extrai o pacote e roda o instalador. Chave, gasto, aprendizado
#  e mascaras criadas por voce sao preservados.
# ============================================================
$ErrorActionPreference = "Stop"
$OutputEncoding = [Console]::OutputEncoding = [Text.Encoding]::UTF8
$pasta = $PSScriptRoot; if (-not $pasta) { $pasta = "$env:USERPROFILE\Documents\laudo-router" }
$tmp  = "$env:TEMP\roteador-pacote"

Clear-Host
Write-Host ""
Write-Host "  Atualizando o Roteador de Laudos" -ForegroundColor Cyan
Write-Host ""

$zip = $null
foreach ($z in @("$pasta\pacote\Roteador-de-Laudos-Instalador.zip",
                 "$env:USERPROFILE\Documents\Roteador-de-Laudos-Instalador.zip")) {
  if (Test-Path $z) { $zip = $z; break }
}
if (-not $zip) {
  Write-Host "  [X] nao achei o zip em pacote\ nem em Documentos" -ForegroundColor Red
  Read-Host "Enter para fechar"; exit 1
}
Write-Host "  pacote: $zip" -ForegroundColor DarkCyan

Unblock-File $zip -ErrorAction SilentlyContinue
if (Test-Path $tmp) { Remove-Item $tmp -Recurse -Force }
Expand-Archive -Path $zip -DestinationPath $tmp -Force
$inst = Get-ChildItem $tmp -Recurse -Filter "INSTALAR.ps1" | Select-Object -First 1
if (-not $inst) { Write-Host "  [X] INSTALAR.ps1 nao encontrado no zip" -ForegroundColor Red; Read-Host; exit 1 }
Write-Host "  [ok] pacote extraido, rodando o instalador..." -ForegroundColor Green
Write-Host ""

# roda o instalador FORA da pasta laudo-router, para ela nao ficar presa
Set-Location $env:TEMP
& powershell -ExecutionPolicy Bypass -File $inst.FullName

# guarda o zip novo dentro da instalacao
$dest = "$env:USERPROFILE\Documents\laudo-router\pacote"
if (Test-Path "$env:USERPROFILE\Documents\laudo-router\roteador.py") {
  New-Item -ItemType Directory -Path $dest -Force | Out-Null
  if ($zip -ne "$dest\Roteador-de-Laudos-Instalador.zip") {
    Copy-Item $zip "$dest\Roteador-de-Laudos-Instalador.zip" -Force
  }
}
Remove-Item $tmp -Recurse -Force -ErrorAction SilentlyContinue

# Desfaz a instalacao: restaura o settings do Handy e remove os atalhos.
$ErrorActionPreference = "Continue"
$OutputEncoding = [Console]::OutputEncoding = [Text.Encoding]::UTF8
Write-Host ""
Write-Host "  Desinstalando o Roteador de Laudos..." -ForegroundColor Cyan

$proc = Get-Process handy -ErrorAction SilentlyContinue
while ($proc) {
  Write-Host "  Feche o Handy primeiro (bandeja -> Quit)." -ForegroundColor Yellow
  Read-Host "  Enter depois de fechar"
  $proc = Get-Process handy -ErrorAction SilentlyContinue
}

Get-Process python, pythonw -ErrorAction SilentlyContinue |
  Where-Object { $_.Path -and (Get-CimInstance Win32_Process -Filter "ProcessId=$($_.Id)").CommandLine -like "*roteador.py*" } |
  Stop-Process -Force -ErrorAction SilentlyContinue

$dir = "$env:APPDATA\com.pais.handy"
$bk = Get-ChildItem "$dir\settings_store.json.backup-*" -ErrorAction SilentlyContinue |
      Sort-Object Name | Select-Object -First 1
if ($bk) {
  Copy-Item $bk.FullName "$dir\settings_store.json" -Force
  Write-Host "  [ok] configuracao do Handy restaurada ($($bk.Name))" -ForegroundColor Green
} else {
  Write-Host "  [!] nenhum backup encontrado; configuracao do Handy nao foi alterada" -ForegroundColor Yellow
}

Remove-Item "$env:USERPROFILE\Desktop\Roteador de Laudos.lnk" -ErrorAction SilentlyContinue
Remove-Item "$([Environment]::GetFolderPath('Startup'))\Roteador de Laudos.lnk" -ErrorAction SilentlyContinue
Write-Host "  [ok] atalhos removidos" -ForegroundColor Green
Write-Host ""
Write-Host "  A pasta Documentos\laudo-router foi mantida (contem suas mascaras)." -ForegroundColor Cyan
Write-Host "  Apague manualmente se quiser remover tudo." -ForegroundColor Cyan
Write-Host ""
Read-Host "Enter para fechar"

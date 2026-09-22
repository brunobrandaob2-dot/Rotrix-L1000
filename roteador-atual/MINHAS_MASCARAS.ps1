# ============================================================
#  MINHAS MASCARAS - inclui as suas mascaras e os seus laudos
#  de estilo no Roteador de Laudos, e escolhe quais mascaras
#  valem (so as do Rotrix, so as suas, ou as duas).
#  Usa importar_usuario.py. O roteador pega a base nova sozinho.
# ============================================================
$OutputEncoding = [Console]::OutputEncoding = [Text.Encoding]::UTF8
$pasta = $PSScriptRoot
if (-not $pasta) { $pasta = "$env:USERPROFILE\Documents\laudo-router" }
Set-Location $pasta

$py = $null
foreach ($c in @("$env:LOCALAPPDATA\Programs\Python\Python313\python.exe",
                 "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
                 "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe")) {
  if (Test-Path $c) { $py = $c; break } }
if (-not $py) { $py = "python" }
$env:PYTHONUTF8 = "1"

function Escolher-Arquivo($titulo) {
  Add-Type -AssemblyName System.Windows.Forms
  $d = New-Object System.Windows.Forms.OpenFileDialog
  $d.Title = $titulo
  $d.Filter = "Mascaras ou laudos (*.txt;*.docx;*.rtf;*.md)|*.txt;*.docx;*.rtf;*.md"
  $d.InitialDirectory = [Environment]::GetFolderPath("MyDocuments")
  if ($d.ShowDialog() -eq "OK") { return $d.FileName }
  return $null
}

while ($true) {
  Clear-Host
  Write-Host ""
  Write-Host "  MINHAS MASCARAS - Roteador de Laudos" -ForegroundColor Cyan
  Write-Host ""
  & $py importar_usuario.py listar
  Write-Host ""
  Write-Host "  1  Incluir arquivo de mascaras (.txt, .docx, .rtf, .md)"
  Write-Host "  2  Incluir arquivo com meus laudos (estilo para a IA; sem dados de paciente)"
  Write-Host "  3  Usar so as mascaras do Rotrix"
  Write-Host "  4  Usar so as minhas mascaras"
  Write-Host "  5  Usar as duas (a minha vale quando o comando e o mesmo)"
  Write-Host "  6  Remover as minhas mascaras"
  Write-Host "  7  Remover os meus laudos de estilo"
  Write-Host "  0  Sair"
  Write-Host ""
  $op = Read-Host "  Escolha"
  Write-Host ""
  switch ($op) {
    "1" { $a = Escolher-Arquivo "Arquivo com as suas mascaras"
          if ($a) {
            $sub = ""
            if ((Read-Host "  Trocar as mascaras que voce ja incluiu por estas? (S = trocar, N = somar)") -match "^[sS]") { $sub = "--substituir" }
            if ($sub) { & $py importar_usuario.py mascaras "$a" $sub } else { & $py importar_usuario.py mascaras "$a" }
          } }
    "2" { $a = Escolher-Arquivo "Arquivo com os seus laudos"; if ($a) { & $py importar_usuario.py laudos "$a" } }
    "3" { & $py importar_usuario.py fonte rotrix }
    "4" { & $py importar_usuario.py fonte minhas }
    "5" { & $py importar_usuario.py fonte ambas }
    "6" { if ((Read-Host "  Remover TODAS as suas mascaras? (S/N)") -match "^[sS]") { & $py importar_usuario.py remover mascaras } }
    "7" { if ((Read-Host "  Remover TODOS os seus laudos de estilo? (S/N)") -match "^[sS]") { & $py importar_usuario.py remover laudos } }
    "0" { exit }
    default { continue }
  }
  Write-Host ""
  Read-Host "  Enter para voltar ao menu" | Out-Null
}

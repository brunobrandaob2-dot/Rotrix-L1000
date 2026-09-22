# ============================================================
#  CHAVE DA API  —  grava a chave e testa a rota de nuvem
#
#  Le a chave da AREA DE TRANSFERENCIA, nao do teclado.
#  Colar num prompt de console trunca chaves longas; copiar e
#  colar pela area de transferencia nao trunca.
# ============================================================
$ErrorActionPreference = "Stop"
$OutputEncoding = [Console]::OutputEncoding = [Text.Encoding]::UTF8
$pasta = $PSScriptRoot
if (-not $pasta) { $pasta = "$env:USERPROFILE\Documents\laudo-router" }

function Ok($t)    { Write-Host "  [ok] $t" -ForegroundColor Green }
function Aviso($t) { Write-Host "  [!]  $t" -ForegroundColor Yellow }
function Falha($t) { Write-Host ""; Write-Host "  [X]  $t" -ForegroundColor Red; Write-Host ""; Read-Host "Enter para fechar"; exit 1 }

Clear-Host
Write-Host ""
Write-Host "  ============================================" -ForegroundColor Cyan
Write-Host "   CHAVE DA API - rota de nuvem" -ForegroundColor Cyan
Write-Host "  ============================================" -ForegroundColor Cyan
Write-Host ""

if (-not (Test-Path "$pasta\roteador.py")) { Falha "nao achei a instalacao em $pasta" }
$py = $null
foreach ($c in @("$env:LOCALAPPDATA\Programs\Python\Python313\python.exe",
                 "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
                 "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe")) {
  if (Test-Path $c) { $py = $c; break } }
if (-not $py) { Falha "Python nao encontrado." }

$arqChave = "$pasta\chave_anthropic.txt"
if (Test-Path $arqChave) {
  $atual = (Get-Content $arqChave -Raw).Trim()
  Write-Host "  Ja existe uma chave guardada, com $($atual.Length) caracteres." -ForegroundColor DarkCyan
  if ($atual.Length -lt 50) {
    Aviso "esse tamanho e curto demais para uma chave da Anthropic."
    Aviso "provavelmente ela foi truncada ao ser colada. Vamos refazer."
  } else {
    $r = Read-Host "  Trocar por outra? (s/N)"
    if ($r -notmatch "^[sSyY]") {
      Write-Host ""
      Ok "mantendo a chave atual"
      $pular = $true
    }
  }
}

if (-not $pular) {
  Write-Host ""
  Write-Host "  COPIE A CHAVE AGORA" -ForegroundColor Yellow
  Write-Host ""
  Write-Host "   1. Abra  https://console.anthropic.com/settings/keys" -ForegroundColor DarkCyan
  Write-Host "   2. Clique no botao de copiar da chave (ou selecione TUDO" -ForegroundColor DarkCyan
  Write-Host "      e Ctrl+C). Ela comeca com  sk-ant-  e tem mais de" -ForegroundColor DarkCyan
  Write-Host "      100 caracteres." -ForegroundColor DarkCyan
  Write-Host "   3. Volte aqui e aperte Enter." -ForegroundColor DarkCyan
  Write-Host ""
  Write-Host "   Nao precisa colar nesta janela. Eu leio da area de" -ForegroundColor DarkGray
  Write-Host "   transferencia, que nao trunca." -ForegroundColor DarkGray
  Write-Host ""
  Read-Host "  Enter quando a chave estiver copiada"

  $chave = ""
  try { $chave = (Get-Clipboard -Raw -ErrorAction Stop) } catch { $chave = "" }
  if ($chave) { $chave = $chave.Trim() -replace "\s", "" }

  if (-not $chave) {
    Aviso "a area de transferencia esta vazia."
    Write-Host ""
    Write-Host "   Alternativa: vou abrir o Bloco de Notas. Cole a chave la," -ForegroundColor Yellow
    Write-Host "   salve e feche." -ForegroundColor Yellow
    Read-Host "   Enter para abrir"
    "" | Set-Content $arqChave -Encoding UTF8
    Start-Process notepad.exe $arqChave -Wait
    $chave = (Get-Content $arqChave -Raw).Trim() -replace "\s", ""
  }

  Write-Host ""
  Write-Host "  Chave lida: $($chave.Length) caracteres, comeca com '$($chave.Substring(0,[Math]::Min(10,$chave.Length)))...'" -ForegroundColor DarkCyan

  if (-not $chave) { Falha "nao consegui ler a chave." }
  if (-not $chave.StartsWith("sk-ant-")) {
    Aviso "a chave nao comeca com sk-ant-. Confira se copiou a chave certa."
  }
  if ($chave.Length -lt 50) {
    Falha ("a chave tem so $($chave.Length) caracteres.`n" +
           "       Uma chave da Anthropic tem bem mais de 100.`n" +
           "       Foi copiada pela metade. Copie de novo, inteira, e rode isto outra vez.")
  }

  [IO.File]::WriteAllText($arqChave, $chave, (New-Object Text.UTF8Encoding $false))
  Ok "chave gravada ($($chave.Length) caracteres), so nesta maquina"
}

# ---------- teste real ----------
Write-Host ""
Write-Host "  Testando a conexao com a API..." -ForegroundColor Cyan
Push-Location $pasta
$teste = & $py -c @"
import nuvem
t, o = nuvem.chamar('Responda apenas: rota ativa.', modo='revisao')
print('ORIGEM:', o)
print('TEXTO:', (t or '')[:200])
"@ 2>&1
Pop-Location
Write-Host ""
$teste | ForEach-Object { Write-Host "  $_" -ForegroundColor DarkGray }
$txt = ($teste | Out-String)

Write-Host ""
if ($txt -match "ORIGEM: nuvem\s*$" -or $txt -match "ORIGEM: nuvem\r?\n") {
  Write-Host "  ============================================" -ForegroundColor Green
  Write-Host "   ROTA DE NUVEM FUNCIONANDO" -ForegroundColor Green
  Write-Host "  ============================================" -ForegroundColor Green
} elseif ($txt -match "401") {
  Aviso "401 - a API nao aceitou a chave."
  Write-Host "       - a chave foi copiada pela metade, ou" -ForegroundColor Yellow
  Write-Host "       - foi revogada, ou" -ForegroundColor Yellow
  Write-Host "       - e de outra conta / outro servico." -ForegroundColor Yellow
  Write-Host "       Gere uma nova em console.anthropic.com/settings/keys" -ForegroundColor Yellow
} elseif ($txt -match "400|credit|billing") {
  Aviso "a conta parece estar sem credito."
  Write-Host "       console.anthropic.com/settings/billing" -ForegroundColor Yellow
} elseif ($txt -match "429") {
  Aviso "429 - limite de uso da conta atingido. Tente daqui a pouco."
} else {
  Aviso "nao consegui confirmar. Veja a mensagem acima."
}

# ---------- religar o roteador ----------
Get-Process python, pythonw -ErrorAction SilentlyContinue |
  Where-Object { $_.Path -like "*Python*" } | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Milliseconds 400
$pyw = $py -replace "python\.exe$", "pythonw.exe"
if (-not (Test-Path $pyw)) { $pyw = $py }
Start-Process -FilePath $pyw -ArgumentList "roteador.py" -WorkingDirectory $pasta
Ok "roteador religado"

Write-Host ""
Write-Host "  Gatilhos de nuvem:" -ForegroundColor Cyan
Write-Host "    revisar / corrigir / passar a limpo   -> revisao de texto" -ForegroundColor DarkCyan
Write-Host "    recist / comparar exames / analise    -> analise" -ForegroundColor DarkCyan
Write-Host "  Todo o resto continua local e instantaneo." -ForegroundColor DarkGray
Write-Host "  Para ver o gasto:  GASTO.ps1" -ForegroundColor DarkGray
Write-Host ""
Read-Host "Enter para fechar"

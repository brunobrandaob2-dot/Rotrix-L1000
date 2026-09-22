# ============================================================
#  APLICAR_ATUALIZACAO - atualiza mascaras e motor NO LUGAR,
#  sem trocar a pasta. Usa pacote\atualizacao.zip.
#  Chave, gasto, aprendizado e config.json nao sao tocados.
# ============================================================
$ErrorActionPreference = "Stop"
$OutputEncoding = [Console]::OutputEncoding = [Text.Encoding]::UTF8
$pasta = $PSScriptRoot
if (-not $pasta) { $pasta = "$env:USERPROFILE\Documents\laudo-router" }
$zip = "$pasta\pacote\atualizacao.zip"

Clear-Host
Write-Host ""
Write-Host "  Aplicando a atualizacao do Roteador de Laudos" -ForegroundColor Cyan
Write-Host ""
if (-not (Test-Path $zip)) {
  Write-Host "  [X] nao achei pacote\atualizacao.zip" -ForegroundColor Red
  Read-Host "Enter para fechar"; exit 1
}

$py = $null
foreach ($c in @("$env:LOCALAPPDATA\Programs\Python\Python313\python.exe",
                 "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
                 "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe")) {
  if (Test-Path $c) { $py = $c; break } }
if (-not $py) { Write-Host "  [X] Python nao encontrado." -ForegroundColor Red; Read-Host; exit 1 }

# 1. para o roteador (pelo processo E por quem ocupa a porta 8123)
function Parar-Roteador {
  Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -like "python*" -and $_.CommandLine -match "roteador\.py" } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
  try {
    Get-NetTCPConnection -LocalPort 8123 -State Listen -ErrorAction Stop |
      ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }
  } catch {}
  Start-Sleep -Milliseconds 800
}
Parar-Roteador
Parar-Roteador
Write-Host "  [ok] roteador parado" -ForegroundColor Green

# 2. copia de seguranca das mascaras atuais
$ts = Get-Date -Format "yyyyMMdd-HHmmss"
$bk = "$pasta\pacote\mascaras-antes-$ts.zip"
Compress-Archive -Path "$pasta\dados\mascaras" -DestinationPath $bk -Force
Write-Host "  [ok] mascaras antigas guardadas em pacote\$(Split-Path $bk -Leaf)" -ForegroundColor Green

# 3. extrai por cima (regras suas do ouvido.tsv sao mantidas)
$ov = "$pasta\dados\ouvido.tsv"
$ovOld = @(); if (Test-Path $ov) { $ovOld = @(Get-Content $ov -Encoding UTF8) }
Unblock-File $zip -ErrorAction SilentlyContinue
Expand-Archive -Path $zip -DestinationPath $pasta -Force
if ($ovOld.Count -gt 0) {
  $ovNew = @(Get-Content $ov -Encoding UTF8)
  $add = @($ovOld | Where-Object { $_ -and -not $_.StartsWith("#") -and ($ovNew -notcontains $_) })
  if ($add.Count -gt 0) { Add-Content -Path $ov -Value $add -Encoding UTF8 }
}
Write-Host "  [ok] arquivos novos copiados" -ForegroundColor Green

# 4. base nova
Push-Location $pasta
& $py construir_base.py
$ok = ($LASTEXITCODE -eq 0)
Pop-Location
if (-not $ok) { Write-Host "  [X] falha ao gerar a base" -ForegroundColor Red; Read-Host; exit 1 }

# 4b. vocabulario do Handy (termos que o Whisper mais erra vao para o fim)
$h = Get-Process -Name handy -ErrorAction SilentlyContinue | Select-Object -First 1
$hp = $null
if ($h) { $hp = $h.Path; Stop-Process -Id $h.Id -Force -ErrorAction SilentlyContinue; Start-Sleep -Seconds 1 }
Push-Location $pasta
& $py configurar_handy.py | Out-Null
Pop-Location
if ($hp) { Start-Process -FilePath $hp }
Write-Host "  [ok] vocabulario do Handy atualizado" -ForegroundColor Green

# 5. sobe o roteador
$pyw = $py -replace "python\.exe$", "pythonw.exe"
if (-not (Test-Path $pyw)) { $pyw = $py }
Start-Process -FilePath $pyw -ArgumentList "roteador.py" -WorkingDirectory $pasta
Start-Sleep -Seconds 2

# 6. confere: o roteador que responde e o NOVO?
$esperada = (Select-String -Path "$pasta\roteador.py" -Pattern 'VERSAO = "([^"]+)"').Matches[0].Groups[1].Value
$v = $null
for ($i = 0; $i -lt 10 -and -not $v; $i++) {
  Start-Sleep -Seconds 1
  try { $v = (Invoke-RestMethod -Uri "http://127.0.0.1:8123/v1/versao" -TimeoutSec 2).versao } catch {}
}
if ($v -eq $esperada) {
  Write-Host "  [ok] roteador novo rodando (versao $v)" -ForegroundColor Green
} elseif ($v) {
  Write-Host "  [!] ainda responde um roteador ANTIGO ($v). Reinicie o computador e teste de novo." -ForegroundColor Yellow
} else {
  Write-Host "  [!] o roteador nao respondeu. Rode INICIAR.ps1 ou reinicie o computador." -ForegroundColor Yellow
}
Write-Host ""
Write-Host "  Pronto. Pode usar o Ctrl+Alt+Espaco." -ForegroundColor Cyan
Write-Host ""
Read-Host "Enter para fechar"

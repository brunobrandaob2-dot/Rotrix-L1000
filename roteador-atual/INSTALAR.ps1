# ============================================================
#  ROTEADOR DE LAUDOS  -  instalador
#  Clique com o botao direito neste arquivo -> "Executar com o PowerShell"
# ============================================================
$ErrorActionPreference = "Stop"
$OutputEncoding = [Console]::OutputEncoding = [Text.Encoding]::UTF8

# ---------- trava de seguranca ----------
# Este arquivo precisa ser EXECUTADO. Se o conteudo for colado dentro de uma
# janela do PowerShell, $PSScriptRoot fica vazio e a instalacao vai para o
# lugar errado. Aqui a gente para antes de tocar em nada.
if (-not $PSScriptRoot -or -not (Test-Path "$PSScriptRoot\app\roteador.py")) {
  Write-Host ""
  Write-Host "  ============================================" -ForegroundColor Red
  Write-Host "   ESTE ARQUIVO NAO PODE SER COLADO" -ForegroundColor Red
  Write-Host "  ============================================" -ForegroundColor Red
  Write-Host ""
  Write-Host "  Feche esta janela e, na pasta onde estao os arquivos:" -ForegroundColor Yellow
  Write-Host "    clique com o botao DIREITO em INSTALAR.ps1" -ForegroundColor Yellow
  Write-Host "    escolha 'Executar com o PowerShell'" -ForegroundColor Yellow
  Write-Host ""
  Write-Host "  (nenhum arquivo foi alterado)" -ForegroundColor DarkGray
  Write-Host ""
  Read-Host "Enter para fechar"
  exit 1
}
Set-Location -Path $PSScriptRoot

function Titulo($t) { Write-Host ""; Write-Host "  $t" -ForegroundColor Cyan }
function Ok($t)     { Write-Host "  [ok] $t" -ForegroundColor Green }
function Aviso($t)  { Write-Host "  [!]  $t" -ForegroundColor Yellow }
function Falha($t)  { Write-Host ""; Write-Host "  [X]  $t" -ForegroundColor Red; Write-Host ""; Read-Host "Enter para fechar"; exit 1 }

Clear-Host
Write-Host ""
Write-Host "  ============================================" -ForegroundColor Cyan
Write-Host "   ROTEADOR DE LAUDOS - instalacao" -ForegroundColor Cyan
Write-Host "   camada de mascaras por voz sobre o Handy" -ForegroundColor DarkCyan
Write-Host "  ============================================" -ForegroundColor Cyan

# ---------- 1. Python ----------
Titulo "1/7  Procurando o Python"
$py = $null
foreach ($c in @("$env:LOCALAPPDATA\Programs\Python\Python313\python.exe",
                 "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
                 "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe",
                 "$env:ProgramFiles\Python313\python.exe",
                 "$env:ProgramFiles\Python312\python.exe")) {
  if (Test-Path $c) { $py = $c; break }
}
if (-not $py) {
  $cmd = Get-Command python -ErrorAction SilentlyContinue
  if ($cmd -and $cmd.Source -notlike "*WindowsApps*") { $py = $cmd.Source }
}
if (-not $py) {
  Aviso "Python nao encontrado. Tentando instalar automaticamente..."
  if (Get-Command winget -ErrorAction SilentlyContinue) {
    winget install -e --id Python.Python.3.13 --accept-source-agreements --accept-package-agreements
    $py = "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe"
  }
}
if (-not $py -or -not (Test-Path $py)) {
  Falha "Nao consegui encontrar nem instalar o Python.`n       Instale em https://www.python.org/downloads/ e rode este arquivo de novo."
}
Ok "Python: $py"

# ---------- 2. Handy ----------
Titulo "2/7  Procurando o Handy"
$cfg = "$env:APPDATA\com.pais.handy\settings_store.json"
if (-not (Test-Path $cfg)) {
  Falha "Handy nao encontrado neste computador.`n       Instale em https://handy.computer e abra o programa ao menos uma vez."
}
Ok "Handy encontrado"

$proc = Get-Process handy -ErrorAction SilentlyContinue
while ($proc) {
  Write-Host ""
  Aviso "O Handy esta ABERTO. Ele precisa ser fechado para a configuracao valer."
  Write-Host "       Feche pelo icone na bandeja (botao direito -> Quit)." -ForegroundColor Yellow
  Read-Host "       Depois de fechar, aperte Enter"
  $proc = Get-Process handy -ErrorAction SilentlyContinue
}
Ok "Handy fechado"

# ---------- 3. Copiar arquivos ----------
Titulo "3/7  Copiando arquivos"
$destino = "$env:USERPROFILE\Documents\laudo-router"
$ts      = Get-Date -Format "yyyyMMdd-HHmmss"
$stage   = "$destino-novo-$ts"

# O roteador em execucao PRENDE a pasta: o Windows nao renomeia uma pasta que
# e o diretorio de trabalho de um processo. Para antes de mexer.
function Parar-Roteador {
  Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -like "python*" -and $_.CommandLine -match "roteador\.py" } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
  Start-Sleep -Milliseconds 600
}
Parar-Roteador
Ok "roteador parado para a atualizacao"

# sobras de tentativas anteriores que falharam no meio
Get-ChildItem "$env:USERPROFILE\Documents" -Directory -Filter "laudo-router-novo-*" -ErrorAction SilentlyContinue |
  ForEach-Object { Remove-Item $_.FullName -Recurse -Force -ErrorAction SilentlyContinue; Aviso "removida sobra de tentativa anterior: $($_.Name)" }

# Copia primeiro para uma pasta nova. Se algo falhar aqui, a instalacao
# que ja existe nao foi tocada.
New-Item -ItemType Directory -Path $stage -Force | Out-Null
try {
  Copy-Item "$PSScriptRoot\app\*" $stage -Recurse -Force
} catch {
  Remove-Item $stage -Recurse -Force -ErrorAction SilentlyContinue
  Falha "nao consegui copiar os arquivos do pacote.`n       A instalacao que ja existia continua intacta."
}
if (-not (Test-Path "$stage\roteador.py")) {
  Remove-Item $stage -Recurse -Force -ErrorAction SilentlyContinue
  Falha "o pacote parece incompleto (roteador.py nao veio).`n       A instalacao que ja existia continua intacta."
}

# So agora troca de lugar.
if (Test-Path $destino) {
  $bk = "$destino-anterior-$ts"
  $movido = $false
  for ($t = 1; $t -le 3 -and -not $movido; $t++) {
    try { Move-Item $destino $bk -ErrorAction Stop; $movido = $true }
    catch { Parar-Roteador; Start-Sleep -Seconds 1 }
  }
  if (-not $movido) {
    Remove-Item $stage -Recurse -Force -ErrorAction SilentlyContinue
    Falha ("a pasta laudo-router esta em uso e nao pode ser substituida.`n" +
           "       Feche janelas do Explorador ou do PowerShell abertas nela e rode de novo.`n" +
           "       A instalacao atual continua intacta.")
  }
  Aviso "instalacao anterior guardada em: $(Split-Path $bk -Leaf)"
  # Mascaras que so existem na instalacao antiga voltam — mas as SOLTAS na raiz
  # de dados\mascaras vao para _legado (fora da compilacao): a raiz e lida
  # primeiro e elas sombreariam as mascaras novas de mesmo gatilho.
  $raizOld = "$bk\dados\mascaras"
  if (Test-Path $raizOld) {
    $nLeg = 0; $nUser = 0
    Get-ChildItem $raizOld -Recurse -File -Filter *.txt | ForEach-Object {
      $rel = $_.FullName.Substring($raizOld.Length + 1)
      if ($rel -notmatch "\\") { $alvo = "$stage\dados\mascaras\_legado\$rel" }
      else { $alvo = "$stage\dados\mascaras\$rel" }
      if (-not (Test-Path $alvo)) {
        New-Item -ItemType Directory -Path (Split-Path $alvo) -Force | Out-Null
        Copy-Item $_.FullName $alvo
        if ($rel -notmatch "\\") { $nLeg++ } else { $nUser++ }
      }
    }
    if ($nLeg)  { Aviso "$nLeg mascara(s) antiga(s) guardada(s) em dados\mascaras\_legado" }
    if ($nUser) { Ok "$nUser mascara(s) criada(s) por voce preservada(s)" }
  }
  # o que e seu e nao vem no pacote: chaves (todos os provedores), gasto, aprendizado, log
  $seus = @("gasto.json", "aprendizado.json", "nuvem.log")
  $seus += @(Get-ChildItem "$bk" -File -Filter "chave_*.txt" -ErrorAction SilentlyContinue | ForEach-Object { $_.Name })
  foreach ($f in $seus) {
    if (Test-Path "$bk\$f") { Copy-Item "$bk\$f" "$stage\$f" -Force; Ok "preservado: $f" }
  }
  # suas mascaras e seus laudos de estilo (Rotrix: importar_usuario.py)
  if (Test-Path "$bk\dados\mascaras_usuario") {
    Copy-Item "$bk\dados\mascaras_usuario" "$stage\dados\mascaras_usuario" -Recurse -Force
    Ok "preservadas: suas mascaras (dados\mascaras_usuario)"
  }
  Get-ChildItem "$bk\dados\estilo" -File -Filter "usuario_*.txt" -ErrorAction SilentlyContinue |
    ForEach-Object { Copy-Item $_.FullName "$stage\dados\estilo\$($_.Name)" -Force }
  # config.json: o do pacote + as suas escolhas por cima (prompt, IA por exame, fonte das mascaras)
  if (Test-Path "$bk\config.json") {
    try {
      $velho = Get-Content "$bk\config.json" -Raw -Encoding UTF8 | ConvertFrom-Json
      $novo = if (Test-Path "$stage\config.json") { Get-Content "$stage\config.json" -Raw -Encoding UTF8 | ConvertFrom-Json } else { [pscustomobject]@{} }
      foreach ($p in $velho.PSObject.Properties) { $novo | Add-Member -NotePropertyName $p.Name -NotePropertyValue $p.Value -Force }
      [IO.File]::WriteAllText("$stage\config.json", ($novo | ConvertTo-Json -Depth 10), (New-Object Text.UTF8Encoding $false))
      Ok "preservada: sua configuracao (config.json)"
    } catch { Aviso "nao consegui juntar o config.json antigo; ficou o do pacote (o antigo esta em $(Split-Path $bk -Leaf))" }
  }
}
Move-Item $stage $destino
Ok "instalado em: $destino"

# ---------- 4. Base ----------
Titulo "4/7  Gerando a base de mascaras"
Push-Location $destino
& $py construir_base.py
if ($LASTEXITCODE -ne 0) { Pop-Location; Falha "falha ao gerar a base." }
Pop-Location

# ---------- 5. Processador de colagem (v8 do Bruno + negrito) ----------
Titulo "5/7  Compilando o processador de colagem com negrito"
$hd = "$env:APPDATA\com.pais.handy"
$env:ROTEADOR_COLADOR_OK = "0"
try {
  Copy-Item "$destino\handy\handy_radiology_paste.cs" "$hd\handy_radiology_paste.cs" -Force
  $novo = "$hd\handy_radiology_paste.novo.exe"
  if (Test-Path $novo) { Remove-Item $novo -Force }
  Add-Type -Path "$hd\handy_radiology_paste.cs" `
    -ReferencedAssemblies @("System.dll","System.Core.dll","System.Windows.Forms.dll") `
    -OutputAssembly $novo -OutputType WindowsApplication
  $exe = "$hd\handy_radiology_paste.exe"
  if (Test-Path $exe) {
    Copy-Item $exe "$hd\handy_radiology_paste.anterior.exe" -Force
  }
  Move-Item $novo $exe -Force
  $env:ROTEADOR_COLADOR_OK = "1"
  Ok "processador compilado (o anterior ficou em handy_radiology_paste.anterior.exe)"
} catch {
  Aviso "nao consegui compilar o processador: $($_.Exception.Message)"
  Aviso "a colagem continua como estava e os titulos saem sem negrito."
}

# ---------- 6. Configurar o Handy ----------
Titulo "6/7  Configurando o Handy"
Push-Location $destino
& $py configurar_handy.py
if ($LASTEXITCODE -ne 0) { Pop-Location; Falha "falha ao configurar o Handy." }
Pop-Location

# ---------- 7. Atalhos e inicializacao ----------
Titulo "7/7  Criando atalhos"
$pyw = $py -replace "python\.exe$", "pythonw.exe"
if (-not (Test-Path $pyw)) { $pyw = $py }

# A Area de Trabalho pode estar no OneDrive ou com nome traduzido: pergunta ao
# Windows onde ela esta. E atalho que falhar NAO interrompe a instalacao.
try {
  $ws = New-Object -ComObject WScript.Shell
  $desk = [Environment]::GetFolderPath("Desktop")
  if ($desk -and (Test-Path $desk)) {
    $lnk = $ws.CreateShortcut("$desk\Roteador de Laudos.lnk")
    $lnk.TargetPath = $py
    $lnk.Arguments = "roteador.py"
    $lnk.WorkingDirectory = $destino
    $lnk.Description = "Inicia o Roteador de Laudos"
    $lnk.Save()
    Ok "atalho criado em: $desk"
  } else {
    Aviso "nao achei a Area de Trabalho; atalho nao criado (use INICIAR.ps1)"
  }
} catch { Aviso "atalho da Area de Trabalho nao criado: $($_.Exception.Message)" }

try {
  $startup = [Environment]::GetFolderPath("Startup")
  $lnk2 = $ws.CreateShortcut("$startup\Roteador de Laudos.lnk")
  $lnk2.TargetPath = $pyw
  $lnk2.Arguments = "roteador.py"
  $lnk2.WorkingDirectory = $destino
  $lnk2.Save()
  Ok "inicia junto com o Windows (sem janela)"
} catch { Aviso "atalho de inicializacao nao criado: $($_.Exception.Message)" }

# ---------- fim ----------
Write-Host ""
Write-Host "  ============================================" -ForegroundColor Green
Write-Host "   INSTALACAO CONCLUIDA" -ForegroundColor Green
Write-Host "  ============================================" -ForegroundColor Green
Write-Host ""
Write-Host "  COMO USAR" -ForegroundColor Cyan
Write-Host "    Ctrl + Space        ditado normal"
Write-Host "    Ctrl + Alt + Space  ditado com mascaras"
Write-Host ""
Write-Host "  EXPERIMENTE FALAR" -ForegroundColor Cyan
Write-Host '    "tomografia de torax"'
Write-Host '    "tomografia do abdome total com contraste, esteatose e apendicite"'
Write-Host '    "raio x de joelho direito com derrame articular"'
Write-Host '    "frase cisto hepatico simples"'
Write-Host ""
Write-Host "  Abra o Handy agora. O roteador ja esta rodando." -ForegroundColor Yellow
Write-Host ""

Start-Process -FilePath $pyw -ArgumentList "roteador.py" -WorkingDirectory $destino
Read-Host "Enter para fechar esta janela"

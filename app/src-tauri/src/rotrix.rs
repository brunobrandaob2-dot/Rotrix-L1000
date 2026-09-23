//! Rotrix L-1000: sobe o Roteador de Laudos junto com o app.
//!
//! O instalador traz, em `resources/rotrix/`:
//!   - `python/`   Python embutido (sem instalar nada no Windows)
//!   - `roteador/` o roteador (roteador.py, mascaras, base.sqlite, colador.exe ...)
//!
//! Na abertura, o roteador e copiado para a pasta de dados do usuario
//! (`%APPDATA%\com.rotrix.l1000\roteador`) quando a versao muda, preservando
//! os arquivos do usuario (chave, gasto, aprendizado, configuracao e as regras
//! dele no ouvido.tsv). Depois o app inicia o roteador em segundo plano
//! (porta 8123) e o encerra ao sair.

use log::{info, warn};
use once_cell::sync::Lazy;
use std::net::{SocketAddr, TcpStream};
use std::path::{Path, PathBuf};
use std::process::{Child, Command};
use std::sync::Mutex;
use std::time::Duration;
use tauri::{AppHandle, Manager};

use crate::settings::{self, ClipboardHandling, PasteMethod};

static ROUTER: Lazy<Mutex<Option<Child>>> = Lazy::new(|| Mutex::new(None));

/// Arquivos do usuario que a copia do pacote nunca sobrescreve.
const PRESERVAR: &[&str] = &[
    "config.json",
    "chave_anthropic.txt",
    "gasto.json",
    "aprendizado.json",
    "atalho.log",
    "nuvem.log",
];

fn pasta_recursos(app: &AppHandle) -> Option<PathBuf> {
    let base = app.path().resource_dir().ok()?;
    for c in [base.join("resources").join("rotrix"), base.join("rotrix")] {
        if c.join("roteador").join("roteador.py").exists() {
            return Some(c);
        }
    }
    None
}

fn pasta_dados(app: &AppHandle) -> Option<PathBuf> {
    let d = crate::portable::app_data_dir(app).ok()?;
    Some(d.join("roteador"))
}

fn versao(p: &Path) -> String {
    std::fs::read_to_string(p.join("VERSAO_PACOTE.txt"))
        .unwrap_or_default()
        .trim()
        .to_string()
}

/// ouvido.tsv: linhas do pacote + linhas que o usuario acrescentou.
fn juntar_ouvido(pacote: &Path, destino: &Path) -> std::io::Result<()> {
    let novo = std::fs::read_to_string(pacote)?;
    let antigo = std::fs::read_to_string(destino).unwrap_or_default();
    let linhas_novas: std::collections::HashSet<&str> = novo.lines().collect();
    let extras: Vec<&str> = antigo
        .lines()
        .filter(|l| !l.trim().is_empty() && !l.starts_with('#') && !linhas_novas.contains(l))
        .collect();
    let mut saida = novo.trim_end().to_string();
    if !extras.is_empty() {
        saida.push_str("\n# regras do usuario preservadas na atualizacao\n");
        saida.push_str(&extras.join("\n"));
    }
    saida.push('\n');
    std::fs::write(destino, saida)
}

fn copiar_arvore(origem: &Path, destino: &Path) -> std::io::Result<()> {
    std::fs::create_dir_all(destino)?;
    for entrada in std::fs::read_dir(origem)? {
        let entrada = entrada?;
        let p = entrada.path();
        let alvo = destino.join(entrada.file_name());
        if p.is_dir() {
            copiar_arvore(&p, &alvo)?;
            continue;
        }
        let nome = entrada.file_name().to_string_lossy().to_string();
        if alvo.exists() {
            if PRESERVAR.contains(&nome.as_str()) {
                continue;
            }
            if nome == "ouvido.tsv" {
                juntar_ouvido(&p, &alvo)?;
                continue;
            }
        }
        std::fs::copy(&p, &alvo)?;
    }
    Ok(())
}

fn porta_ocupada() -> bool {
    let addr: SocketAddr = "127.0.0.1:8123".parse().unwrap();
    TcpStream::connect_timeout(&addr, Duration::from_millis(250)).is_ok()
}

/// Na primeira vez, usa o colador com negrito (texto rico) que vem no pacote.
fn configurar_colagem(app: &AppHandle, dados: &Path) {
    let colador = dados.join("colador.exe");
    if !colador.exists() {
        return;
    }
    let mut s = settings::get_settings(app);
    if s.external_script_path.is_none() {
        s.external_script_path = Some(colador.to_string_lossy().to_string());
        s.paste_method = PasteMethod::ExternalScript;
        s.clipboard_handling = ClipboardHandling::DontModify;
        settings::write_settings(app, s);
        info!("Rotrix: colagem com negrito configurada ({})", colador.display());
    }
}

pub fn iniciar(app: &AppHandle) {
    let (recursos, dados) = match (pasta_recursos(app), pasta_dados(app)) {
        (Some(r), Some(d)) => (r, d),
        _ => {
            warn!("Rotrix: pacote do roteador nao encontrado; pos-processamento local indisponivel");
            return;
        }
    };
    let origem = recursos.join("roteador");
    if versao(&origem) != versao(&dados) || !dados.join("roteador.py").exists() {
        match copiar_arvore(&origem, &dados) {
            Ok(_) => info!("Rotrix: roteador instalado/atualizado em {}", dados.display()),
            Err(e) => warn!("Rotrix: falha ao copiar o roteador: {e}"),
        }
    }
    configurar_colagem(app, &dados);

    if porta_ocupada() {
        info!("Rotrix: ja existe um roteador na porta 8123; usando o que esta rodando");
        return;
    }

    let py_dir = recursos.join("python");
    let py = if py_dir.join("pythonw.exe").exists() {
        py_dir.join("pythonw.exe")
    } else if py_dir.join("python.exe").exists() {
        py_dir.join("python.exe")
    } else {
        PathBuf::from(if cfg!(windows) { "pythonw" } else { "python3" })
    };

    let mut cmd = Command::new(&py);
    cmd.arg(dados.join("roteador.py"))
        .current_dir(&dados)
        .env("PYTHONUTF8", "1")
        .env("PYTHONDONTWRITEBYTECODE", "1")
        .env("ROTEADOR_COLADOR", dados.join("colador.exe"));
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        const CREATE_NO_WINDOW: u32 = 0x0800_0000;
        cmd.creation_flags(CREATE_NO_WINDOW);
    }
    match cmd.spawn() {
        Ok(child) => {
            info!("Rotrix: roteador iniciado (pid {})", child.id());
            *ROUTER.lock().unwrap() = Some(child);
        }
        Err(e) => warn!("Rotrix: nao consegui iniciar o roteador com {}: {e}", py.display()),
    }
}

pub fn encerrar() {
    if let Ok(mut g) = ROUTER.lock() {
        if let Some(mut child) = g.take() {
            let _ = child.kill();
            let _ = child.wait();
            info!("Rotrix: roteador encerrado");
        }
    }
}

/// Pasta do roteador na maquina do usuario (para o item "Abrir pasta do roteador").
pub fn pasta_roteador(app: &AppHandle) -> Option<PathBuf> {
    pasta_ativa(app)
}

fn fmt_usd(v: f64) -> String {
    format!("US$ {:.2}", v).replace('.', ",")
}

/// Resumo do gasto com IA para o menu da bandeja:
/// "IA: hoje US$ 0,31 · mês US$ 4,20 de 25" (le gasto.json, nuvem.log e config.json).
pub fn resumo_gasto(app: &AppHandle) -> Option<String> {
    let dados = pasta_ativa_cache(app)?;
    if !dados.join("roteador.py").exists() {
        return None;
    }
    let ler_json = |nome: &str| -> Option<serde_json::Value> {
        let txt = std::fs::read_to_string(dados.join(nome)).ok()?;
        serde_json::from_str(&txt).ok()
    };
    let mes_atual = chrono::Local::now().format("%Y-%m").to_string();
    let hoje = chrono::Local::now().format("%Y-%m-%d").to_string();

    let mut mes_usd = 0.0;
    let mut chamadas: u64 = 0;
    if let Some(g) = ler_json("gasto.json") {
        if g.get("mes").and_then(|v| v.as_str()) == Some(mes_atual.as_str()) {
            mes_usd = g.get("usd").and_then(|v| v.as_f64()).unwrap_or(0.0);
            chamadas = g.get("chamadas").and_then(|v| v.as_u64()).unwrap_or(0);
        }
    }
    let limite = ler_json("config.json")
        .and_then(|c| c.get("limite_mes_usd").and_then(|v| v.as_f64()))
        .unwrap_or(0.0);

    // nuvem.log: "2026-09-22T10:00:00\tmodelo\testado\tin=..\tout=..\tusd=0.01234\tmes=.."
    let mut hoje_usd = 0.0;
    if let Ok(log) = std::fs::read_to_string(dados.join("nuvem.log")) {
        for linha in log.lines().filter(|l| l.starts_with(&hoje)) {
            if let Some(v) = linha
                .split('\t')
                .find_map(|c| c.strip_prefix("usd="))
                .and_then(|v| v.trim().parse::<f64>().ok())
            {
                hoje_usd += v;
            }
        }
    }

    if chamadas == 0 && hoje_usd == 0.0 {
        return Some("IA: nenhum uso neste mês".to_string());
    }
    let mut s = format!("IA: hoje {} · mês {}", fmt_usd(hoje_usd), fmt_usd(mes_usd));
    if limite > 0.0 {
        s.push_str(&format!(" de {}", fmt_usd(limite).replace("US$ ", "")));
    }
    Some(s)
}

// ---------------------------------------------------------------------------
// Comandos para a pagina "Rotrix" das configuracoes
// ---------------------------------------------------------------------------

#[derive(serde::Serialize, specta::Type)]
pub struct RotrixStatus {
    pub ativo: bool,
    pub versao: Option<String>,
    pub gatilhos: Option<u32>,
    pub gasto: Option<String>,
    pub pasta: Option<String>,
}

/// GET simples no roteador local (sem dependencias extras). Devolve o corpo.
fn http_get(caminho: &str) -> Option<String> {
    use std::io::{Read, Write};
    let addr: SocketAddr = "127.0.0.1:8123".parse().ok()?;
    let mut s = TcpStream::connect_timeout(&addr, Duration::from_millis(400)).ok()?;
    s.set_read_timeout(Some(Duration::from_millis(2500))).ok()?;
    let pedido = format!("GET {caminho} HTTP/1.0\r\nHost: 127.0.0.1\r\n\r\n");
    s.write_all(pedido.as_bytes()).ok()?;
    let mut bytes = Vec::new();
    s.read_to_end(&mut bytes).ok()?;
    let resp = String::from_utf8_lossy(&bytes).to_string();
    let (cab, corpo) = resp.split_once("\r\n\r\n")?;
    if !cab.starts_with("HTTP/1.0 200") && !cab.starts_with("HTTP/1.1 200") {
        return None;
    }
    Some(corpo.trim().to_string())
}

/// POST simples no roteador local (corpo JSON). Devolve o corpo da resposta.
/// Espera mais que o GET: importar perfil regera a base de mascaras.
fn http_post(caminho: &str, corpo: &str, espera_ms: u64) -> Result<String, String> {
    use std::io::{Read, Write};
    let addr: SocketAddr = "127.0.0.1:8123"
        .parse()
        .map_err(|_| "endereco invalido".to_string())?;
    let mut s = TcpStream::connect_timeout(&addr, Duration::from_millis(600))
        .map_err(|_| "roteador parado".to_string())?;
    s.set_read_timeout(Some(Duration::from_millis(espera_ms)))
        .map_err(|e| e.to_string())?;
    let pedido = format!(
        "POST {caminho} HTTP/1.0\r\nHost: 127.0.0.1\r\nContent-Type: application/json\r\n\
         Content-Length: {}\r\n\r\n{corpo}",
        corpo.as_bytes().len()
    );
    s.write_all(pedido.as_bytes()).map_err(|e| e.to_string())?;
    let mut bytes = Vec::new();
    s.read_to_end(&mut bytes).map_err(|e| e.to_string())?;
    let resp = String::from_utf8_lossy(&bytes).to_string();
    let (cab, body) = resp
        .split_once("\r\n\r\n")
        .ok_or_else(|| "resposta incompleta do roteador".to_string())?;
    if !cab.starts_with("HTTP/1.0 200") && !cab.starts_with("HTTP/1.1 200") {
        return Err(format!("roteador respondeu: {}", cab.lines().next().unwrap_or("")));
    }
    Ok(body.trim().to_string())
}

/// GET http://127.0.0.1:8123/v1/versao -> {"versao", "gatilhos", "pasta"}.
fn consultar_versao() -> Option<serde_json::Value> {
    serde_json::from_str(&http_get("/v1/versao")?).ok()
}

static PASTA_ATIVA: Lazy<Mutex<Option<PathBuf>>> = Lazy::new(|| Mutex::new(None));

/// Pasta do roteador que esta RODANDO (o de Documentos, quando ele ja ocupa a
/// porta 8123); senao, a pasta do roteador do app. Configuracoes feitas na tela
/// vao para essa pasta, para valerem de verdade.
pub fn pasta_ativa(app: &AppHandle) -> Option<PathBuf> {
    if let Some(v) = consultar_versao() {
        if let Some(p) = v.get("pasta").and_then(|x| x.as_str()) {
            let p = PathBuf::from(p);
            if p.join("roteador.py").exists() {
                if let Ok(mut g) = PASTA_ATIVA.lock() {
                    *g = Some(p.clone());
                }
                return Some(p);
            }
        }
    }
    pasta_dados(app)
}

/// Ultima pasta ativa conhecida, sem consultar o roteador (para a bandeja).
fn pasta_ativa_cache(app: &AppHandle) -> Option<PathBuf> {
    PASTA_ATIVA
        .lock()
        .ok()
        .and_then(|g| g.clone())
        .or_else(|| pasta_dados(app))
}

#[specta::specta]
#[tauri::command]
pub fn rotrix_status(app: AppHandle) -> RotrixStatus {
    let v = consultar_versao();
    RotrixStatus {
        ativo: v.is_some() || porta_ocupada(),
        versao: v
            .as_ref()
            .and_then(|j| j.get("versao"))
            .and_then(|x| x.as_str())
            .map(|x| x.to_string()),
        gatilhos: v
            .as_ref()
            .and_then(|j| j.get("gatilhos"))
            .and_then(|x| x.as_u64())
            .map(|x| x as u32),
        pasta: pasta_ativa(&app).map(|p| p.to_string_lossy().to_string()),
        gasto: resumo_gasto(&app),
    }
}

fn caminho_config(app: &AppHandle) -> Result<PathBuf, String> {
    pasta_ativa(app)
        .map(|d| d.join("config.json"))
        .ok_or_else(|| "pasta do roteador indisponivel".to_string())
}

/// Campo "Prompt adicionado no processamento de todos os laudos" (config.json: prompt_perfil).
#[specta::specta]
#[tauri::command]
pub fn rotrix_get_prompt(app: AppHandle) -> Result<String, String> {
    let p = caminho_config(&app)?;
    let v = ler_config(&p).unwrap_or(serde_json::json!({}));
    Ok(v.get("prompt_perfil")
        .and_then(|x| x.as_str())
        .unwrap_or("")
        .to_string())
}

#[specta::specta]
#[tauri::command]
pub fn rotrix_set_prompt(app: AppHandle, texto: String) -> Result<(), String> {
    let p = caminho_config(&app)?;
    if let Some(dir) = p.parent() {
        std::fs::create_dir_all(dir).map_err(|e| e.to_string())?;
    }
    let mut v = ler_config(&p)?;
    let limpo: String = texto.chars().take(2000).collect();
    match v.as_object_mut() {
        Some(obj) => {
            obj.insert("prompt_perfil".to_string(), serde_json::Value::String(limpo));
        }
        None => return Err("config.json nao e um objeto".to_string()),
    }
    gravar_config(&p, &v)?;
    info!("Rotrix: prompt do perfil salvo ({} caracteres)", texto.chars().count().min(2000));
    Ok(())
}

#[specta::specta]
#[tauri::command]
pub fn rotrix_abrir_pasta(app: AppHandle) -> Result<(), String> {
    use tauri_plugin_opener::OpenerExt;
    let p = pasta_ativa(&app).ok_or_else(|| "pasta do roteador indisponivel".to_string())?;
    std::fs::create_dir_all(&p).map_err(|e| e.to_string())?;
    app.opener()
        .open_path(p.to_string_lossy().to_string(), None::<String>)
        .map_err(|e| e.to_string())
}

// ---------------------------------------------------------------------------
// Inteligencia artificial: provedor, modelo, rota por exame, chaves e gasto
// ---------------------------------------------------------------------------

const PROVEDORES: &[&str] = &["anthropic", "openai", "gemini", "openrouter", "ollama", "compativel"];
const PROVEDORES_COM_CHAVE: &[&str] = &["anthropic", "openai", "gemini", "openrouter", "compativel"];
const TIPOS_EXAME: &[&str] = &["rx", "tc", "rm", "angio", "mamo", "us", "onco", "padrao"];

fn ler_config(p: &Path) -> Result<serde_json::Value, String> {
    let txt = std::fs::read_to_string(p).unwrap_or_else(|_| "{}".to_string());
    let txt = txt.trim_start_matches('\u{feff}'); // BOM de editor do Windows
    let v: serde_json::Value =
        serde_json::from_str(txt).map_err(|e| format!("config.json invalido: {e}"))?;
    if !v.is_object() {
        return Err("config.json nao e um objeto".to_string());
    }
    Ok(v)
}

/// Grava o config.json sem risco de deixar o arquivo pela metade.
fn gravar_config(p: &Path, v: &serde_json::Value) -> Result<(), String> {
    let saida = serde_json::to_string_pretty(v).map_err(|e| e.to_string())?;
    let tmp = p.with_extension("json.tmp");
    std::fs::write(&tmp, saida).map_err(|e| e.to_string())?;
    std::fs::rename(&tmp, p).map_err(|e| e.to_string())
}

fn modelo_valido(m: &str) -> bool {
    !m.is_empty()
        && m.len() <= 100
        && m.chars()
            .all(|c| c.is_ascii_alphanumeric() || "._:/-".contains(c))
}

/// Situacao da IA (GET /v1/ia do roteador). Se o roteador estiver parado,
/// monta o mesmo formato a partir dos arquivos (sem saber quais chaves existem).
#[specta::specta]
#[tauri::command]
pub fn rotrix_ia_estado(app: AppHandle) -> Result<String, String> {
    if let Some(corpo) = http_get("/v1/ia") {
        return Ok(corpo);
    }
    let dados = pasta_ativa(&app).ok_or_else(|| "pasta do roteador indisponivel".to_string())?;
    let c = ler_config(&dados.join("config.json"))?;
    let gasto: serde_json::Value = std::fs::read_to_string(dados.join("gasto.json"))
        .ok()
        .and_then(|t| serde_json::from_str(&t).ok())
        .unwrap_or(serde_json::json!({}));
    let mut chaves = serde_json::Map::new();
    for p in PROVEDORES_COM_CHAVE {
        let arq = dados.join(format!("chave_{p}.txt"));
        chaves.insert(p.to_string(), serde_json::Value::Bool(arq.exists()));
    }
    let v = serde_json::json!({
        "ativa": c.get("ativa").and_then(|x| x.as_bool()).unwrap_or(false),
        "provedor": c.get("provedor").and_then(|x| x.as_str()).unwrap_or("anthropic"),
        "modelo": c.get("modelo").and_then(|x| x.as_str()).unwrap_or(""),
        "modo_ia": c.get("modo_ia").and_then(|x| x.as_str()).unwrap_or(""),
        "ia_por_exame": c.get("ia_por_exame").cloned().unwrap_or(serde_json::json!({})),
        "chaves": chaves,
        "limite_mes_usd": c.get("limite_mes_usd").and_then(|x| x.as_f64()).unwrap_or(0.0),
        "gasto": gasto,
        "roteador_parado": true,
    });
    Ok(v.to_string())
}

/// Grava as escolhas da tela de IA no config.json. So aceita as chaves conhecidas,
/// com valores validados; o resto do config fica como estava. Nunca grava chave de API.
#[specta::specta]
#[tauri::command]
pub fn rotrix_ia_salvar(app: AppHandle, ajustes: String) -> Result<(), String> {
    let novo: serde_json::Value =
        serde_json::from_str(&ajustes).map_err(|e| format!("ajustes invalidos: {e}"))?;
    let novo = novo.as_object().ok_or("ajustes invalidos")?;
    let p = caminho_config(&app)?;
    let mut c = ler_config(&p)?;
    let obj = c.as_object_mut().ok_or("config.json nao e um objeto")?;

    if let Some(v) = novo.get("ativa").and_then(|x| x.as_bool()) {
        obj.insert("ativa".into(), serde_json::Value::Bool(v));
    }
    if let Some(v) = novo.get("provedor").and_then(|x| x.as_str()) {
        if !PROVEDORES.contains(&v) {
            return Err(format!("provedor desconhecido: {v}"));
        }
        obj.insert("provedor".into(), serde_json::Value::String(v.into()));
    }
    if let Some(v) = novo.get("modelo").and_then(|x| x.as_str()) {
        if !v.is_empty() && !modelo_valido(v) {
            return Err(format!("nome de modelo invalido: {v}"));
        }
        obj.insert("modelo".into(), serde_json::Value::String(v.into()));
    }
    if let Some(v) = novo.get("modo_ia").and_then(|x| x.as_str()) {
        if !["", "formatar"].contains(&v) {
            return Err("modo_ia deve ser vazio ou formatar".into());
        }
        obj.insert("modo_ia".into(), serde_json::Value::String(v.into()));
    }
    if let Some(v) = novo.get("limite_mes_usd").and_then(|x| x.as_f64()) {
        if !(0.0..=1000.0).contains(&v) {
            return Err("teto do mes deve ficar entre 0 e 1000".into());
        }
        obj.insert("limite_mes_usd".into(), serde_json::json!(v));
    }
    if let Some(mapa) = novo.get("ia_por_exame").and_then(|x| x.as_object()) {
        let mut limpo = serde_json::Map::new();
        for (tipo, e) in mapa {
            if !TIPOS_EXAME.contains(&tipo.as_str()) {
                continue;
            }
            let e = match e.as_object() {
                Some(e) => e,
                None => continue,
            };
            let mut item = serde_json::Map::new();
            if let Some(pv) = e.get("provedor").and_then(|x| x.as_str()).filter(|x| !x.is_empty()) {
                if !PROVEDORES.contains(&pv) {
                    return Err(format!("provedor desconhecido em {tipo}: {pv}"));
                }
                item.insert("provedor".into(), serde_json::Value::String(pv.into()));
            }
            if let Some(m) = e.get("modelo").and_then(|x| x.as_str()).filter(|x| !x.is_empty()) {
                if !modelo_valido(m) {
                    return Err(format!("nome de modelo invalido em {tipo}: {m}"));
                }
                item.insert("modelo".into(), serde_json::Value::String(m.into()));
            }
            if let Some(m) = e.get("modo").and_then(|x| x.as_str()).filter(|x| !x.is_empty()) {
                if !["formatar", "analisar"].contains(&m) {
                    return Err(format!("modo invalido em {tipo}: {m}"));
                }
                item.insert("modo".into(), serde_json::Value::String(m.into()));
            }
            if let Some(r) = e.get("raciocinio").and_then(|x| x.as_str()).filter(|x| !x.is_empty()) {
                if !["none", "low", "medium", "high"].contains(&r) {
                    return Err(format!("raciocinio invalido em {tipo}: {r}"));
                }
                item.insert("raciocinio".into(), serde_json::Value::String(r.into()));
            }
            if !item.is_empty() {
                limpo.insert(tipo.clone(), serde_json::Value::Object(item));
            }
        }
        obj.insert("ia_por_exame".into(), serde_json::Value::Object(limpo));
    }
    gravar_config(&p, &c)?;
    info!("Rotrix: configuracao de IA salva");
    Ok(())
}

fn arquivo_da_chave(app: &AppHandle, provedor: &str) -> Result<PathBuf, String> {
    if !PROVEDORES_COM_CHAVE.contains(&provedor) {
        return Err(format!("provedor sem chave: {provedor}"));
    }
    let dados = pasta_ativa(app).ok_or_else(|| "pasta do roteador indisponivel".to_string())?;
    Ok(dados.join(format!("chave_{provedor}.txt")))
}

/// Grava a chave digitada na tela no arquivo local do provedor (chave_<provedor>.txt).
/// A chave nao vai para log, config ou qualquer outro lugar.
#[specta::specta]
#[tauri::command]
pub fn rotrix_chave_salvar(app: AppHandle, provedor: String, chave: String) -> Result<(), String> {
    let k = chave.trim();
    if k.len() < 10 || k.len() > 400 || k.chars().any(|c| c.is_whitespace() || c.is_control()) {
        return Err("a chave parece incompleta: confira se copiou inteira, sem espacos".into());
    }
    let arq = arquivo_da_chave(&app, &provedor)?;
    std::fs::write(&arq, k).map_err(|e| e.to_string())?;
    info!("Rotrix: chave de {provedor} gravada");
    Ok(())
}

#[specta::specta]
#[tauri::command]
pub fn rotrix_chave_apagar(app: AppHandle, provedor: String) -> Result<(), String> {
    let arq = arquivo_da_chave(&app, &provedor)?;
    if arq.exists() {
        std::fs::remove_file(&arq).map_err(|e| e.to_string())?;
        info!("Rotrix: chave de {provedor} apagada");
    }
    Ok(())
}

// ---------------------------------------------------------------------------
// Minhas mascaras e laudos (importar_usuario.py no Python do roteador)
// ---------------------------------------------------------------------------

fn achar_python(app: &AppHandle) -> PathBuf {
    if let Some(r) = pasta_recursos(app) {
        let p = r.join("python").join("python.exe");
        if p.exists() {
            return p;
        }
    }
    #[cfg(windows)]
    {
        if let Ok(la) = std::env::var("LOCALAPPDATA") {
            for v in ["Python313", "Python312", "Python311", "Python310"] {
                let p = PathBuf::from(&la).join("Programs").join("Python").join(v).join("python.exe");
                if p.exists() {
                    return p;
                }
            }
        }
    }
    PathBuf::from(if cfg!(windows) { "python" } else { "python3" })
}

fn rodar_importador(app: &AppHandle, args: Vec<String>) -> Result<String, String> {
    let dados = pasta_ativa(app).ok_or_else(|| "pasta do roteador indisponivel".to_string())?;
    let script = dados.join("importar_usuario.py");
    if !script.exists() {
        return Err("este roteador ainda nao tem o importador: atualize o roteador".into());
    }
    let mut cmd = Command::new(achar_python(app));
    cmd.arg(&script)
        .args(&args)
        .arg("--json")
        .current_dir(&dados)
        .env("PYTHONUTF8", "1")
        .env("PYTHONDONTWRITEBYTECODE", "1");
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        const CREATE_NO_WINDOW: u32 = 0x0800_0000;
        cmd.creation_flags(CREATE_NO_WINDOW);
    }
    let out = cmd.output().map_err(|e| format!("nao consegui rodar o Python: {e}"))?;
    let txt = String::from_utf8_lossy(&out.stdout).trim().to_string();
    if txt.starts_with('{') {
        return Ok(txt);
    }
    let erro = String::from_utf8_lossy(&out.stderr);
    Err(format!("importador falhou: {}", erro.lines().last().unwrap_or("sem mensagem")))
}

/// acao: "mascaras" | "laudos" (arg = caminho do arquivo), "fonte" (arg = rotrix|minhas|ambas),
/// "listar", "remover" (arg = mascaras|laudos). Devolve o JSON do importador.
#[specta::specta]
#[tauri::command]
pub async fn rotrix_mascaras(
    app: AppHandle,
    acao: String,
    arg: Option<String>,
    substituir: bool,
) -> Result<String, String> {
    let mut args: Vec<String> = vec![acao.clone()];
    match acao.as_str() {
        "mascaras" | "laudos" => {
            let caminho = arg.ok_or("escolha um arquivo")?;
            let ext = Path::new(&caminho)
                .extension()
                .map(|e| e.to_string_lossy().to_lowercase())
                .unwrap_or_default();
            if !["txt", "md", "docx", "rtf"].contains(&ext.as_str()) {
                return Err("use um arquivo .txt, .md, .docx ou .rtf".into());
            }
            if !Path::new(&caminho).is_file() {
                return Err("arquivo nao encontrado".into());
            }
            args.push(caminho);
            if substituir {
                args.push("--substituir".into());
            }
        }
        "fonte" => {
            let f = arg.ok_or("escolha a fonte")?;
            if !["rotrix", "minhas", "ambas"].contains(&f.as_str()) {
                return Err("fonte deve ser rotrix, minhas ou ambas".into());
            }
            args.push(f);
        }
        "remover" => {
            let o = arg.ok_or("diga o que remover")?;
            if !["mascaras", "laudos"].contains(&o.as_str()) {
                return Err("remover: mascaras ou laudos".into());
            }
            args.push(o);
        }
        "listar" => {}
        _ => return Err(format!("acao desconhecida: {acao}")),
    }
    tauri::async_runtime::spawn_blocking(move || rodar_importador(&app, args))
        .await
        .map_err(|e| e.to_string())?
}

// ---------------------------------------------------------------------------
// Fila do Radius (radius.py no roteador). O roteador so devolve modalidade,
// descricao, status e laudado; nome e numero de acesso nunca chegam aqui.
// ---------------------------------------------------------------------------

/// GET /v1/fila do roteador (JSON em texto).
#[specta::specta]
#[tauri::command]
pub fn rotrix_fila() -> Result<String, String> {
    http_get("/v1/fila").ok_or_else(|| "roteador parado".to_string())
}

/// Modo estacao: passa para o proximo exame da fila (Ctrl+Alt+N).
#[specta::specta]
#[tauri::command]
pub fn rotrix_fila_proximo() -> Result<String, String> {
    http_post("/v1/fila/proximo", "{}", 4000)
}

/// Modo estacao: escolhe na mao o exame da vez.
#[specta::specta]
#[tauri::command]
pub fn rotrix_fila_escolher(id: String) -> Result<String, String> {
    http_post(
        "/v1/fila/escolher",
        &serde_json::json!({ "id": id }).to_string(),
        4000,
    )
}

/// Modo estacao: marca (ou desmarca) um exame como laudado por voce.
#[specta::specta]
#[tauri::command]
pub fn rotrix_fila_feito(id: String, feito: bool) -> Result<String, String> {
    http_post(
        "/v1/fila/feito",
        &serde_json::json!({ "id": id, "feito": feito }).to_string(),
        4000,
    )
}

/// Banco de mascaras para a aba Mascaras: regioes, lista e, com `titulo`,
/// o texto inteiro de uma mascara.
#[specta::specta]
#[tauri::command]
pub fn rotrix_mascaras_banco(busca: String, titulo: String) -> Result<String, String> {
    http_post(
        "/v1/mascaras/banco",
        &serde_json::json!({ "busca": busca, "titulo": titulo }).to_string(),
        20_000,
    )
}

/// Pedido falado sobre o banco de mascaras: a IA le o texto das mascaras
/// filtradas e devolve propostas. Nada e alterado sem a sua aprovacao.
#[specta::specta]
#[tauri::command]
pub fn rotrix_mascaras_ia(instrucao: String, busca: String) -> Result<String, String> {
    http_post(
        "/v1/mascaras/ia",
        &serde_json::json!({ "instrucao": instrucao, "busca": busca }).to_string(),
        180_000,
    )
}

/// Abre no RadiAnt os exames marcados na aba Fila, todos na mesma janela.
/// O roteador resolve os ids em caminhos de pasta no proprio computador e
/// chama o RadiAnt; nome de paciente nao entra nem sai deste caminho.
#[specta::specta]
#[tauri::command]
pub fn rotrix_abrir_estudos(ids: Vec<String>) -> Result<String, String> {
    if ids.is_empty() {
        return Err("nenhum exame marcado".to_string());
    }
    http_post(
        "/v1/fila/abrir",
        &serde_json::json!({ "ids": ids }).to_string(),
        15_000,
    )
}

/// Perfil: grava num .rotrix.zip as suas mascaras, o ouvido.tsv e os ajustes.
/// A chave de IA nunca entra; os laudos de estilo so com incluir_estilo.
#[specta::specta]
#[tauri::command]
pub fn rotrix_perfil_exportar(destino: String, incluir_estilo: bool) -> Result<String, String> {
    http_post(
        "/v1/perfil/exportar",
        &serde_json::json!({ "destino": destino, "incluir_estilo": incluir_estilo }).to_string(),
        60_000,
    )
}

/// Perfil: le um .rotrix.zip. modo = "juntar" ou "substituir". Regera a base.
#[specta::specta]
#[tauri::command]
pub fn rotrix_perfil_importar(arquivo: String, modo: String) -> Result<String, String> {
    http_post(
        "/v1/perfil/importar",
        &serde_json::json!({ "arquivo": arquivo, "modo": modo }).to_string(),
        900_000,
    )
}

/// Correcoes do medico, escritas na caixa de texto do app.
#[specta::specta]
#[tauri::command]
pub fn rotrix_correcao_aplicar(
    texto: String,
    laudo: String,
    usar_ia: bool,
) -> Result<String, String> {
    http_post(
        "/v1/correcao",
        &serde_json::json!({ "texto": texto, "laudo": laudo, "usar_ia": usar_ia }).to_string(),
        90_000,
    )
}

/// As ultimas regras que voce criou (para conferir e desfazer).
#[specta::specta]
#[tauri::command]
pub fn rotrix_correcao_listar() -> Result<String, String> {
    http_get("/v1/correcao").ok_or_else(|| "roteador parado".to_string())
}

#[specta::specta]
#[tauri::command]
pub fn rotrix_correcao_desfazer(id: String) -> Result<String, String> {
    http_post(
        "/v1/correcao/desfazer",
        &serde_json::json!({ "id": id }).to_string(),
        10_000,
    )
}

/// Versao publicada no GitHub ("ultima"), para o app avisar e baixar sozinho.
/// Sem token e sem login: e uma Release publica.
const RELEASE_ULTIMA: &str =
    "https://api.github.com/repos/brunobrandaob2-dot/Rotrix-L1000/releases/tags/ultima";

#[derive(serde::Serialize, specta::Type)]
pub struct VersaoPublicada {
    /// commit do app instalado (vazio quando compilado fora do CI)
    pub instalada: String,
    /// commit da versao publicada
    pub publicada: String,
    pub nome: String,
    pub quando: String,
    pub link: String,
    pub tem_nova: bool,
}

#[specta::specta]
#[tauri::command]
pub async fn rotrix_versao_publicada() -> Result<VersaoPublicada, String> {
    let instalada = option_env!("ROTRIX_COMMIT").unwrap_or("").to_string();
    let cliente = reqwest::Client::builder()
        .timeout(Duration::from_secs(15))
        .user_agent("Rotrix-L1000")
        .build()
        .map_err(|e| e.to_string())?;
    let v: serde_json::Value = cliente
        .get(RELEASE_ULTIMA)
        .header("Accept", "application/vnd.github+json")
        .send()
        .await
        .map_err(|e| format!("sem internet ou GitHub fora do ar: {e}"))?
        .json()
        .await
        .map_err(|e| e.to_string())?;
    let publicada = v
        .get("target_commitish")
        .and_then(|x| x.as_str())
        .unwrap_or("")
        .to_string();
    let link = v
        .get("assets")
        .and_then(|a| a.as_array())
        .and_then(|a| a.iter().find(|x| {
            x.get("name")
                .and_then(|n| n.as_str())
                .map(|n| n.ends_with(".exe"))
                .unwrap_or(false)
        }))
        .and_then(|x| x.get("browser_download_url"))
        .and_then(|x| x.as_str())
        .unwrap_or("")
        .to_string();
    let tem_nova = !publicada.is_empty() && !instalada.is_empty() && publicada != instalada;
    Ok(VersaoPublicada {
        instalada,
        publicada,
        nome: v
            .get("name")
            .and_then(|x| x.as_str())
            .unwrap_or("")
            .to_string(),
        quando: v
            .get("published_at")
            .and_then(|x| x.as_str())
            .unwrap_or("")
            .to_string(),
        link,
        tem_nova,
    })
}

/// Primeiros passos: o que ja esta pronto nesta maquina.
#[derive(serde::Serialize, specta::Type)]
pub struct PrimeirosPassos {
    pub roteador: bool,
    pub modelo: bool,
    pub radius: bool,
    pub chave_ia: bool,
    pub mascaras: u32,
}

#[specta::specta]
#[tauri::command]
pub fn rotrix_primeiros_passos(app: AppHandle) -> PrimeirosPassos {
    let versao = consultar_versao();
    let mascaras = versao
        .as_ref()
        .and_then(|v| v.get("gatilhos"))
        .and_then(|x| x.as_u64())
        .unwrap_or(0) as u32;
    let fila: Option<serde_json::Value> =
        http_get("/v1/fila").and_then(|c| serde_json::from_str(&c).ok());
    let ia: Option<serde_json::Value> =
        http_get("/v1/ia").and_then(|c| serde_json::from_str(&c).ok());
    let chave_ia = ia
        .as_ref()
        .and_then(|v| v.get("chaves"))
        .and_then(|x| x.as_object())
        .map(|o| o.values().any(|v| v.as_bool().unwrap_or(false)))
        .unwrap_or(false);
    let s = settings::get_settings(&app);
    PrimeirosPassos {
        roteador: versao.is_some(),
        modelo: !s.selected_model.is_empty(),
        radius: fila
            .as_ref()
            .and_then(|v| v.get("pasta_existe"))
            .and_then(|x| x.as_bool())
            .unwrap_or(false),
        chave_ia,
        mascaras,
    }
}

/// Grava no config.json o perfil automatico e, se vier, a pasta do Radius.
#[specta::specta]
#[tauri::command]
pub fn rotrix_fila_salvar(
    app: AppHandle,
    perfil_automatico: bool,
    pasta: Option<String>,
) -> Result<(), String> {
    let p = caminho_config(&app)?;
    let mut c = ler_config(&p)?;
    let obj = c
        .as_object_mut()
        .ok_or_else(|| "config.json nao e um objeto".to_string())?;
    obj.insert(
        "perfil_automatico".to_string(),
        serde_json::Value::Bool(perfil_automatico),
    );
    if let Some(pa) = pasta {
        let pa = pa.trim();
        if pa.is_empty() {
            obj.remove("radius_pasta");
        } else {
            if pa.len() > 300 || pa.contains('\n') || pa.contains('\r') {
                return Err("pasta invalida".to_string());
            }
            obj.insert(
                "radius_pasta".to_string(),
                serde_json::Value::String(pa.to_string()),
            );
        }
    }
    gravar_config(&p, &c)
}

/// Ditado simples (Ctrl+Espaço, sem o roteador): começa com letra maiúscula,
/// cada frase depois de ". ", "! ", "? " ou de uma linha nova também, e o texto
/// termina com ponto final. Vírgula solta no fim vira ponto.
pub fn frase_formatada(texto: &str) -> String {
    let corpo = texto.trim_end();
    if corpo.trim().is_empty() {
        return texto.to_string();
    }
    let cauda = &texto[corpo.len()..];
    let mut out = String::with_capacity(corpo.len() + 1);
    let mut maiuscula = true;
    let mut anterior_fim = false;
    for ch in corpo.chars() {
        if ch.is_alphabetic() {
            if maiuscula {
                out.extend(ch.to_uppercase());
            } else {
                out.push(ch);
            }
            maiuscula = false;
            anterior_fim = false;
            continue;
        }
        if ch.is_numeric() {
            maiuscula = false;
        }
        if ch == '\n' || (ch.is_whitespace() && anterior_fim) {
            maiuscula = true;
        }
        anterior_fim = matches!(ch, '.' | '!' | '?');
        out.push(ch);
    }
    if out.ends_with(',') || out.ends_with(';') {
        out.pop();
    }
    let ultimo = out.chars().last().unwrap_or('.');
    if ultimo.is_alphanumeric() || matches!(ultimo, ')' | '%' | '°' | ']') {
        out.push('.');
    }
    out.push_str(cauda);
    out
}

// ---------------------------------------------------------------------------
// Rotrix v2: a aba Laudo. Os botoes da barra precisam de tres coisas que os
// atalhos ja fazem: gravar, colar na janela de antes e passar o texto pela IA.
// ---------------------------------------------------------------------------

/// Quando o ditado foi disparado por um botao da aba Laudo, o texto NAO e
/// colado na janela de fora: ele volta para a folha do app pelo evento
/// "rotrix-ditado". A bandeira e consumida uma unica vez, pelo ditado seguinte.
static DITADO_PARA_FOLHA: std::sync::atomic::AtomicBool = std::sync::atomic::AtomicBool::new(false);

pub fn folha_quer_o_texto() -> bool {
    DITADO_PARA_FOLHA.swap(false, std::sync::atomic::Ordering::SeqCst)
}

/// Dispara, a partir de um botao da tela, a mesma acao de um atalho.
/// `binding`: "transcribe" (ditado simples) ou "transcribe_with_post_process"
/// (ditado que passa pelo roteador). `comeco` = true no apertar, false no soltar.
#[tauri::command]
#[specta::specta]
pub fn rotrix_acao(
    app: AppHandle,
    binding: String,
    comeco: bool,
    para_folha: bool,
) -> Result<(), String> {
    if comeco {
        DITADO_PARA_FOLHA.store(para_folha, std::sync::atomic::Ordering::SeqCst);
    }
    let acao = crate::actions::ACTION_MAP
        .get(&binding)
        .ok_or_else(|| format!("acao desconhecida: {binding}"))?
        .clone();
    if comeco {
        acao.start(&app, &binding, "");
    } else {
        acao.stop(&app, &binding, "");
    }
    Ok(())
}

/// Cola o texto na janela que estava na frente antes do Rotrix.
/// Minimiza a janela do app (o Windows devolve o foco para a anterior), espera
/// o foco assentar e usa a mesma colagem do ditado.
#[tauri::command]
#[specta::specta]
pub fn rotrix_colar(app: AppHandle, texto: String) -> Result<(), String> {
    if texto.trim().is_empty() {
        return Err("nada para colar".to_string());
    }
    if let Some(janela) = app.get_webview_window("main") {
        let _ = janela.minimize();
    }
    std::thread::sleep(Duration::from_millis(250));
    crate::clipboard::paste(texto, app)
}

/// Manda o laudo que esta na folha para a IA do roteador e devolve o texto pronto.
/// `instrucao` vazia = so revisar; com instrucao, a IA obedece ao pedido falado.
/// `modelo` vazio = o modelo da configuracao.
#[tauri::command]
#[specta::specta]
pub fn rotrix_ia_texto(texto: String, instrucao: String, modelo: String) -> Result<String, String> {
    let corpo = serde_json::json!({
        "texto": texto,
        "instrucao": instrucao,
        "modelo": modelo,
    })
    .to_string();
    http_post("/v1/ia", &corpo, 90_000)
}

#[cfg(test)]
mod testes_frase {
    use super::frase_formatada;

    #[test]
    fn maiuscula_e_ponto() {
        assert_eq!(frase_formatada("derrame pleural à direita"), "Derrame pleural à direita.");
        assert_eq!(frase_formatada("já tem ponto."), "Já tem ponto.");
        assert_eq!(frase_formatada("medindo 1.5 cm"), "Medindo 1.5 cm.");
        assert_eq!(frase_formatada("primeira. segunda frase,"), "Primeira. Segunda frase.");
        assert_eq!(frase_formatada("linha um\nlinha dois"), "Linha um\nLinha dois.");
        assert_eq!(frase_formatada("L4-L5 com protrusão"), "L4-L5 com protrusão.");
        assert_eq!(frase_formatada("  "), "  ");
    }
}

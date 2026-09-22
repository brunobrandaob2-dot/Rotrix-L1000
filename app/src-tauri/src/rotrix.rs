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

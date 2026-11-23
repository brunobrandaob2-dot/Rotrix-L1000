# -*- coding: utf-8 -*-
"""Rotrix v2 — fase 5: a IA pelo PLANO (assinatura), sem chave de API.

Em vez de mandar o pedido para a API com a chave guardada num .txt, o roteador
chama o programa da própria assinatura que já está instalado no PC:

- Claude Code (claude.exe): `claude -p` com stream-json — sem ferramentas, sem
  servidores MCP, sem os ajustes do usuário, sem guardar sessão, numa pasta
  temporária vazia. Só pergunta e resposta, com o MESMO texto de sistema e o
  MESMO pedido que iriam para a API. Imagens vão junto (blocos base64).
- Codex (codex.exe da OpenAI): `codex exec` somente leitura, sem repositório; a
  resposta final vem do arquivo de --output-last-message. (Ainda não testado num
  PC com o Codex instalado.)

O que NÃO muda: a triagem de dados do paciente (nuvem.triagem) roda ANTES,
igual para todos os provedores; o pedido vai pela entrada padrão (não aparece
na linha de comando); nada disso é gravado em disco fora da pasta temporária,
que é apagada no fim. Custo: 0 aqui — o gasto é do plano, não da chave.
"""
import base64
import json
import os
import shutil
import subprocess
import tempfile

_SEM_JANELA = 0x08000000 if os.name == "nt" else 0

MODELOS_CLAUDE = [("sonnet", "Claude Sonnet · pelo plano (sem chave)"),
                  ("opus", "Claude Opus · pelo plano (sem chave)"),
                  ("haiku", "Claude Haiku · pelo plano (sem chave)")]
MODELOS_CODEX = [("padrao", "Codex · modelo padrão do plano (sem chave)")]


class ErroLocal(Exception):
    def __init__(self, motivo, det=""):
        super().__init__(motivo)
        self.motivo, self.det = motivo, det


def _candidatos(nome, extras=()):
    home = os.path.expanduser("~")
    loc = os.environ.get("LOCALAPPDATA", "")
    app = os.environ.get("APPDATA", "")
    vistos = list(extras) + [
        os.path.join(home, ".local", "bin", nome + ".exe"),
        os.path.join(loc, "Programs", nome, nome + ".exe"),
        os.path.join(app, "npm", nome + ".cmd"),
        os.path.join(home, ".local", "bin", nome),
    ]
    achado = shutil.which(nome)
    if achado:
        vistos.append(achado)
    return vistos


def achar(qual, c=None):
    """Caminho do claude/codex (config: "claude_exe" / "codex_exe" manda), ou ""."""
    c = c or {}
    prop = os.path.expandvars(str(c.get(qual + "_exe") or "")).strip().strip('"')
    for cam in _candidatos(qual, [prop] if prop else []):
        if cam and os.path.isfile(cam):
            return cam
    return ""


def disponivel(qual, c=None):
    return bool(achar(qual, c))


def modelos(qual, c=None):
    if not achar(qual, c):
        return {"ok": False, "motivo": "nao_instalado", "provedor": qual + "_local", "modelos": []}
    lista = MODELOS_CLAUDE if qual == "claude" else MODELOS_CODEX
    return {"ok": True, "provedor": qual + "_local", "origem_da_chave": "plano",
            "modelos": [{"id": i, "nome": n} for i, n in lista], "quantos": len(lista)}


def _rodar(args, entrada, pasta, timeout):
    try:
        r = subprocess.run(args, input=entrada, capture_output=True, cwd=pasta, timeout=timeout,
                           creationflags=_SEM_JANELA)
    except subprocess.TimeoutExpired:
        raise ErroLocal("tempo_esgotado")
    except OSError as e:
        raise ErroLocal("nao_abriu", type(e).__name__)
    return r


# --- Claude Code ---------------------------------------------------------------
_ESFORCO = {"low": "low", "medium": "medium", "high": "high", "xhigh": "xhigh", "max": "max"}


def args_claude(exe, modelo, arq_sistema, raciocinio=""):
    a = [exe, "-p", "--output-format", "stream-json", "--input-format", "stream-json", "--verbose",
         "--tools", "", "--strict-mcp-config", "--setting-sources", "", "--no-session-persistence",
         "--system-prompt-file", arq_sistema]
    if modelo and modelo != "padrao":
        a += ["--model", modelo]
    if raciocinio in _ESFORCO:
        a += ["--effort", _ESFORCO[raciocinio]]
    return a


def mensagem_claude(pedido, imagens=None):
    conteudo = [{"type": "image", "source": {"type": "base64", "media_type": mt, "data": b64}}
                for mt, b64 in (imagens or [])]
    conteudo.append({"type": "text", "text": pedido})
    return json.dumps({"type": "user", "message": {"role": "user", "content": conteudo}},
                      ensure_ascii=False) + "\n"


def ler_resultado_claude(saida):
    """(texto, uso) da última linha "result" do stream-json."""
    fim = None
    for linha in saida.splitlines():
        try:
            d = json.loads(linha)
        except ValueError:
            continue
        if isinstance(d, dict) and d.get("type") == "result":
            fim = d
    if fim is None:
        raise ErroLocal("sem_resposta")
    if fim.get("is_error"):
        det = str(fim.get("result") or fim.get("subtype") or "")
        raise ErroLocal("limite_do_plano" if "limit" in det.lower() else "erro_do_claude", det[:200])
    u = fim.get("usage") or {}
    uso = {"in": int(u.get("input_tokens", 0) or 0), "out": int(u.get("output_tokens", 0) or 0),
           "cache_w": int(u.get("cache_creation_input_tokens", 0) or 0),
           "cache_r": int(u.get("cache_read_input_tokens", 0) or 0),
           "fim": str(fim.get("stop_reason") or fim.get("subtype") or ""),
           "pensou": int(((u.get("output_tokens_details") or {}).get("thinking_tokens", 0)) or 0)}
    return str(fim.get("result") or "").strip(), uso


def enviar_claude(p, k, modelo, sistema, pedido, max_tokens, timeout, raciocinio, cache=None,
                  imagens=None, c=None):
    """Mesma assinatura dos _enviar_* do nuvem.py: (texto, uso, usd)."""
    exe = achar("claude", c)
    if not exe:
        raise ErroLocal("nao_instalado")
    pasta = tempfile.mkdtemp(prefix="rotrix_ia_")
    try:
        arq = os.path.join(pasta, "sistema.txt")
        with open(arq, "w", encoding="utf-8") as f:
            f.write(sistema or "")
        r = _rodar(args_claude(exe, modelo, arq, raciocinio),
                   mensagem_claude(pedido, imagens).encode("utf-8"), pasta, timeout)
        texto, uso = ler_resultado_claude(r.stdout.decode("utf-8", "replace"))
        if r.returncode != 0 and not texto:
            raise ErroLocal("erro_do_claude", r.stderr.decode("utf-8", "replace")[:200])
        return texto, uso, 0.0
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


# --- Codex ---------------------------------------------------------------------
def args_codex(exe, modelo, arq_resposta, arquivos_imagem=(), raciocinio=""):
    a = [exe, "exec", "--skip-git-repo-check", "--sandbox", "read-only", "--color", "never",
         "--output-last-message", arq_resposta]
    if modelo and modelo != "padrao":
        a += ["-m", modelo]
    if raciocinio in ("none", "low", "medium", "high"):
        a += ["-c", "model_reasoning_effort=%s" % ("minimal" if raciocinio == "none" else raciocinio)]
    for img in arquivos_imagem:
        a += ["-i", img]
    a.append("-")  # o pedido vem pela entrada padrão
    return a


def enviar_codex(p, k, modelo, sistema, pedido, max_tokens, timeout, raciocinio, cache=None,
                 imagens=None, c=None):
    exe = achar("codex", c)
    if not exe:
        raise ErroLocal("nao_instalado")
    pasta = tempfile.mkdtemp(prefix="rotrix_ia_")
    try:
        imgs = []
        for i, (mt, b64) in enumerate(imagens or []):
            ext = ".png" if "png" in mt else ".jpg"
            cam = os.path.join(pasta, "imagem%d%s" % (i + 1, ext))
            with open(cam, "wb") as f:
                f.write(base64.b64decode(b64))
            imgs.append(cam)
        resposta = os.path.join(pasta, "resposta.txt")
        # o Codex não tem texto de sistema à parte: vai na frente do pedido
        entrada = "%s\n\n---\n\n%s" % (sistema or "", pedido)
        r = _rodar(args_codex(exe, modelo, resposta, imgs, raciocinio), entrada.encode("utf-8"), pasta, timeout)
        try:
            with open(resposta, encoding="utf-8") as f:
                texto = f.read().strip()
        except OSError:
            texto = ""
        if not texto:
            raise ErroLocal("erro_do_codex", r.stderr.decode("utf-8", "replace")[:200])
        return texto, {"in": 0, "out": 0, "cache_w": 0, "cache_r": 0, "fim": "", "pensou": 0}, 0.0
    finally:
        shutil.rmtree(pasta, ignore_errors=True)

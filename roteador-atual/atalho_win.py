# -*- coding: utf-8 -*-
"""Ctrl+Alt+A: revisão do laudo inteiro pela nuvem.

Com o laudo selecionado (ou com o cursor no campo do laudo), Ctrl+Alt+A:
  1. copia a seleção (se não houver seleção, seleciona tudo no campo e copia);
  2. manda o texto para a revisão da nuvem (o prompt de revisão do Bruno);
  3. cola por cima o texto revisado, com os cabeçalhos em negrito.
Bipe curto = começou. Bipe agudo = colou. Bipe grave = não deu (ver atalho.log).

Roda como uma thread dentro do roteador (só no Windows). Sem dependências.
"""
import ctypes, ctypes.wintypes as w, os, re, subprocess, threading, time, datetime
import formato

AQUI = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(AQUI, "atalho.log")
COLADOR = os.environ.get("ROTEADOR_COLADOR") or \
    os.path.join(os.environ.get("APPDATA", ""), "com.pais.handy", "handy_radiology_paste.exe")

MOD_ALT, MOD_CONTROL, MOD_NOREPEAT = 0x1, 0x2, 0x4000
WM_HOTKEY = 0x0312
VK_CONTROL, VK_MENU, VK_SHIFT = 0x11, 0x12, 0x10
CF_UNICODETEXT = 13
GMEM_MOVEABLE = 0x0002

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
user32.GetClipboardData.restype = w.HANDLE
user32.GetClipboardData.argtypes = [w.UINT]
user32.SetClipboardData.restype = w.HANDLE
user32.SetClipboardData.argtypes = [w.UINT, w.HANDLE]
user32.OpenClipboard.argtypes = [w.HWND]
user32.GetClipboardSequenceNumber.restype = w.DWORD
user32.RegisterHotKey.argtypes = [w.HWND, ctypes.c_int, w.UINT, w.UINT]
user32.GetAsyncKeyState.restype = ctypes.c_short
kernel32.GlobalLock.restype = ctypes.c_void_p
kernel32.GlobalLock.argtypes = [w.HGLOBAL]
kernel32.GlobalUnlock.argtypes = [w.HGLOBAL]
kernel32.GlobalAlloc.restype = w.HGLOBAL
kernel32.GlobalAlloc.argtypes = [w.UINT, ctypes.c_size_t]

_ocupado = threading.Lock()


def log(msg):
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(datetime.datetime.now().isoformat(timespec="seconds") + "  " + msg + "\n")
    except Exception:
        pass


def _bipe(tipo):
    try:
        import winsound
        if tipo == "inicio":
            winsound.Beep(880, 70)
        elif tipo == "ok":
            winsound.Beep(1320, 90)
        else:
            winsound.Beep(300, 250)
    except Exception:
        pass


def _tecla(vk, solta=False):
    user32.keybd_event(vk, 0, 0x0002 if solta else 0, 0)


def _combo(vk):
    _tecla(VK_CONTROL); _tecla(vk); time.sleep(0.02)
    _tecla(vk, True); _tecla(VK_CONTROL, True)


def _esperar_soltar(teclas=(VK_CONTROL, VK_MENU, VK_SHIFT, ord("A")), limite=3.0):
    fim = time.time() + limite
    while time.time() < fim:
        if not any(user32.GetAsyncKeyState(k) & 0x8000 for k in teclas):
            return True
        time.sleep(0.03)
    return False


def _abrir_clipboard():
    for _ in range(20):
        if user32.OpenClipboard(None):
            return True
        time.sleep(0.03)
    return False


def clip_ler():
    if not _abrir_clipboard():
        return ""
    try:
        h = user32.GetClipboardData(CF_UNICODETEXT)
        if not h:
            return ""
        p = kernel32.GlobalLock(h)
        try:
            return ctypes.wstring_at(p) if p else ""
        finally:
            kernel32.GlobalUnlock(h)
    finally:
        user32.CloseClipboard()


def clip_gravar(texto):
    dados = (texto + "\0").encode("utf-16-le")
    if not _abrir_clipboard():
        return False
    try:
        user32.EmptyClipboard()
        h = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(dados))
        p = kernel32.GlobalLock(h)
        ctypes.memmove(p, dados, len(dados))
        kernel32.GlobalUnlock(h)
        user32.SetClipboardData(CF_UNICODETEXT, h)
        return True
    finally:
        user32.CloseClipboard()


def _copiar(vk):
    antes = user32.GetClipboardSequenceNumber()
    _combo(vk)
    fim = time.time() + 0.8
    while time.time() < fim:
        if user32.GetClipboardSequenceNumber() != antes:
            time.sleep(0.05)
            return clip_ler()
        time.sleep(0.02)
    return None


def copiar_selecao():
    """Copia o que está selecionado na janela ativa. Sem seleção: Ctrl+A e copia."""
    _esperar_soltar()
    t = _copiar(ord("C"))
    if not (t or "").strip():
        _combo(ord("A")); time.sleep(0.08)
        t = _copiar(ord("C"))
    return (t or "").strip()


_CABS = ("TÉCNICA", "TECNICA", "INDICAÇÃO CLÍNICA", "INDICACAO CLINICA", "INDICAÇÃO", "ANÁLISE",
         "ANALISE", "RELATÓRIO", "COMPARAÇÃO", "COMPARACAO", "CONCLUSÃO", "CONCLUSAO",
         "IMPRESSÃO DIAGNÓSTICA", "OPINIÃO")


def marcar_negrito(texto):
    """Cabeçalhos e título em **negrito** para o colador v9."""
    linhas = texto.split("\n")
    for i, l in enumerate(linhas):
        s = l.strip()
        if not s or s.startswith("**"):
            continue
        m = re.match(r"^(%s)\s*:\s*(.*)$" % "|".join(map(re.escape, _CABS)), s)
        if m:
            resto = m.group(2)
            linhas[i] = "**%s:**" % m.group(1) + (("  " + resto) if resto else "")
        elif i == next((j for j, x in enumerate(linhas) if x.strip()), -1) and s.upper() == s \
                and len(s) > 8 and any(c.isalpha() for c in s):
            linhas[i] = "**%s**" % s
    return "\n".join(linhas)


def colar(texto, rico=True):
    if rico and os.path.exists(COLADOR):
        try:
            subprocess.run([COLADOR, formato.padronizar(texto)], timeout=20,
                           creationflags=0x08000000)
            return True
        except Exception as e:
            log("colador falhou: %r — colando texto puro" % e)
    if clip_gravar(formato.padronizar(texto).replace("**", "")):
        time.sleep(0.05)
        _combo(ord("V"))
        return True
    return False


def _executar(revisar):
    if not _ocupado.acquire(blocking=False):
        return
    try:
        _bipe("inicio")
        texto = copiar_selecao()
        if not texto:
            log("nada para revisar: a seleção veio vazia")
            _bipe("erro"); return
        t0 = time.time()
        novo, origem = revisar(texto)
        if not novo or origem != "nuvem":
            log("revisão não aplicada (%s)" % origem)
            _bipe("erro"); return
        colar(novo)
        log("revisado: %d -> %d caracteres em %.1fs" % (len(texto), len(novo), time.time() - t0))
        _bipe("ok")
    except Exception as e:
        log("erro: %r" % e)
        _bipe("erro")
    finally:
        _ocupado.release()


def iniciar(revisar, tecla="A"):
    """revisar(texto) -> (texto_revisado, origem). Registra Ctrl+Alt+<tecla>."""
    def laco():
        vk = ord(tecla.upper())
        if not user32.RegisterHotKey(None, 1, MOD_CONTROL | MOD_ALT | MOD_NOREPEAT, vk):
            log("não consegui registrar Ctrl+Alt+%s — outro programa já usa esse atalho" % tecla)
            return
        log("atalho Ctrl+Alt+%s ativo" % tecla)
        msg = w.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
            if msg.message == WM_HOTKEY:
                threading.Thread(target=_executar, args=(revisar,), daemon=True).start()
    threading.Thread(target=laco, daemon=True, name="atalho-revisao").start()

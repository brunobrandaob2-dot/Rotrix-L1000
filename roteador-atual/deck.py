# -*- coding: utf-8 -*-
"""Stream Deck / Stream Dock do Rotrix v2 (fase 3, 22/11/2026).

"Eu quero poder configurar qualquer Stream Deck dentro do Rotrix, sem precisar
abrir o programa do aparelho." O Rotrix vira o programa do aparelho:

  - acha o aparelho na USB (API de HID do próprio Windows, por ctypes — o
    instalador não leva biblioteca nenhuma a mais)
  - pinta as teclas com as imagens que a TELA desenha (JPEG pronto: o roteador
    não precisa de Pillow)
  - lê teclas, botões e giratórios e faz a ação mapeada no Painel

Famílias de aparelho:
  mirabox — AJAZZ / Mirabox "Stream Dock" (protocolo "CRT"). AKP03E testado
            no aparelho dele em 22/11/2026: 6 teclas com tela 64x64, 3 botões
            sem tela, 3 giratórios.
  elgato2 — Elgato Stream Deck de 2ª geração (MK.2, XL, Original v2, Plus,
            Neo): JPEG em pacotes de 1024 bytes. Montado pelo protocolo
            conhecido; ainda NÃO testado em aparelho (marcado na tela).

O programa do fabricante tem de ficar fechado: os dois brigariam pelas teclas.
"""
import base64
import os
import sys
import threading
import time

EH_WINDOWS = sys.platform == "win32"

# ---------------------------------------------------------------------------
# Catálogo: o desenho de cada modelo e como ele fala
# slots: "k0".."kN" teclas com tela, "b0".. botões sem tela, "g0".. giratórios
# img: (largura, altura, rotação em graus no sentido horário, espelhar)
# ---------------------------------------------------------------------------
MODELOS = {
    (0x0300, 0x3002): {"id": "akp03e", "nome": "AJAZZ AKP03E (Stream Dock)", "familia": "mirabox",
                       "cols": 3, "linhas": 2, "botoes": 3, "giros": 3, "img": (64, 64, 90, False),
                       "testado": True},
    (0x0FD9, 0x0080): {"id": "sd_mk2", "nome": "Elgato Stream Deck MK.2", "familia": "elgato2",
                       "cols": 5, "linhas": 3, "botoes": 0, "giros": 0, "img": (72, 72, 180, False)},
    (0x0FD9, 0x00A5): {"id": "sd_mk2b", "nome": "Elgato Stream Deck MK.2", "familia": "elgato2",
                       "cols": 5, "linhas": 3, "botoes": 0, "giros": 0, "img": (72, 72, 180, False)},
    (0x0FD9, 0x006D): {"id": "sd_v2", "nome": "Elgato Stream Deck (v2)", "familia": "elgato2",
                       "cols": 5, "linhas": 3, "botoes": 0, "giros": 0, "img": (72, 72, 180, False)},
    (0x0FD9, 0x006C): {"id": "sd_xl", "nome": "Elgato Stream Deck XL", "familia": "elgato2",
                       "cols": 8, "linhas": 4, "botoes": 0, "giros": 0, "img": (96, 96, 180, False)},
    (0x0FD9, 0x008F): {"id": "sd_xl2", "nome": "Elgato Stream Deck XL", "familia": "elgato2",
                       "cols": 8, "linhas": 4, "botoes": 0, "giros": 0, "img": (96, 96, 180, False)},
    (0x0FD9, 0x0084): {"id": "sd_plus", "nome": "Elgato Stream Deck +", "familia": "elgato2",
                       "cols": 4, "linhas": 2, "botoes": 0, "giros": 4, "img": (120, 120, 0, False)},
    (0x0FD9, 0x009A): {"id": "sd_neo", "nome": "Elgato Stream Deck Neo", "familia": "elgato2",
                       "cols": 4, "linhas": 2, "botoes": 2, "giros": 0, "img": (96, 96, 180, False)},
}
# aparelhos conhecidos que ainda não falam com o Rotrix (geração 1: BMP)
SEM_SUPORTE = {(0x0FD9, 0x0060): "Elgato Stream Deck (1ª geração)",
               (0x0FD9, 0x0063): "Elgato Stream Deck Mini", (0x0FD9, 0x0090): "Elgato Stream Deck Mini MK.2"}
PAGINA_DE_USO = {"mirabox": 0xFFA0, "elgato2": 0x000C}

# programas do fabricante que seguram o aparelho
PROGRAMAS_DO_FABRICANTE = ("streamdeck.exe", "streamdock.exe", "hotspotstreamdock.exe", "mirabox.exe")


def slots_do_modelo(m):
    s = ["k%d" % i for i in range(m["cols"] * m["linhas"])]
    s += ["b%d" % i for i in range(m["botoes"])]
    s += ["g%d" % i for i in range(m["giros"])]
    return s


def publico(m):
    """O que a tela precisa para desenhar o aparelho."""
    return {k: m[k] for k in ("id", "nome", "familia", "cols", "linhas", "botoes", "giros")} | {
        "img": {"w": m["img"][0], "h": m["img"][1], "rot": m["img"][2], "espelhar": m["img"][3]},
        "testado": bool(m.get("testado")), "slots": slots_do_modelo(m)}


# ---------------------------------------------------------------------------
# Protocolos (puros: montam bytes e leem entradas — testados no CI)
# ---------------------------------------------------------------------------
class Mirabox:
    """AJAZZ / Mirabox Stream Dock, protocolo v3 (AKP03E)."""
    PACOTE = 1024

    @staticmethod
    def cmd(payload, tam=1025):
        b = bytes([0x00]) + b"CRT\x00\x00" + payload
        return b + bytes(max(0, tam - len(b)))

    @classmethod
    def iniciar(cls, tam=1025):
        return [cls.cmd(b"DIS", tam), cls.cmd(b"LIG\x00\x00\x00\x00", tam)]

    @classmethod
    def brilho(cls, pct, tam=1025):
        return [cls.cmd(b"LIG\x00\x00" + bytes([max(0, min(100, int(pct)))]), tam)]

    @classmethod
    def manter(cls, tam=1025):
        return [cls.cmd(b"CONNECT", tam)]

    @classmethod
    def limpar(cls, tam=1025):
        return [cls.cmd(b"CLE\x00\x00\x00\xff", tam), cls.cmd(b"STP", tam)]

    @classmethod
    def imagem(cls, indice, jpeg, tam=1025):
        n = len(jpeg)
        out = [cls.cmd(b"BAT\x00\x00" + bytes([(n >> 8) & 0xFF, n & 0xFF, indice + 1]), tam)]
        for i in range(0, n, cls.PACOTE):
            parte = jpeg[i:i + cls.PACOTE]
            out.append(bytes([0x00]) + parte + bytes(max(0, tam - 1 - len(parte))))
        return out

    @classmethod
    def confirmar(cls, tam=1025):
        return [cls.cmd(b"STP", tam)]

    # entrada: código -> (slot, tipo)  tipo: "tecla" | "girar-" | "girar+" | "clique"
    ENTRADA = {0x25: ("b0", "tecla"), 0x30: ("b1", "tecla"), 0x31: ("b2", "tecla"),
               0x90: ("g0", "girar-"), 0x91: ("g0", "girar+"), 0x50: ("g1", "girar-"), 0x51: ("g1", "girar+"),
               0x60: ("g2", "girar-"), 0x61: ("g2", "girar+"),
               0x33: ("g0", "clique"), 0x35: ("g1", "clique"), 0x34: ("g2", "clique")}

    @classmethod
    def ler(cls, dados, _estado=None):
        """Bytes de um relatório -> [(slot, tipo, apertado)]"""
        if len(dados) < 11 or bytes(dados[:3]) != b"ACK":
            return []
        cod, est = dados[9], dados[10]
        if cod == 0:
            return []
        if 1 <= cod <= 6:
            return [("k%d" % (cod - 1), "tecla", bool(est))]
        if cod in cls.ENTRADA:
            slot, tipo = cls.ENTRADA[cod]
            if tipo.startswith("girar"):
                return [(slot, tipo, True)]
            return [(slot, tipo, bool(est))]
        return []


class Elgato2:
    """Elgato Stream Deck 2ª geração (MK.2, XL, v2, Plus, Neo). Não testado."""
    PACOTE = 1024

    @staticmethod
    def brilho(pct, tam_feature=32):
        b = bytes([0x03, 0x08, max(0, min(100, int(pct)))])
        return [("feature", b + bytes(max(0, tam_feature - len(b))))]

    @staticmethod
    def iniciar(tam_feature=32):
        b = bytes([0x03, 0x02])
        return [("feature", b + bytes(max(0, tam_feature - len(b))))]

    @classmethod
    def imagem(cls, indice, jpeg, tam=1024):
        out, pagina, cab = [], 0, 8
        corpo = tam - cab
        for i in range(0, len(jpeg), corpo):
            parte = jpeg[i:i + corpo]
            ultimo = 1 if i + corpo >= len(jpeg) else 0
            h = bytes([0x02, 0x07, indice, ultimo, len(parte) & 0xFF, len(parte) >> 8,
                       pagina & 0xFF, pagina >> 8])
            out.append(("saida", h + parte + bytes(tam - cab - len(parte))))
            pagina += 1
        return out

    @staticmethod
    def ler(dados, estado):
        """Relatório de entrada -> eventos. `estado` guarda as teclas apertadas antes."""
        if len(dados) < 5 or dados[0] != 0x01:
            return []
        ev = []
        if dados[1] == 0x00:  # teclas: a partir do byte 4, uma por tecla
            n = estado.get("n", 15)
            atual = [bool(x) for x in dados[4:4 + n]]
            antes = estado.get("teclas") or [False] * len(atual)
            for i, (a, b) in enumerate(zip(antes, atual)):
                if a != b:
                    ev.append(("k%d" % i, "tecla", b))
            estado["teclas"] = atual
        elif dados[1] == 0x03 and len(dados) > 9:  # giratórios do Stream Deck +
            if dados[4] == 0x01:  # girou
                for i in range(4):
                    d = dados[5 + i]
                    if d:
                        ev.append(("g%d" % i, "girar+" if d < 128 else "girar-", True))
            else:  # apertou o giratório
                atual = [bool(x) for x in dados[5:9]]
                antes = estado.get("giros") or [False] * 4
                for i, (a, b) in enumerate(zip(antes, atual)):
                    if a != b:
                        ev.append(("g%d" % i, "clique", b))
                estado["giros"] = atual
        return ev


FAMILIAS = {"mirabox": Mirabox, "elgato2": Elgato2}


# ---------------------------------------------------------------------------
# HID do Windows por ctypes (setupapi + hid + kernel32)
# ---------------------------------------------------------------------------
if EH_WINDOWS:
    import ctypes
    from ctypes import wintypes as W

    _setup = ctypes.WinDLL("setupapi", use_last_error=True)
    _hid = ctypes.WinDLL("hid", use_last_error=True)
    _k32 = ctypes.WinDLL("kernel32", use_last_error=True)

    class _GUID(ctypes.Structure):
        _fields_ = [("Data1", W.DWORD), ("Data2", W.WORD), ("Data3", W.WORD), ("Data4", ctypes.c_ubyte * 8)]

    class _IFDATA(ctypes.Structure):
        _fields_ = [("cbSize", W.DWORD), ("InterfaceClassGuid", _GUID), ("Flags", W.DWORD),
                    ("Reserved", ctypes.c_void_p)]

    class _ATTR(ctypes.Structure):
        _fields_ = [("Size", W.ULONG), ("VendorID", W.USHORT), ("ProductID", W.USHORT),
                    ("VersionNumber", W.USHORT)]

    class _CAPS(ctypes.Structure):
        _fields_ = [("Usage", W.USHORT), ("UsagePage", W.USHORT), ("InputReportByteLength", W.USHORT),
                    ("OutputReportByteLength", W.USHORT), ("FeatureReportByteLength", W.USHORT),
                    ("Reserved", W.USHORT * 17), ("NumberLinkCollectionNodes", W.USHORT),
                    ("NumberInputButtonCaps", W.USHORT), ("NumberInputValueCaps", W.USHORT),
                    ("NumberInputDataIndices", W.USHORT), ("NumberOutputButtonCaps", W.USHORT),
                    ("NumberOutputValueCaps", W.USHORT), ("NumberOutputDataIndices", W.USHORT),
                    ("NumberFeatureButtonCaps", W.USHORT), ("NumberFeatureValueCaps", W.USHORT),
                    ("NumberFeatureDataIndices", W.USHORT)]

    _INVALIDO = ctypes.c_void_p(-1).value
    _setup.SetupDiGetClassDevsW.restype = W.HANDLE
    _setup.SetupDiGetClassDevsW.argtypes = [ctypes.POINTER(_GUID), W.LPCWSTR, W.HWND, W.DWORD]
    _setup.SetupDiEnumDeviceInterfaces.argtypes = [W.HANDLE, ctypes.c_void_p, ctypes.POINTER(_GUID), W.DWORD,
                                                   ctypes.POINTER(_IFDATA)]
    _setup.SetupDiGetDeviceInterfaceDetailW.argtypes = [W.HANDLE, ctypes.POINTER(_IFDATA), ctypes.c_void_p,
                                                        W.DWORD, ctypes.POINTER(W.DWORD), ctypes.c_void_p]
    _setup.SetupDiDestroyDeviceInfoList.argtypes = [W.HANDLE]
    _k32.CreateFileW.restype = W.HANDLE
    _k32.CreateFileW.argtypes = [W.LPCWSTR, W.DWORD, W.DWORD, ctypes.c_void_p, W.DWORD, W.DWORD, W.HANDLE]
    _k32.CloseHandle.argtypes = [W.HANDLE]
    _k32.ReadFile.argtypes = [W.HANDLE, ctypes.c_void_p, W.DWORD, ctypes.POINTER(W.DWORD), ctypes.c_void_p]
    _k32.WriteFile.argtypes = [W.HANDLE, ctypes.c_void_p, W.DWORD, ctypes.POINTER(W.DWORD), ctypes.c_void_p]
    _k32.CancelIoEx.argtypes = [W.HANDLE, ctypes.c_void_p]
    for f in ("HidD_GetAttributes", "HidD_GetPreparsedData", "HidD_FreePreparsedData",
              "HidD_GetProductString", "HidD_GetSerialNumberString", "HidD_SetFeature"):
        getattr(_hid, f).restype = W.BOOLEAN
    _hid.HidD_GetAttributes.argtypes = [W.HANDLE, ctypes.POINTER(_ATTR)]
    _hid.HidD_GetPreparsedData.argtypes = [W.HANDLE, ctypes.POINTER(ctypes.c_void_p)]
    _hid.HidD_FreePreparsedData.argtypes = [ctypes.c_void_p]
    _hid.HidP_GetCaps.argtypes = [ctypes.c_void_p, ctypes.POINTER(_CAPS)]
    _hid.HidD_GetProductString.argtypes = [W.HANDLE, ctypes.c_void_p, W.ULONG]
    _hid.HidD_GetSerialNumberString.argtypes = [W.HANDLE, ctypes.c_void_p, W.ULONG]
    _hid.HidD_SetFeature.argtypes = [W.HANDLE, ctypes.c_void_p, W.ULONG]

    def _abrir(caminho, acesso):
        return _k32.CreateFileW(caminho, acesso, 0x3, None, 3, 0, None)  # compartilhado, OPEN_EXISTING

    def listar_hid():
        """[{caminho, vid, pid, pagina, uso, entrada, saida, feature, produto, serie}]"""
        guid = _GUID()
        _hid.HidD_GetHidGuid(ctypes.byref(guid))
        lista = _setup.SetupDiGetClassDevsW(ctypes.byref(guid), None, None, 0x12)
        if not lista or lista == _INVALIDO:
            return []
        out = []
        try:
            i = 0
            while True:
                ifd = _IFDATA()
                ifd.cbSize = ctypes.sizeof(_IFDATA)
                if not _setup.SetupDiEnumDeviceInterfaces(lista, None, ctypes.byref(guid), i, ctypes.byref(ifd)):
                    break
                i += 1
                req = W.DWORD()
                _setup.SetupDiGetDeviceInterfaceDetailW(lista, ctypes.byref(ifd), None, 0, ctypes.byref(req), None)
                buf = ctypes.create_string_buffer(req.value)
                ctypes.cast(buf, ctypes.POINTER(W.DWORD))[0] = 8 if ctypes.sizeof(ctypes.c_void_p) == 8 else 6
                if not _setup.SetupDiGetDeviceInterfaceDetailW(lista, ctypes.byref(ifd), buf, req, None, None):
                    continue
                caminho = ctypes.wstring_at(ctypes.addressof(buf) + 4)
                h = _abrir(caminho, 0)
                if not h or h == _INVALIDO:
                    continue
                try:
                    at = _ATTR()
                    at.Size = ctypes.sizeof(_ATTR)
                    if not _hid.HidD_GetAttributes(h, ctypes.byref(at)):
                        continue
                    if (at.VendorID, at.ProductID) not in MODELOS and (at.VendorID, at.ProductID) not in SEM_SUPORTE:
                        continue
                    caps = _CAPS()
                    pp = ctypes.c_void_p()
                    if _hid.HidD_GetPreparsedData(h, ctypes.byref(pp)):
                        _hid.HidP_GetCaps(pp, ctypes.byref(caps))
                        _hid.HidD_FreePreparsedData(pp)
                    nome = ctypes.create_unicode_buffer(128)
                    serie = ctypes.create_unicode_buffer(128)
                    _hid.HidD_GetProductString(h, nome, ctypes.sizeof(nome))
                    _hid.HidD_GetSerialNumberString(h, serie, ctypes.sizeof(serie))
                    out.append({"caminho": caminho, "vid": at.VendorID, "pid": at.ProductID,
                                "pagina": caps.UsagePage, "uso": caps.Usage,
                                "entrada": caps.InputReportByteLength, "saida": caps.OutputReportByteLength,
                                "feature": caps.FeatureReportByteLength,
                                "produto": nome.value, "serie": serie.value})
                finally:
                    _k32.CloseHandle(h)
        finally:
            _setup.SetupDiDestroyDeviceInfoList(lista)
        return out

    class Conexao:
        """Duas alças: uma só para ler (fica presa no ReadFile) e outra para
        escrever — numa alça síncrona só, a leitura travaria a escrita."""

        def __init__(self, info):
            self.info = info
            self.le = _abrir(info["caminho"], 0x80000000)
            self.escreve = _abrir(info["caminho"], 0x40000000)
            if not self.le or self.le == _INVALIDO or not self.escreve or self.escreve == _INVALIDO:
                self.fechar()
                raise OSError("não consegui abrir o aparelho (outro programa está com ele?)")
            self.trava = threading.Lock()

        def escrever(self, dados):
            with self.trava:
                b = ctypes.create_string_buffer(bytes(dados), len(dados))
                n = W.DWORD()
                if not _k32.WriteFile(self.escreve, b, len(dados), ctypes.byref(n), None):
                    raise OSError("falhou escrever no aparelho (%d)" % ctypes.get_last_error())

        def feature(self, dados):
            with self.trava:
                b = ctypes.create_string_buffer(bytes(dados), len(dados))
                if not _hid.HidD_SetFeature(self.escreve, b, len(dados)):
                    raise OSError("falhou o ajuste do aparelho (%d)" % ctypes.get_last_error())

        def ler(self, tam):
            b = ctypes.create_string_buffer(tam)
            n = W.DWORD()
            if not _k32.ReadFile(self.le, b, tam, ctypes.byref(n), None):
                raise OSError("leitura parou (%d)" % ctypes.get_last_error())
            return b.raw[:n.value]

        def fechar(self):
            for h in (getattr(self, "le", None), getattr(self, "escreve", None)):
                if h and h != _INVALIDO:
                    try:
                        _k32.CancelIoEx(h, None)
                    except Exception:
                        pass
                    _k32.CloseHandle(h)
            self.le = self.escreve = None
else:
    def listar_hid():
        return []

    class Conexao:  # pragma: no cover - só existe no Windows
        def __init__(self, info):
            raise OSError("só no Windows")


# ---------------------------------------------------------------------------
# O aparelho conectado
# ---------------------------------------------------------------------------
class Aparelho:
    def __init__(self, info, modelo, ao_evento):
        self.info, self.modelo, self.ao_evento = info, modelo, ao_evento
        self.proto = FAMILIAS[modelo["familia"]]
        self.chave = "%s:%s" % (modelo["id"], info.get("serie") or info["caminho"][-12:])
        self.con = Conexao(info)
        self.vivo = True
        self.estado_leitura = {"n": modelo["cols"] * modelo["linhas"]}
        self.ultima_atividade = time.time()
        self.erro = ""
        self._iniciar()
        threading.Thread(target=self._ler_sempre, name="deck-ler", daemon=True).start()

    def _mandar(self, pacotes):
        for p in pacotes:
            if isinstance(p, tuple):
                tipo, dados = p
                if tipo == "feature":
                    self.con.feature(dados)
                else:
                    self.con.escrever(dados)
            else:
                self.con.escrever(p)

    def _tam(self):
        return self.info.get("saida") or 1025

    def _iniciar(self):
        if self.modelo["familia"] == "mirabox":
            self._mandar(Mirabox.iniciar(self._tam()))
        else:
            self._mandar(Elgato2.iniciar(self.info.get("feature") or 32))

    def brilho(self, pct):
        if self.modelo["familia"] == "mirabox":
            self._mandar(Mirabox.brilho(pct, self._tam()))
        else:
            self._mandar(Elgato2.brilho(pct, self.info.get("feature") or 32))

    def pintar(self, imagens):
        """imagens: {slot 'kN': bytes JPEG já no tamanho e na rotação do modelo}"""
        if self.modelo["familia"] == "mirabox":
            for slot, jpeg in imagens.items():
                if slot.startswith("k"):
                    self._mandar(Mirabox.imagem(int(slot[1:]), jpeg, self._tam()))
            self._mandar(Mirabox.confirmar(self._tam()))
        else:
            for slot, jpeg in imagens.items():
                if slot.startswith("k"):
                    self._mandar(Elgato2.imagem(int(slot[1:]), jpeg, self._tam() or 1024))

    def manter_vivo(self):
        if self.modelo["familia"] == "mirabox":
            self._mandar(Mirabox.manter(self._tam()))

    def _ler_sempre(self):
        tam = max(512, self.info.get("entrada") or 512)
        while self.vivo:
            try:
                dados = self.con.ler(tam)
            except OSError as e:
                self.erro = str(e)
                self.vivo = False
                break
            for ev in self.proto.ler(dados, self.estado_leitura):
                self.ultima_atividade = time.time()
                try:
                    self.ao_evento(self, *ev)
                except Exception as e:  # um erro numa ação não derruba a leitura
                    self.erro = "%s: %s" % (type(e).__name__, e)

    def fechar(self):
        self.vivo = False
        try:
            self.con.fechar()
        except Exception:
            pass


class Gerente:
    """Procura aparelhos a cada poucos segundos, abre os novos, solta os que
    saíram e guarda as imagens de cada página para repintar quando precisar."""

    def __init__(self, ao_evento):
        self.ao_evento = ao_evento
        self.aparelhos = {}       # chave -> Aparelho
        self.vistos = []          # o que está na USB (inclusive sem suporte)
        self.imagens = {}         # chave do modelo -> {pagina: {slot: jpeg}}
        self.pagina = {}          # chave do aparelho -> índice da página
        self.brilhos = {}         # modelo -> %
        self.trava = threading.RLock()
        self.rodando = False
        self.motivo = ""

    def iniciar(self):
        if self.rodando or not EH_WINDOWS:
            return
        self.rodando = True
        threading.Thread(target=self._vigiar, name="deck-usb", daemon=True).start()

    def _fabricante_aberto(self):
        try:
            import painel
            return sorted({p["nome"] for p in painel.processos() if p["nome"].lower() in PROGRAMAS_DO_FABRICANTE})
        except Exception:
            return []

    def _vigiar(self):
        ultimo_vivo = 0
        while self.rodando:
            try:
                self.varrer()
                if time.time() - ultimo_vivo > 10:
                    ultimo_vivo = time.time()
                    with self.trava:
                        for a in list(self.aparelhos.values()):
                            try:
                                a.manter_vivo()
                            except OSError:
                                a.vivo = False
            except Exception as e:
                self.motivo = "%s: %s" % (type(e).__name__, e)
            time.sleep(3)

    def varrer(self):
        achados = listar_hid()
        with self.trava:
            self.vistos = achados
            # solta o que morreu ou saiu da USB
            caminhos = {d["caminho"] for d in achados}
            for k, a in list(self.aparelhos.items()):
                if not a.vivo or a.info["caminho"] not in caminhos:
                    a.fechar()
                    del self.aparelhos[k]
            abertos = {a.info["caminho"] for a in self.aparelhos.values()}
            for d in achados:
                m = MODELOS.get((d["vid"], d["pid"]))
                if not m or d["caminho"] in abertos:
                    continue
                if PAGINA_DE_USO.get(m["familia"]) and d["pagina"] != PAGINA_DE_USO[m["familia"]]:
                    continue  # a outra interface do aparelho (teclado de mídia etc.)
                try:
                    a = Aparelho(d, m, self.ao_evento)
                except OSError as e:
                    self.motivo = str(e)
                    continue
                self.aparelhos[a.chave] = a
                self.pagina.setdefault(a.chave, 0)
                try:
                    a.brilho(self.brilhos.get(m["id"], 80))
                except OSError:
                    pass
                self._repintar(a)

    def _repintar(self, a):
        imgs = (self.imagens.get(a.modelo["id"]) or {}).get(self.pagina.get(a.chave, 0)) or {}
        if imgs:
            try:
                a.pintar(imgs)
            except OSError as e:
                a.erro = str(e)

    # --- a tela manda ---
    def receber_imagens(self, modelo_id, paginas):
        """paginas: {indice: {slot: base64 JPEG}}"""
        conv = {}
        for p, slots in (paginas or {}).items():
            try:
                conv[int(p)] = {s: base64.b64decode(v) for s, v in (slots or {}).items() if v}
            except (ValueError, TypeError):
                continue
        with self.trava:
            self.imagens[modelo_id] = conv
            for a in self.aparelhos.values():
                if a.modelo["id"] == modelo_id:
                    self._repintar(a)
        return sum(len(v) for v in conv.values())

    def trocar_pagina(self, chave, indice, total):
        with self.trava:
            a = self.aparelhos.get(chave)
            if not a or total <= 0:
                return
            self.pagina[chave] = indice % total
            self._repintar(a)

    def ajustar_brilho(self, modelo_id, pct):
        with self.trava:
            self.brilhos[modelo_id] = pct
            for a in self.aparelhos.values():
                if a.modelo["id"] == modelo_id:
                    try:
                        a.brilho(pct)
                    except OSError as e:
                        a.erro = str(e)

    def estado(self):
        with self.trava:
            conectados = [{"chave": a.chave, "modelo": a.modelo["id"], "nome": a.modelo["nome"],
                           "pagina": self.pagina.get(a.chave, 0), "erro": a.erro,
                           "testado": bool(a.modelo.get("testado"))}
                          for a in self.aparelhos.values()]
            sem = [{"nome": SEM_SUPORTE[(d["vid"], d["pid"])]} for d in self.vistos
                   if (d["vid"], d["pid"]) in SEM_SUPORTE]
        return {"conectados": conectados, "sem_suporte": sem, "fabricante_aberto": self._fabricante_aberto(),
                "catalogo": {m["id"]: publico(m) for m in {v["id"]: v for v in MODELOS.values()}.values()},
                "motivo": self.motivo}

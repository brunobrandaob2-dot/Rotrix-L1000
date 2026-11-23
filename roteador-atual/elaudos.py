# -*- coding: utf-8 -*-
"""Rotrix v2 — fase 4: os exames do E-Laudos baixados pelo próprio Rotrix.

Até aqui quem baixava era o Radius Download Queue (PowerShell). O site do
E-Laudos chama o link  radius-radiant://open?t=TOKEN  e o exame é baixado de
https://app.elaudos.com/rdt/api/radiant/download?t=TOKEN  (um .zip de DICOM).

Agora o roteador faz isso:
- receber_link.py (o Windows chama com o link) entrega o link aqui;
- o .zip vai para  Downloads\\Radius Downloads\\Studies\\<id>.zip  (a mesma pasta
  do Radius) e o estado fica em  state.rotrix.json, NO MESMO FORMATO do estado
  do Radius — a aba E-Laudos, o Abrir, o Laudado e a estatística já leem esse
  formato sem mudar nada;
- até 3 downloads ao mesmo tempo; só https; o .zip só vale se abrir como zip;
- do DICOM sai só o cabeçalho (dicom.py): modalidade, descrição, UID e o nome
  para a tela dele. Nada disso sai do computador.

O token fica guardado só enquanto o exame não terminou de baixar (para continuar
depois de reiniciar ou tentar de novo) e nunca vai para log.
"""
import hashlib
import json
import os
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from datetime import datetime

AQUI = os.path.dirname(os.path.abspath(__file__))
BASE_PADRAO = "https://app.elaudos.com/rdt"
PROTOCOLO = "radius-radiant"
MAX_PARALELO = 3
_URI = re.compile(r"^radius-radiant://open/?\?t=([A-Za-z0-9._-]+)$", re.I)
_PENDENTES = ("Na fila", "Interrompido")
_BLOCO = 1024 * 1024


def token_do_link(uri):
    """O token de um link radius-radiant://open?t=... (None se não for um)."""
    m = _URI.match(str(uri or "").strip().rstrip("/"))
    return m.group(1) if m else None


def id_do_token(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _agora():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def pasta_padrao():
    return os.path.join(os.path.expanduser("~"), "Downloads", "Radius Downloads")


def base_url():
    """A do Radius antigo (radiant.cfg) se existir; senão a do E-Laudos."""
    cfg = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Radius", "radiant.cfg")
    try:
        with open(cfg, encoding="utf-8-sig") as f:
            c = f.readline().strip()
        if c.startswith("https://"):
            return c.rstrip("/")
    except OSError:
        pass
    return BASE_PADRAO


class _SoHttps(urllib.request.HTTPRedirectHandler):
    """Redirecionamento só para https (como no Radius)."""

    def __init__(self, permitir_http=False):
        self.permitir_http = permitir_http

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        esquema = urllib.parse.urlparse(newurl).scheme
        if esquema != "https" and not (self.permitir_http and esquema == "http"):
            raise urllib.error.HTTPError(newurl, code, "redirecionamento inseguro bloqueado", headers, fp)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class Fila:
    """Os downloads do E-Laudos. Um objeto por roteador (ver ligar())."""

    def __init__(self, pasta=None, base=None, ler_cabecalho=None):
        self.pasta = pasta or pasta_padrao()
        self.estudos = os.path.join(self.pasta, "Studies")
        self.arquivo = os.path.join(self.pasta, "state.rotrix.json")
        self.base = (base or base_url()).rstrip("/")
        self.ler_cabecalho = ler_cabecalho or _cabecalho
        self.itens = []
        self.trava = threading.RLock()
        self.rodando = {}          # id -> threading.Event (cancelar)
        self._salvo_em = 0.0
        self.carregar()

    # --- estado em disco (formato do Radius) ---
    def carregar(self):
        try:
            with open(self.arquivo, encoding="utf-8-sig") as f:
                bruto = json.load(f)
        except (OSError, ValueError):
            bruto = []
        itens = []
        for d in bruto if isinstance(bruto, list) else []:
            if not isinstance(d, dict) or not d.get("Id"):
                continue
            d = dict(d)
            st = str(d.get("Status") or "")
            if st.startswith("Baixando") or st in _PENDENTES:
                # caiu no meio (roteador reiniciou): volta para a fila se ainda
                # temos o token; o pedaço baixado é apagado
                d["Status"] = "Na fila" if d.get("Token") else "Interrompido"
            itens.append(d)
        with self.trava:
            self.itens = itens
        try:
            for a in os.listdir(self.estudos):
                if a.endswith(".part"):
                    os.remove(os.path.join(self.estudos, a))
        except OSError:
            pass

    def salvar(self, forcar=True):
        if not forcar and time.time() - self._salvo_em < 1.5:
            return
        with self.trava:
            persist = []
            for d in self.itens:
                x = {k: v for k, v in d.items() if not k.startswith("_")}
                if x.get("Status") == "Pronto":
                    x["Token"] = ""  # baixou: o token não serve mais e não fica guardado
                persist.append(x)
            os.makedirs(self.pasta, exist_ok=True)
            tmp = self.arquivo + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(persist, f, ensure_ascii=False, indent=1)
            os.replace(tmp, self.arquivo)
            self._salvo_em = time.time()

    def _item(self, id_):
        return next((d for d in self.itens if d.get("Id") == id_), None)

    def _achar(self, id_tela):
        """Pelo id que a fila mostra (radius._codigo) ou pelo começo do nosso Id."""
        if not id_tela:
            return None
        try:
            import radius
            sal = radius._sal()
            d = next((x for x in self.itens if radius._codigo(x, sal) == id_tela), None)
            if d:
                return d
        except Exception:
            pass
        return next((x for x in self.itens if x["Id"].startswith(id_tela)), None)

    # --- entrada ---
    def receber(self, uri):
        token = token_do_link(uri)
        if not token:
            return {"ok": False, "motivo": "link_invalido"}
        id_ = id_do_token(token)
        with self.trava:
            d = self._item(id_)
            if d:
                arquivo_ok = os.path.isfile(d.get("FilePath") or "")
                if d["Status"] in ("Falhou", "Cancelado", "Interrompido") or \
                        str(d["Status"]).startswith("Falhou") or (d["Status"] == "Pronto" and not arquivo_ok):
                    d.update(Token=token, Status="Na fila", Error="", IsReported=False, QueueEnteredAt=_agora())
                    frase = "download de novo"
                else:
                    d.update(IsReported=False, QueueEnteredAt=_agora())
                    frase = "já estava na fila"
                self.itens.remove(d)
                self.itens.append(d)
                novo = False
            else:
                d = {"Id": id_, "Token": token, "FilePath": os.path.join(self.estudos, id_ + ".zip"),
                     "Status": "Na fila", "PatientName": "", "Modality": "", "StudyDescription": "",
                     "AccessionNumber": "", "StudyInstanceUID": "", "SizeBytes": 0, "IsReported": False,
                     "CreatedAt": _agora(), "QueueEnteredAt": _agora(), "CompletedAt": "", "Error": "",
                     "Origem": "rotrix"}
                self.itens.append(d)
                frase = "na fila de download"
                novo = True
            self.salvar()
        self.andar()
        return {"ok": True, "id": id_[:12], "novo": novo, "frase": frase}

    # --- downloads ---
    def andar(self):
        """Começa os downloads da fila até MAX_PARALELO."""
        with self.trava:
            livres = MAX_PARALELO - len(self.rodando)
            for d in self.itens:
                if livres <= 0:
                    break
                if d["Status"] == "Na fila" and d.get("Token") and d["Id"] not in self.rodando:
                    ev = threading.Event()
                    self.rodando[d["Id"]] = ev
                    d["Status"] = "Baixando 0%"
                    threading.Thread(target=self._baixar, args=(d, ev), name="elaudos-baixar", daemon=True).start()
                    livres -= 1
            self.salvar()

    def _abrir_url(self, url):
        permitir_http = self.base.startswith("http://")  # só nos testes (localhost)
        opener = urllib.request.build_opener(_SoHttps(permitir_http))
        req = urllib.request.Request(url, headers={"User-Agent": "Rotrix-L1000"})
        return opener.open(req, timeout=60)

    def _baixar(self, d, cancelar):
        url = "%s/api/radiant/download?t=%s" % (self.base, urllib.parse.quote(d["Token"], safe="._-"))
        final = d["FilePath"]
        parte = final + ".part"
        try:
            os.makedirs(self.estudos, exist_ok=True)
            with self._abrir_url(url) as r:
                total = int(r.headers.get("Content-Length") or 0)
                feito = 0
                with open(parte, "wb") as f:
                    while True:
                        if cancelar.is_set():
                            raise _Cancelado()
                        bloco = r.read(_BLOCO)
                        if not bloco:
                            break
                        f.write(bloco)
                        feito += len(bloco)
                        with self.trava:
                            d["Status"] = ("Baixando %d%%" % min(99, feito * 100 // total)) if total \
                                else "Baixando %d MB" % (feito // _BLOCO)
                            d["SizeBytes"] = feito
                            self.salvar(forcar=False)
            if cancelar.is_set():
                raise _Cancelado()
            with zipfile.ZipFile(parte) as z:
                if not z.namelist():
                    raise ValueError("zip vazio")
            os.replace(parte, final)
            cab = self.ler_cabecalho(final) or {}
            with self.trava:
                d.update(Status="Pronto", Token="", Error="", CompletedAt=_agora(),
                         SizeBytes=os.path.getsize(final),
                         PatientName=cab.get("nome", "") or "", Modality=cab.get("modalidade", "") or "",
                         StudyDescription=cab.get("descricao", "") or "",
                         StudyInstanceUID=cab.get("uid", "") or "")
                self._juntar_repetido(d)
        except _Cancelado:
            with self.trava:
                d.update(Status="Cancelado", Error="")
        except urllib.error.HTTPError as e:
            with self.trava:
                d.update(Status="Falhou (HTTP %s)" % e.code, Error="HTTP %s" % e.code)
        except (urllib.error.URLError, OSError, ValueError, zipfile.BadZipFile) as e:
            with self.trava:
                d.update(Status="Falhou (%s)" % type(e).__name__, Error=type(e).__name__)
        finally:
            try:
                if os.path.exists(parte):
                    os.remove(parte)
            except OSError:
                pass
            with self.trava:
                self.rodando.pop(d["Id"], None)
                self.salvar()
            self.andar()

    def _juntar_repetido(self, d):
        """O mesmo estudo (mesmo StudyInstanceUID) baixado por outro link: fica um
        só — o que já estava, que volta para a fila — e o arquivo novo sai."""
        uid = d.get("StudyInstanceUID")
        if not uid:
            return
        velho = next((x for x in self.itens if x is not d and x.get("StudyInstanceUID") == uid
                      and x.get("Status") == "Pronto" and os.path.isfile(x.get("FilePath") or "")), None)
        if not velho:
            return
        try:
            os.remove(d["FilePath"])
        except OSError:
            return
        velho.update(IsReported=False, QueueEnteredAt=_agora())
        self.itens.remove(d)
        self.itens.remove(velho)
        self.itens.append(velho)

    def cancelar(self, id_curto):
        with self.trava:
            d = self._achar(id_curto)
            if not d:
                return {"ok": False, "motivo": "nao_achado"}
            ev = self.rodando.get(d["Id"])
            if ev:
                ev.set()
            elif d["Status"] in _PENDENTES:
                d["Status"] = "Cancelado"
                self.salvar()
        return {"ok": True}

    def esquecer(self, id_curto):
        """Tira a linha da fila (o arquivo baixado, se houver, fica)."""
        with self.trava:
            d = self._achar(id_curto)
            if not d or d["Id"] in self.rodando:
                return {"ok": False, "motivo": "nao_achado"}
            self.itens.remove(d)
            self.salvar()
        return {"ok": True}

    def repetir(self, id_curto):
        with self.trava:
            d = self._achar(id_curto)
            if not d:
                return {"ok": False, "motivo": "nao_achado"}
            if not d.get("Token"):
                return {"ok": False, "motivo": "sem_token",
                        "frase": "clique no exame de novo no E-Laudos para baixar outra vez"}
            d.update(Status="Na fila", Error="")
            self.salvar()
        self.andar()
        return {"ok": True}

    def estado(self):
        """Só contagens e andamento — sem nome de paciente nem token."""
        with self.trava:
            baixando = [{"id": d["Id"][:12], "status": d["Status"], "bytes": d.get("SizeBytes", 0)}
                        for d in self.itens if str(d["Status"]).startswith("Baixando")]
            return {"ok": True, "baixando": baixando,
                    "na_fila": sum(1 for d in self.itens if d["Status"] == "Na fila"),
                    "falhou": sum(1 for d in self.itens if str(d["Status"]).startswith("Falhou")),
                    "prontos": sum(1 for d in self.itens if d["Status"] == "Pronto"),
                    "pasta": self.pasta}


class _Cancelado(Exception):
    pass


def _cabecalho(caminho):
    try:
        import dicom
        return dicom.de(caminho)
    except Exception:
        return {}


# ---------------------------------------------------------------------------
# Links que chegam com o roteador fechado: receber_link.py grava em
# dados/elaudos_entrada/ e o roteador pega quando liga (e a cada poucos segundos)
# ---------------------------------------------------------------------------
ENTRADA = os.path.join(AQUI, "dados", "elaudos_entrada")


def esvaziar_entrada(fila):
    try:
        nomes = sorted(os.listdir(ENTRADA))
    except OSError:
        return 0
    n = 0
    for nome in nomes:
        caminho = os.path.join(ENTRADA, nome)
        try:
            with open(caminho, encoding="utf-8") as f:
                uri = f.read().strip()
            os.remove(caminho)
        except OSError:
            continue
        if fila.receber(uri).get("ok"):
            n += 1
    return n


# ---------------------------------------------------------------------------
# Quem atende o link radius-radiant:// no Windows (Radius ou Rotrix)
# HKCU\Software\Classes\radius-radiant\shell\open\command
# ---------------------------------------------------------------------------
_CHAVE = r"Software\Classes\radius-radiant"
_ANTERIOR = os.path.join(AQUI, "dados", "elaudos_protocolo_anterior.json")


def _pythonw():
    import sys
    exe = sys.executable or "pythonw.exe"
    w = os.path.join(os.path.dirname(exe), "pythonw.exe")
    return w if os.path.isfile(w) else exe


def comando_rotrix():
    return '"%s" "%s" "%%1"' % (_pythonw(), os.path.join(AQUI, "receber_link.py"))


def comando_atual():
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _CHAVE + r"\shell\open\command") as k:
            return winreg.QueryValueEx(k, "")[0]
    except OSError:
        return ""


def quem_atende():
    c = comando_atual().lower()
    if "receber_link.py" in c:
        return "rotrix"
    if "radiusqueue.ps1" in c:
        return "radius"
    return "outro" if c else "ninguem"


def avisar_o_windows():
    """Manda o Windows renovar as associações (SHCNE_ASSOCCHANGED).

    23/11: depois da troca no registro, o Brave (aberto desde antes) continuou
    chamando o Radius — o Windows guarda as associações na memória de cada
    programa até alguém avisar que mudaram. Um programa novo já lia o certo."""
    try:
        import ctypes
        ctypes.windll.shell32.SHChangeNotify(0x08000000, 0x0000, None, None)
        return True
    except Exception:
        return False


def atender_no_rotrix():
    """Passa os links do E-Laudos para o Rotrix (guarda o comando de antes)."""
    import winreg
    antes = comando_atual()
    if antes and "receber_link.py" not in antes.lower():
        os.makedirs(os.path.dirname(_ANTERIOR), exist_ok=True)
        with open(_ANTERIOR, "w", encoding="utf-8") as f:
            json.dump({"comando": antes, "em": _agora()}, f, ensure_ascii=False)
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, _CHAVE) as k:
        winreg.SetValueEx(k, "", 0, winreg.REG_SZ, "URL:Rotrix E-Laudos")
        winreg.SetValueEx(k, "URL Protocol", 0, winreg.REG_SZ, "")
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, _CHAVE + r"\shell\open\command") as k:
        winreg.SetValueEx(k, "", 0, winreg.REG_SZ, comando_rotrix())
    avisar_o_windows()
    return {"ok": True, "atende": quem_atende()}


def devolver_ao_radius():
    """Volta o comando de antes (o do Radius)."""
    import winreg
    try:
        with open(_ANTERIOR, encoding="utf-8") as f:
            antes = json.load(f).get("comando") or ""
    except (OSError, ValueError):
        antes = ""
    if not antes:
        return {"ok": False, "motivo": "sem_anterior", "frase": "não sei qual era o comando de antes"}
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, _CHAVE + r"\shell\open\command") as k:
        winreg.SetValueEx(k, "", 0, winreg.REG_SZ, antes)
    avisar_o_windows()
    return {"ok": True, "atende": quem_atende()}


# ---------------------------------------------------------------------------
# O roteador
# ---------------------------------------------------------------------------
_FILA = {"fila": None, "vigia": None}


def ligar(pasta=None):
    if _FILA["fila"] is None:
        _FILA["fila"] = Fila(pasta)
        _FILA["fila"].andar()

        def vigiar():
            while True:
                try:
                    esvaziar_entrada(_FILA["fila"])
                except Exception:
                    pass
                time.sleep(2)
        _FILA["vigia"] = threading.Thread(target=vigiar, name="elaudos-entrada", daemon=True)
        _FILA["vigia"].start()
    return _FILA["fila"]


def rota(acao, corpo, pasta=None):
    fila = ligar(pasta)
    if acao == "receber":
        return fila.receber(corpo.get("uri"))
    if acao == "estado":
        e = fila.estado()
        e["atende"] = quem_atende()
        return e
    if acao == "cancelar":
        return fila.cancelar(str(corpo.get("id") or ""))
    if acao == "repetir":
        return fila.repetir(str(corpo.get("id") or ""))
    if acao == "esquecer":
        return fila.esquecer(str(corpo.get("id") or ""))
    if acao == "ligar":
        return atender_no_rotrix()
    if acao == "desligar":
        return devolver_ao_radius()
    return {"ok": False, "motivo": "acao_desconhecida"}

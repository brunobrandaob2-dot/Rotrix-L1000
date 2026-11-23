# -*- coding: utf-8 -*-
"""Fase 4: downloads do E-Laudos pelo Rotrix (elaudos.py), contra um servidor
local que finge ser o E-Laudos. Não toca no registro do Windows nem na pasta de
verdade: tudo numa pasta temporária."""
import io
import json
import os
import shutil
import struct
import sys
import tempfile
import threading
import time
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import elaudos  # noqa: E402
import radius  # noqa: E402
import receber_link  # noqa: E402

falhas = 0


def confere(nome, ok, detalhe=""):
    global falhas
    print(("ok     " if ok else "FALHA  ") + nome + ("" if ok else "  -> %r" % (detalhe,)))
    if not ok:
        falhas += 1


def dicom_falso(nome="FULANO DE TAL", mod="CT", desc="TC DE TORAX", uid="1.2.840.99999.7"):
    def elem(g, e, vr, val):
        b = val.encode("latin-1")
        if len(b) % 2:
            b += b" "
        return struct.pack("<HH", g, e) + vr + struct.pack("<H", len(b)) + b
    meta = (elem(0x0002, 0x0002, b"UI", "1.2.840.10008.5.1.4.1.1.2")
            + elem(0x0002, 0x0010, b"UI", "1.2.840.10008.1.2.1"))
    cab = struct.pack("<HH", 0x0002, 0x0000) + b"UL" + struct.pack("<H", 4) + struct.pack("<I", len(meta))
    corpo = (elem(0x0008, 0x0020, b"DA", "20261122") + elem(0x0008, 0x0030, b"TM", "140512")
             + elem(0x0008, 0x0060, b"CS", mod) + elem(0x0008, 0x1030, b"LO", desc)
             + elem(0x0010, 0x0010, b"PN", nome) + elem(0x0020, 0x000D, b"UI", uid))
    return b"\0" * 128 + b"DICM" + cab + meta + corpo


def zip_com(dcm, tamanho_extra=0):
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        z.writestr("serie1/IM0001.dcm", dcm)
        if tamanho_extra:
            z.writestr("lixo.bin", os.urandom(tamanho_extra))
    return b.getvalue()


ZIPS = {"tokA": zip_com(dicom_falso()),
        "tokB": zip_com(dicom_falso(uid="1.2.840.99999.7")),       # o mesmo estudo por outro link
        "tokLento": zip_com(dicom_falso(uid="9.9.9"), 3 * 1024 * 1024),
        "tokRuim": b"isto nao e zip"}
PEDIDOS = []


class Falso(BaseHTTPRequestHandler):
    def do_GET(self):
        PEDIDOS.append(self.path)
        t = self.path.split("t=", 1)[-1]
        if not self.path.startswith("/rdt/api/radiant/download?t=") or t == "tokProibido":
            self.send_response(403)
            self.end_headers()
            return
        corpo = ZIPS.get(t, b"")
        self.send_response(200)
        self.send_header("Content-Length", str(len(corpo)))
        self.end_headers()
        if t == "tokLento":
            for i in range(0, len(corpo), 64 * 1024):
                try:
                    self.wfile.write(corpo[i:i + 64 * 1024])
                    time.sleep(0.05)
                except OSError:
                    return
        else:
            self.wfile.write(corpo)

    def log_message(self, *a):
        pass


srv = ThreadingHTTPServer(("127.0.0.1", 0), Falso)
threading.Thread(target=srv.serve_forever, daemon=True).start()
BASE = "http://127.0.0.1:%d/rdt" % srv.server_address[1]
pasta = tempfile.mkdtemp(prefix="elaudos_teste_")


def esperar(fila, cond, s=15):
    fim = time.time() + s
    while time.time() < fim:
        with fila.trava:
            if cond():
                return True
        time.sleep(0.05)
    return False


try:
    # --- links ---
    confere("link do E-Laudos dá o token", elaudos.token_do_link("radius-radiant://open?t=abc.DEF_1-2") == "abc.DEF_1-2")
    confere("link com barra no fim também", elaudos.token_do_link("radius-radiant://open/?t=abc/") == "abc")
    confere("link de outro jeito não entra", elaudos.token_do_link("radius-radiant://open?t=a&x=b") is None
            and elaudos.token_do_link("https://open?t=a") is None and elaudos.token_do_link("") is None)

    f = elaudos.Fila(pasta, base=BASE)
    r = f.receber("radius-radiant://open?t=tokA")
    confere("link válido entra na fila", r["ok"] and r["novo"], r)
    confere("link inválido é recusado", not f.receber("radius-radiant://open?t=../../x")["ok"])
    d = f.itens[0]
    confere("baixa e fica Pronto", esperar(f, lambda: d["Status"] == "Pronto"), d["Status"])
    confere("o .zip fica em Studies com o id", os.path.isfile(os.path.join(pasta, "Studies", d["Id"] + ".zip")))
    confere("do DICOM: modalidade, descrição, UID e nome", (d["Modality"], d["StudyDescription"], d["StudyInstanceUID"])
            == ("CT", "TC DE TORAX", "1.2.840.99999.7") and d["PatientName"], d)
    disco = json.load(open(os.path.join(pasta, "state.rotrix.json"), encoding="utf-8"))
    confere("depois de baixar o token não fica no disco", disco[0]["Token"] == "", disco[0].get("Token"))
    confere("o pedido foi o do E-Laudos", PEDIDOS[-1] == "/rdt/api/radiant/download?t=tokA", PEDIDOS[-1:])
    confere("sem .part sobrando", not [a for a in os.listdir(os.path.join(pasta, "Studies")) if a.endswith(".part")])

    # a fila do Rotrix (radius.py) lê o estado sem mudar nada
    radius._CACHE["chave"] = None
    fila = radius.ler_fila(pasta)
    x = next((i for i in fila if i["descricao"] == "TC DE TORAX"), None)
    confere("a aba E-Laudos mostra o exame (origem radius)", x and x["origem"] == "radius" and x["modalidade"] == "CT", fila)
    confere("o Abrir acha o arquivo", x and list(radius.caminhos(pasta, [x["id"]]).values()) == [d["FilePath"]])
    confere("a pasta Studies não vira 'baixado por fora'", not [i for i in fila if i["origem"] == "pasta"], fila)

    # mesmo link de novo: não baixa outra vez
    n = len(PEDIDOS)
    r = f.receber("radius-radiant://open?t=tokA")
    time.sleep(0.3)
    confere("mesmo link: não baixa de novo", not r["novo"] and len(PEDIDOS) == n and len(f.itens) == 1, r)
    # outro link, mesmo estudo (mesmo UID): fica um só
    f.receber("radius-radiant://open?t=tokB")
    esperar(f, lambda: len(f.itens) == 1 and not f.rodando)
    confere("mesmo estudo por outro link: fica um só", len(f.itens) == 1 and len(os.listdir(os.path.join(pasta, "Studies"))) == 1,
            [i["Status"] for i in f.itens])

    # erros
    f.receber("radius-radiant://open?t=tokProibido")
    ruim = f.itens[-1]
    confere("HTTP 403 vira Falhou (HTTP 403)", esperar(f, lambda: ruim["Status"] == "Falhou (HTTP 403)"), ruim["Status"])
    disco = json.load(open(os.path.join(pasta, "state.rotrix.json"), encoding="utf-8"))
    confere("o que falhou guarda o token para tentar de novo", any(i["Token"] == "tokProibido" for i in disco))
    f.receber("radius-radiant://open?t=tokRuim")
    ruim2 = f.itens[-1]
    confere("arquivo que não é zip vira Falhou e é apagado",
            esperar(f, lambda: ruim2["Status"].startswith("Falhou")) and not os.path.exists(ruim2["FilePath"]), ruim2["Status"])
    radius._CACHE["chave"] = None
    st = {i["status"] for i in radius.ler_fila(pasta)}
    confere("a fila mostra a falha", any(s.startswith("Falhou") for s in st), st)

    # cancelar no meio
    f.receber("radius-radiant://open?t=tokLento")
    lento = f.itens[-1]
    confere("mostra o andamento (Baixando N%)", esperar(f, lambda: lento["Status"].startswith("Baixando ") and lento["Status"] != "Baixando 0%"),
            lento["Status"])
    radius._CACHE["chave"] = None
    xs = [i for i in radius.ler_fila(pasta) if i["status"].startswith("Baixando")]
    confere("cancelar pelo id que a tela mostra", f.cancelar(xs[0]["id"])["ok"] if xs else False, xs)
    confere("cancelado e sem pedaço no disco", esperar(f, lambda: lento["Status"] == "Cancelado")
            and not os.path.exists(lento["FilePath"] + ".part"), lento["Status"])
    r = f.repetir(xs[0]["id"]) if xs else {}
    confere("tentar de novo baixa até o fim", r.get("ok") and esperar(f, lambda: lento["Status"] == "Pronto", 30), lento["Status"])

    # o roteador caiu no meio: volta para a fila
    with open(os.path.join(pasta, "state.rotrix.json"), "w", encoding="utf-8") as fh:
        json.dump([{"Id": "x" * 64, "Token": "tokA", "Status": "Baixando 40%", "FilePath": os.path.join(pasta, "Studies", "x.zip")},
                   {"Id": "y" * 64, "Token": "", "Status": "Na fila", "FilePath": ""}], fh)
    open(os.path.join(pasta, "Studies", "x.zip.part"), "wb").write(b"meio")
    g = elaudos.Fila(pasta, base=BASE)
    confere("reiniciou: o que estava baixando volta para a fila; sem token, Interrompido",
            [i["Status"] for i in g.itens] == ["Na fila", "Interrompido"], [i["Status"] for i in g.itens])
    confere("reiniciou: o pedaço baixado é apagado", not os.path.exists(os.path.join(pasta, "Studies", "x.zip.part")))

    # redirecionamento para http (fora do teste) é bloqueado
    h = elaudos._SoHttps(False)
    try:
        h.redirect_request(None, None, 302, "", {}, "http://malicioso/x")
        bloqueou = False
    except Exception:
        bloqueou = True
    confere("redirecionamento para http é bloqueado", bloqueou)

    # links que chegam com o roteador fechado
    elaudos.ENTRADA = os.path.join(pasta, "entrada")
    os.makedirs(elaudos.ENTRADA)
    receber_link.AQUI = pasta
    os.makedirs(os.path.join(pasta, "dados"), exist_ok=True)
    receber_link.guardar("radius-radiant://open?t=tokA")
    elaudos.ENTRADA = os.path.join(pasta, "dados", "elaudos_entrada")
    n = elaudos.esvaziar_entrada(g)
    confere("link guardado com o roteador fechado entra quando ele liga", n == 1 and not os.listdir(elaudos.ENTRADA), n)
    confere("receber_link recusa o que não é link do E-Laudos", receber_link.main(["https://x"]) == 2)
    confere("o comando do Windows chama o receber_link", "receber_link.py" in elaudos.comando_rotrix()
            and elaudos.comando_rotrix().endswith('"%1"'))
finally:
    srv.shutdown()
    time.sleep(0.3)
    shutil.rmtree(pasta, ignore_errors=True)

print("\nelaudos: %s" % ("tudo certo" if not falhas else "%d falha(s)" % falhas))
sys.exit(1 if falhas else 0)

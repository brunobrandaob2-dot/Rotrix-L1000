# -*- coding: utf-8 -*-
"""O Windows chama isto quando você clica num exame no E-Laudos (link
radius-radiant://open?t=...), se o Rotrix estiver atendendo esses links.

Entrega o link ao roteador (127.0.0.1:8123). Roteador fechado: guarda o link em
dados/elaudos_entrada/ e liga o roteador, que baixa quando subir.
Só aceita o formato do link do E-Laudos; não escreve o token em log nenhum."""
import json
import os
import re
import subprocess
import sys
import time
import urllib.request

AQUI = os.path.dirname(os.path.abspath(__file__))
_URI = re.compile(r"^radius-radiant://open/?\?t=[A-Za-z0-9._-]+/?$", re.I)


def entregar(uri):
    req = urllib.request.Request("http://127.0.0.1:8123/v1/elaudos/receber",
                                 data=json.dumps({"uri": uri}).encode("utf-8"), method="POST",
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=5) as r:
        return json.loads(r.read().decode("utf-8") or "{}").get("ok")


def guardar(uri):
    pasta = os.path.join(AQUI, "dados", "elaudos_entrada")
    os.makedirs(pasta, exist_ok=True)
    nome = "%020d_%d.txt" % (time.time_ns(), os.getpid())
    with open(os.path.join(pasta, nome), "w", encoding="utf-8") as f:
        f.write(uri)


def ligar_roteador():
    exe = sys.executable
    w = os.path.join(os.path.dirname(exe), "pythonw.exe")
    subprocess.Popen([w if os.path.isfile(w) else exe, os.path.join(AQUI, "roteador.py")], cwd=AQUI,
                     creationflags=0x08000000 | 0x00000200, close_fds=True,
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def main(args):
    uri = (args[0] if args else "").strip()
    if not _URI.match(uri):
        return 2
    try:
        if entregar(uri):
            return 0
    except Exception:
        pass
    guardar(uri)
    try:
        ligar_roteador()
    except OSError:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

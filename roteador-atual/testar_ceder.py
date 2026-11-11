# -*- coding: utf-8 -*-
"""A cópia do roteador que vem no app cede ao de Documentos\\laudo-router (python testar_ceder.py).

11/11: "por algum motivo a IA não está funcionando no Rotrix". Na 8123 respondia a cópia
do app (AppData\\Roaming\\com.rotrix.l1000\\roteador): 25.296 gatilhos, nenhuma chave, sem
as máscaras dele. O app liga essa cópia quando a porta está livre na hora em que abre
(depois de reiniciar o PC, por exemplo). Agora ela liga o roteador de Documentos, solto
do app, espera ele responder e sai."""
import http.server
import io
import json
import os
import socket
import sys
import tempfile
import threading

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
import roteador as r  # noqa: E402

FALSO = r'''# roteador falso: responde /v1/versao com a pasta dele e sai sozinho em 20 s
import http.server, json, os, sys, threading
PORTA = int(sys.argv[1]) if len(sys.argv) > 1 else int(os.environ["PORTA_TESTE"])
class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        corpo = json.dumps({"versao": "teste", "pasta": os.getcwd(),
                            "colador_env": os.environ.get("ROTEADOR_COLADOR", "")}).encode()
        self.send_response(200); self.end_headers(); self.wfile.write(corpo)
    def log_message(self, *a): pass
srv = http.server.HTTPServer(("127.0.0.1", PORTA), H)
threading.Timer(20, srv.shutdown).start()
srv.serve_forever()
'''


def porta_livre():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def main():
    falhas = []

    def ok(cond, nome):
        print(("ok      " if cond else "FALHA   ") + nome)
        if not cond:
            falhas.append(nome)

    tmp = tempfile.mkdtemp()
    home = os.path.join(tmp, "bruno")
    app = os.path.join(home, "AppData", "Roaming", "com.rotrix.l1000", "roteador")
    doc = os.path.join(home, "Documents", "laudo-router")
    os.makedirs(app)
    ok(r._documentos_para_ceder(app, home) is None, "sem laudo-router em Documentos: a cópia do app segue")
    os.makedirs(doc)
    with open(os.path.join(doc, "roteador.py"), "w", encoding="utf-8") as f:
        f.write(FALSO)
    ok(r._documentos_para_ceder(app, home) == doc, "com laudo-router em Documentos: a cópia do app cede")
    ok(r._documentos_para_ceder(doc, home) is None, "o de Documentos nunca cede (não entra em laço)")
    os.environ["ROTRIX_NAO_CEDER"] = "1"
    ok(r._documentos_para_ceder(app, home) is None, "ROTRIX_NAO_CEDER=1 desliga a cessão")
    del os.environ["ROTRIX_NAO_CEDER"]

    # de verdade: liga o "roteador de Documentos" (falso) e espera ele responder com a pasta dele
    porta = porta_livre()
    os.environ["PORTA_TESTE"] = str(porta)
    os.environ["ROTEADOR_COLADOR"] = os.path.join(app, "colador.exe")
    cedeu = r._ceder_para_documentos(doc, espera_s=15, porta=porta, python=sys.executable)
    ok(cedeu, "liga o roteador de Documentos e vê ele responder com a pasta dele")
    if cedeu:
        import urllib.request
        abrir = urllib.request.build_opener(urllib.request.ProxyHandler({})).open
        v = json.loads(abrir("http://127.0.0.1:%d/v1/versao" % porta, timeout=2).read().decode())
        ok(v.get("colador_env") == "", "o roteador de Documentos não herda o colador do app")
    os.environ.pop("ROTEADOR_COLADOR", None)

    # outra pasta na porta (a própria cópia do app, por exemplo) não conta como cedido
    p2 = porta_livre()

    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(json.dumps({"pasta": app}).encode())

        def log_message(self, *a):
            pass

    srv = http.server.HTTPServer(("127.0.0.1", p2), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    doc_vazio = os.path.join(tmp, "outro", "laudo-router")
    os.makedirs(doc_vazio)
    with open(os.path.join(doc_vazio, "roteador.py"), "w", encoding="utf-8") as f:
        f.write("import sys; sys.exit(0)\n")
    ok(not r._ceder_para_documentos(doc_vazio, espera_s=3, porta=p2, python=sys.executable),
       "se quem responde não é o de Documentos, a cópia do app segue (não fica sem roteador)")
    srv.shutdown()

    src = open(os.path.join(AQUI, "roteador.py"), encoding="utf-8").read()
    i_main = src.find('if __name__ == "__main__":')
    i_ceder, i_base, i_srv = (src.find(x, i_main) for x in ("_documentos_para_ceder()", "_base_em_dia()",
                                                              "srv = _abrir_servidor()"))
    ok(0 <= i_ceder < i_base < i_srv, "cede antes de refazer a base e antes de abrir a porta")

    print()
    print("cessão ao roteador de Documentos: tudo certo" if not falhas else "cessão: %d falha(s)" % len(falhas))
    sys.exit(1 if falhas else 0)


if __name__ == "__main__":
    main()

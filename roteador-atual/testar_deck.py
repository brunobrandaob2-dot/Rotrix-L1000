# -*- coding: utf-8 -*-
"""Stream Deck / Stream Dock (fase 3): os protocolos e o mapa das teclas.

Monta os bytes de cada comando e lê relatórios de entrada falsos — não precisa
do aparelho e não abre nada. O AKP03E foi conferido no aparelho em 22/11/2026.
"""
import os
import base64
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import deck  # noqa: E402
import painel  # noqa: E402

falhas = 0


def confere(nome, ok, detalhe=""):
    global falhas
    print(("ok     " if ok else "FALHA  ") + nome + ("" if ok else "  -> %r" % (detalhe,)))
    if not ok:
        falhas += 1


M = deck.Mirabox
c = M.cmd(b"STP")
confere("Mirabox: relatório com 1025 bytes e prefixo CRT", len(c) == 1025 and c[:9] == b"\x00CRT\x00\x00STP", c[:12])
confere("Mirabox: brilho 80", M.brilho(80)[0][6:12] == b"LIG\x00\x00\x50")
confere("Mirabox: brilho fora da faixa fica em 100", M.brilho(300)[0][11] == 100)
jpeg = bytes(range(256)) * 9  # 2304 bytes
p = M.imagem(4, jpeg)
confere("Mirabox: imagem = cabeçalho BAT + 3 pacotes", len(p) == 4, len(p))
confere("Mirabox: tamanho e tecla no cabeçalho", p[0][6:14] == b"BAT\x00\x00" + bytes([0x09, 0x00, 5]), p[0][6:14])
confere("Mirabox: pacotes de dados com 1025 bytes", all(len(x) == 1025 for x in p[1:]))
confere("Mirabox: os dados chegam inteiros", b"".join(x[1:] for x in p[1:])[:len(jpeg)] == jpeg)


def ack(cod, est):
    return b"ACK" + bytes(6) + bytes([cod, est]) + bytes(500)


confere("Mirabox: tecla 1 apertada", M.ler(ack(1, 1)) == [("k0", "tecla", True)])
confere("Mirabox: tecla 6 solta", M.ler(ack(6, 0)) == [("k5", "tecla", False)])
confere("Mirabox: botão sem tela B", M.ler(ack(0x30, 1)) == [("b1", "tecla", True)])
confere("Mirabox: giratório esquerdo para a direita", M.ler(ack(0x91, 0)) == [("g0", "girar+", True)])
confere("Mirabox: clique do giratório de cima", M.ler(ack(0x35, 1)) == [("g1", "clique", True)])
confere("Mirabox: relatório sem ACK é ignorado", M.ler(b"XYZ" + bytes(20)) == [])
confere("Mirabox: com o byte 0x00 do relatório na frente (ReadFile do Windows)",
        M.ler(b"\x00" + ack(3, 1)) == [("k2", "tecla", True)])

E = deck.Elgato2
p = E.imagem(3, bytes(2500))
confere("Elgato: 3 pacotes de 1024 para 2500 bytes", len(p) == 3 and all(len(x[1]) == 1024 for x in p), [len(x[1]) for x in p])
confere("Elgato: só o último pacote marcado", [x[1][3] for x in p] == [0, 0, 1])
confere("Elgato: tecla e página no cabeçalho", p[1][1][:3] == bytes([0x02, 0x07, 3]) and p[1][1][6] == 1)
est = {"n": 15}
confere("Elgato: tecla 3 apertada", E.ler(bytes([1, 0, 15, 0, 0, 0, 1] + [0] * 12), est) == [("k2", "tecla", True)])
confere("Elgato: tecla 3 solta", E.ler(bytes([1, 0, 15, 0] + [0] * 15), est) == [("k2", "tecla", False)])

m = deck.MODELOS[(0x0300, 0x3002)]
confere("AKP03E: 6 teclas, 3 botões, 3 giratórios", deck.slots_do_modelo(m) ==
        ["k0", "k1", "k2", "k3", "k4", "k5", "b0", "b1", "b2", "g0", "g1", "g2"])
pub = deck.publico(m)
confere("catálogo diz o tamanho e a rotação da imagem", pub["img"] == {"w": 64, "h": 64, "rot": 90, "espelhar": False})

# --- mapa no painel.json ---
cfg = painel.normalizar(None)
a = cfg["aparelhos"].get("akp03e")
confere("painel padrão já traz o AKP03E mapeado", a and a["perfis"][0]["paginas"][0]["m"]["k0"] == "l_proximo", a)
lixo = painel.normalizar({"versao": 3, "paginas": cfg["paginas"], "aparelhos": {"akp03e": {"paginas": [
    {"nome": "X", "m": {"k0": "nao_existe", "k1": "mesa", "zz": "mesa",
                        "g0": {"girar": "foguete", "clique": "mesa"}}}]}, "../x": {}}})
mm = lixo["aparelhos"]["akp03e"]["perfis"][0]["paginas"][0]["m"]
confere("mapa: tecla inexistente e slot inválido saem; giro inválido vira vazio",
        mm == {"k1": "mesa", "g0": {"girar": "", "clique": "mesa"}}, mm)
confere("mapa: nome de modelo esquisito não entra", "../x" not in lixo["aparelhos"])


# --- perfis no Gerente (sem USB: um aparelho de mentira) ---
class _Ap:
    def __init__(self):
        self.chave, self.modelo, self.pintado = "x1", {"id": "akp03e"}, []

    def pintar(self, imgs):
        self.pintado.append(dict(imgs))


G = deck.Gerente(lambda *a: None)
falso = _Ap()
G.aparelhos["x1"] = falso
um = base64.b64encode(b"A").decode()
dois = base64.b64encode(b"B").decode()
G.receber_imagens("akp03e", {"0.0": {"k0": um}, "1.1": {"k0": dois}, "2": {"k0": um}})
confere("imagens por perfil.página (e o jeito antigo = perfil 0)",
        set(G.imagens["akp03e"]) == {(0, 0), (1, 1), (0, 2)}, list(G.imagens["akp03e"]))
G.trocar_pagina("x1", 3, 2, perfil=1)
confere("trocar perfil + página repinta a imagem certa",
        G.perfil["x1"] == 1 and G.pagina["x1"] == 1 and falso.pintado[-1] == {"k0": b"B"}, (G.perfil, G.pagina))

# tecla "Próximo perfil" e giro "perfil", pelo mesmo caminho de um aperto de verdade
cfg3 = painel.normalizar(None)
painel.carregar = lambda caminho=None: cfg3
painel._DECK["gerente"] = G
G.perfil["x1"], G.pagina["x1"] = 0, 1
painel._ao_evento(falso, "b2", "tecla", True)  # b2 = Próximo perfil
confere("botão C (Próximo perfil) leva ao perfil 2, página 1", (G.perfil["x1"], G.pagina["x1"]) == (1, 0),
        (G.perfil["x1"], G.pagina["x1"]))
painel._ao_evento(falso, "b2", "tecla", True)
confere("depois do último perfil volta ao primeiro", G.perfil["x1"] == 0)
cfg3["aparelhos"]["akp03e"]["perfis"][0]["paginas"][0]["m"]["g1"] = {"girar": "perfil", "clique": ""}
painel._ao_evento(falso, "g1", "girar-", True)
confere("giratório no modo perfil anda para trás", G.perfil["x1"] == 1, G.perfil["x1"])
ev = painel.deck_rota("deck_eventos", {})["eventos"]
confere("a tela fica sabendo do perfil novo", bool(ev) and ev[-1].get("perfil") == 1 and ev[-1].get("modelo") == "akp03e",
        ev[-1:])
r = painel._acao_aparelho({"nome": "Ir", "comando": "perfil_ir", "destino": "laudo"})
confere("Ir para o perfil pelo nome (sem ligar para maiúsculas)", r["ok"] and G.perfil["x1"] == 0, r)
r = painel._acao_aparelho({"nome": "Ir", "comando": "perfil_ir", "destino": "Não existe"})
confere("perfil que não existe: avisa", not r["ok"], r)
G.pagina["x1"] = 0
r = painel._acao_aparelho({"nome": "Pág", "comando": "pagina_anterior"})
confere("página anterior da primeira vai para a última do perfil", r["ok"] and G.pagina["x1"] == 1, G.pagina)

print("\ndeck: %s" % ("tudo certo" if not falhas else "%d falha(s)" % falhas))
sys.exit(1 if falhas else 0)

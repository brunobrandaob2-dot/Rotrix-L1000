# -*- coding: utf-8 -*-
"""Testes das rotas novas da interface v2 (python testar_v2.py).

Cobre o que os botões das abas chamam: o banco de máscaras da aba Máscaras, o
pedido falado para a IA sobre o banco, a IA sobre o texto da folha e o "abrir
juntos no RadiAnt" da aba Fila.

O que mais importa aqui: NENHUMA dessas rotas pode devolver nome de paciente
nem caminho de pasta — o caminho tem o nome do paciente dentro.
"""
import io
import json
import os
import shutil
import sys
import tempfile

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import radius  # noqa: E402
import roteador  # noqa: E402

PROIBIDOS = ["FULANO", "BELTRANO", "CICLANO", "SOUZA", "123456789", "987654321",
             "Downloads", "estudo.zip", "SEGREDO"]


def _estudo(nome, acesso, pasta, mod="CT", desc="TC DE TORAX"):
    return {"AccessionNumber": acesso, "PatientName": nome, "Modality": mod,
            "StudyDescription": desc, "Status": "Downloaded", "IsReported": False,
            "QueueEnteredAt": "2026-09-23T10:00:00",
            "StudyInstanceUID": "1.2.840.99999." + acesso,
            "FilePath": os.path.join(pasta, "%s %s" % (nome, acesso), "estudo.zip"),
            "Token": "SEGREDO-" + acesso}


def banco(falhas):
    b = roteador.mascaras_banco("joelho")
    if not b.get("ok") or not b.get("mascaras"):
        falhas.append("banco: busca por joelho não trouxe máscara")
        return
    if not b.get("regioes"):
        falhas.append("banco: sem lista de regiões")
    m = b["mascaras"][0]
    for campo in ("titulo", "nome", "regiao", "gatilhos", "tamanho"):
        if campo not in m:
            falhas.append("banco: máscara sem campo %s" % campo)
    if not m["gatilhos"]:
        falhas.append("banco: máscara sem gatilho (ninguém consegue chamar por voz)")
    if "_" in m["nome"]:
        falhas.append("banco: nome ainda com underline: %r" % m["nome"])
    inteira = roteador.mascaras_banco("", m["titulo"])
    if not inteira.get("texto"):
        falhas.append("banco: pedir o título não trouxe o texto da máscara")
    elif len(inteira["texto"]) != m["tamanho"]:
        falhas.append("banco: tamanho anunciado %d, texto com %d"
                      % (m["tamanho"], len(inteira["texto"])))
    vazio = roteador.mascaras_banco("xpto que nao existe em lugar nenhum")
    if vazio.get("mascaras"):
        falhas.append("banco: busca sem resultado devolveu máscara")
    limitado = roteador.mascaras_banco("", "", 3)
    if len(limitado.get("mascaras") or []) > 3:
        falhas.append("banco: limite não respeitado")


def ia(falhas):
    if roteador.ia_no_texto("").get("motivo") != "texto_vazio":
        falhas.append("ia: folha vazia deveria dizer texto_vazio")
    if roteador.ia_no_texto("   ").get("ok"):
        falhas.append("ia: só espaço não pode ser aceito")
    r = roteador.mascaras_ia("")
    if r.get("motivo") != "instrucao_vazia":
        falhas.append("ia do banco: pedido vazio deveria dizer instrucao_vazia")
    # sem chave/sem internet: tem que responder, não levantar exceção
    r = roteador.mascaras_ia("revisa a escrita", "joelho")
    if r.get("ok"):
        falhas.append("ia do banco: sem chave não pode dar ok")
    if not r.get("motivo"):
        falhas.append("ia do banco: falhou sem dizer o motivo")
    r = roteador.ia_no_texto("Derrame pleural à direita.")
    if r.get("ok"):
        falhas.append("ia: sem chave não pode dar ok")
    if r.get("texto") != "Derrame pleural à direita.":
        falhas.append("ia: quando falha, o texto de volta tem que ser o mesmo")


def abrir_estudos(falhas):
    pasta = tempfile.mkdtemp(prefix="v2_radius_")
    radius._ARQ_SAL = os.path.join(pasta, ".radius_sal_teste")
    try:
        destino = os.path.join(pasta, "Downloads")
        os.makedirs(os.path.join(destino, "FULANO BELTRANO 123456789"))
        with open(os.path.join(destino, "FULANO BELTRANO 123456789", "estudo.zip"), "wb") as f:
            f.write(b"PK\x03\x04 nao abrir")
        estudos = [_estudo("FULANO BELTRANO", "123456789", destino),
                   _estudo("CICLANO SOUZA", "987654321", destino, "CR", "RX TORAX")]
        with open(os.path.join(pasta, "state.beta-v3.json"), "w", encoding="utf-8") as f:
            json.dump(estudos, f)
        fila = radius.ler_fila(pasta)
        if len(fila) != 2:
            falhas.append("abrir: esperava 2 estudos na fila, veio %d" % len(fila))
            return
        ids = [x["id"] for x in fila]
        achados = radius.caminhos(pasta, ids)
        if len(achados) != 1:
            falhas.append("abrir: só o estudo com pasta no disco deveria ter caminho (%d)"
                          % len(achados))
        # o RadiAnt não existe aqui: tem que dizer isso, sem estourar
        r = radius.abrir(pasta, ids, {})
        if r.get("ok"):
            falhas.append("abrir: sem RadiAnt instalado não pode dar ok")
        if r.get("motivo") not in ("radiant_nao_encontrado", "sem_caminho"):
            falhas.append("abrir: motivo inesperado %r" % r.get("motivo"))
        texto = json.dumps(r, ensure_ascii=False)
        for p in PROIBIDOS:
            if p.lower() in texto.lower():
                falhas.append("abrir: a resposta vazou %s" % p)
        # nenhum id pedido: não mexe em nada
        if radius.abrir(pasta, [], {}).get("ok"):
            falhas.append("abrir: lista vazia não pode dar ok")
        if radius.caminhos(pasta, ["id-que-nao-existe"]):
            falhas.append("abrir: id desconhecido não pode virar caminho")
        # a rota do roteador devolve o mesmo formato, sem vazar nada
        rr = roteador.fila_abrir(["id-que-nao-existe"])
        if rr.get("ok"):
            falhas.append("rota /fila/abrir: id inexistente não pode dar ok")
        for p in PROIBIDOS:
            if p.lower() in json.dumps(rr, ensure_ascii=False).lower():
                falhas.append("rota /fila/abrir vazou %s" % p)
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


def main():
    falhas = []
    banco(falhas)
    ia(falhas)
    abrir_estudos(falhas)
    for f in falhas:
        print("FALHOU", f)
    print("v2: tudo certo" if not falhas else "v2: %d falha(s)" % len(falhas))
    sys.exit(1 if falhas else 0)


if __name__ == "__main__":
    main()

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



def iniciais_e_soltos(falhas):
    """Iniciais no lugar do nome, varredura da pasta e apagar para a Lixeira."""
    casos = [("FULANO BELTRANO DE TAL", "F.B.T."), ("SOUZA^MARIA", "S.M."),
             ("Ciclano", "C."), ("", ""), (None, "")]
    for bruto, esperado in casos:
        if radius.iniciais(bruto) != esperado:
            falhas.append("iniciais de %r: %r" % (bruto, radius.iniciais(bruto)))
    pasta = tempfile.mkdtemp(prefix="v2_soltos_")
    radius._ARQ_SAL = os.path.join(pasta, ".radius_sal_teste")
    radius._ARQ_APAGADOS = os.path.join(pasta, "apagados_teste.json")
    radius._CACHE.update(chave=None, arqs=None, pasta=None, t_arqs=0.0)
    try:
        destino = os.path.join(pasta, "FULANO BELTRANO 123456789")
        os.makedirs(destino)
        with open(os.path.join(destino, "estudo.zip"), "wb") as f:
            f.write(b"PK\x03\x04 nao abrir")
        # esse o Radius registrou: nao pode aparecer como "solto"
        with open(os.path.join(pasta, "state.beta-v3.json"), "w", encoding="utf-8") as f:
            json.dump([_estudo("FULANO BELTRANO", "123456789", pasta)], f)
        # esse foi baixado pelo navegador: so existe na pasta
        pelo_navegador = os.path.join(pasta, "CICLANO SOUZA 555444333")
        os.makedirs(pelo_navegador)
        with open(os.path.join(pelo_navegador, "serie.dcm"), "wb") as f:
            f.write(b"DICM" + b"0" * 2048)
        fila = radius.ler_fila(pasta)
        soltos = [x for x in fila if x.get("origem") == "pasta"]
        do_radius = [x for x in fila if x.get("origem") == "radius"]
        if len(soltos) != 1:
            falhas.append("soltos: esperava 1 exame baixado por fora, veio %d" % len(soltos))
            return
        if not do_radius:
            falhas.append("soltos: a fila do Radius sumiu quando entrou a varredura")
        s = soltos[0]
        if s["iniciais"] != "C.S." or not s["bytes"]:
            falhas.append("soltos: iniciais/tamanho errados: %r" % s)
        for item in fila:
            if "iniciais" not in item:
                falhas.append("fila sem o campo iniciais: %r" % item)
                break
        texto = json.dumps(fila, ensure_ascii=False)
        for p in PROIBIDOS + ["serie.dcm"]:
            if p.lower() in texto.lower():
                falhas.append("fila com varredura vazou %s" % p)
        # apagar: fora da lista e fora da pasta (aqui vai para _apagados, nao ha Lixeira)
        r = radius.apagar(pasta, [s["id"]])
        if not r.get("ok") or r.get("apagados") != 1:
            falhas.append("apagar: resposta %r" % r)
        for p in PROIBIDOS:
            if p.lower() in json.dumps(r, ensure_ascii=False).lower():
                falhas.append("apagar vazou %s" % p)
        if os.path.isdir(pelo_navegador):
            falhas.append("apagar: a pasta do exame continua no lugar")
        if not os.path.isdir(os.path.join(pasta, "_apagados")):
            falhas.append("apagar: nada foi para _apagados (fora do Windows)")
        depois = radius.ler_fila(pasta)
        if any(x["id"] == s["id"] for x in depois):
            falhas.append("apagar: o exame continua na lista")
        if not [x for x in depois if x.get("origem") == "radius"]:
            falhas.append("apagar: levou junto a fila do Radius")
        if radius.apagar(pasta, []).get("ok"):
            falhas.append("apagar: lista vazia nao pode dar ok")
    finally:
        shutil.rmtree(pasta, ignore_errors=True)



def pasta_de_downloads(falhas):
    """Com o Radius fechado: o que cai na pasta de downloads do navegador
    aparece — mas só o que tem cara de exame."""
    pasta = tempfile.mkdtemp(prefix="v2_radius2_")
    downloads = tempfile.mkdtemp(prefix="v2_downloads_")
    radius._ARQ_SAL = os.path.join(pasta, ".radius_sal_teste")
    radius._ARQ_APAGADOS = os.path.join(pasta, "apagados_teste.json")
    radius._CACHE.update(chave=None, arqs=None, pasta=None, t_arqs=0.0)
    try:
        # exame baixado pelo navegador: pasta com um .dcm dentro
        exame = os.path.join(downloads, "CICLANO SOUZA 555444333")
        os.makedirs(os.path.join(exame, "serie1"))
        with open(os.path.join(exame, "serie1", "IM0001.dcm"), "wb") as f:
            f.write(b"DICM" + b"0" * 1024)
        # lixo que mora na mesma pasta e NAO pode virar exame
        os.makedirs(os.path.join(downloads, "instalador do escritorio"))
        with open(os.path.join(downloads, "boleto.pdf"), "wb") as f:
            f.write(b"%PDF-1.4")
        with open(os.path.join(downloads, "planilha.zip"), "wb") as f:
            f.write(b"PK\x03\x04")
        fila = radius.ler_fila(pasta, [downloads])
        soltos = [x for x in fila if x.get("origem") == "pasta"]
        if len(soltos) != 1:
            falhas.append("downloads: esperava 1 exame, veio %d (%s)"
                          % (len(soltos), [x.get("iniciais") for x in soltos]))
            return
        if soltos[0]["iniciais"] != "C.S.":
            falhas.append("downloads: iniciais %r" % soltos[0]["iniciais"])
        texto = json.dumps(fila, ensure_ascii=False)
        for p in PROIBIDOS + ["boleto", "instalador", "IM0001"]:
            if p.lower() in texto.lower():
                falhas.append("downloads: a fila vazou %s" % p)
        # apagar um exame que está na pasta extra
        r = radius.apagar(pasta, [soltos[0]["id"]], {}, [downloads])
        if not r.get("ok") or r.get("apagados") != 1:
            falhas.append("downloads: apagar respondeu %r" % r)
        if os.path.isdir(exame):
            falhas.append("downloads: a pasta do exame continua no lugar")
        # a pasta observada é a do Radius + a de downloads, sem repetir
        lista = radius.pastas_observadas({"radius_pasta": pasta, "pastas_extras": [downloads, downloads]})
        if lista != [os.path.abspath(pasta), os.path.abspath(downloads)]:
            falhas.append("pastas observadas: %r" % lista)
    finally:
        shutil.rmtree(pasta, ignore_errors=True)
        shutil.rmtree(downloads, ignore_errors=True)


def main():
    falhas = []
    banco(falhas)
    ia(falhas)
    abrir_estudos(falhas)
    iniciais_e_soltos(falhas)
    pasta_de_downloads(falhas)
    for f in falhas:
        print("FALHOU", f)
    print("v2: tudo certo" if not falhas else "v2: %d falha(s)" % len(falhas))
    sys.exit(1 if falhas else 0)


if __name__ == "__main__":
    main()

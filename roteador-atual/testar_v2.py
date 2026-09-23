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
import time

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



def _dicom_falso(nome="FULANO BELTRANO DE TAL", data="20260923", hora="140512",
                 mod="CT", desc="TOMOGRAFIA DE TORAX", uid="1.2.840.99999.7"):
    """Bytes de um DICOM de mentira (explicit VR little endian), com imagem no fim."""
    import struct

    def elem(g, e, vr, val):
        b = val.encode("latin-1")
        if len(b) % 2:
            b += b" "
        return struct.pack("<HH", g, e) + vr + struct.pack("<H", len(b)) + b

    meta = (elem(0x0002, 0x0002, b"UI", "1.2.840.10008.5.1.4.1.1.2")
            + elem(0x0002, 0x0010, b"UI", "1.2.840.10008.1.2.1"))
    cab = (struct.pack("<HH", 0x0002, 0x0000) + b"UL" + struct.pack("<H", 4)
           + struct.pack("<I", len(meta)))
    corpo = (elem(0x0008, 0x0020, b"DA", data) + elem(0x0008, 0x0030, b"TM", hora)
             + elem(0x0008, 0x0060, b"CS", mod) + elem(0x0008, 0x1030, b"LO", desc)
             + elem(0x0010, 0x0010, b"PN", nome) + elem(0x0020, 0x000D, b"UI", uid))
    imagem = struct.pack("<HH", 0x7FE0, 0x0010) + b"OB" + b"\0\0" + struct.pack("<I", 8) + b"IMAGEM!!"
    return b"\0" * 128 + b"DICM" + cab + meta + corpo + imagem


def download_de_dicom(falhas):
    """O fluxo sem Radius: baixou um .zip com DICOM pelo navegador, ele entra na
    fila já com modalidade, exame e hora — lidos do cabeçalho, no computador."""
    import zipfile
    import dicom

    bruto = _dicom_falso()
    # 1) o leitor entende os três jeitos de o exame chegar
    pasta = tempfile.mkdtemp(prefix="v2_dcm_")
    downloads = tempfile.mkdtemp(prefix="v2_baixados_")
    radius._ARQ_SAL = os.path.join(pasta, ".radius_sal_teste")
    radius._ARQ_APAGADOS = os.path.join(pasta, "apagados_teste.json")
    radius._CACHE.update(chave=None, arqs=None, pasta=None, t_arqs=0.0)
    radius._CAB.clear()
    try:
        solto = os.path.join(downloads, "IM0001.dcm")
        with open(solto, "wb") as f:
            f.write(bruto)
        if dicom.do_arquivo(solto).get("modalidade") != "CT":
            falhas.append("dicom: cabeçalho do .dcm não foi lido")
        # 2) o caso do Bruno: zip com nome que não diz nada
        zipado = os.path.join(downloads, "20260923_143012.zip")
        with zipfile.ZipFile(zipado, "w") as z:
            z.writestr("DICOM/PA000001/ST000001/SE000001/IM000001", bruto)
        d = dicom.do_zip(zipado)
        if d.get("modalidade") != "CT" or d.get("iniciais") != "F.B.T.":
            falhas.append("dicom: zip sem extensão .dcm dentro não foi lido: %r" % d)
        os.remove(solto)
        # 3) a fila mostra o zip como exame de verdade
        fila = radius.ler_fila(pasta, [downloads])
        soltos = [x for x in fila if x.get("origem") == "pasta"]
        if len(soltos) != 1:
            falhas.append("download: esperava 1 exame, veio %d" % len(soltos))
            return
        x = soltos[0]
        if x["modalidade"] != "CT" or x["descricao"] != "TOMOGRAFIA DE TORAX":
            falhas.append("download: a linha não veio do cabeçalho: %r" % x)
        if x["entrou"] != "2026-09-23T14:05:12":
            falhas.append("download: hora do exame %r" % x["entrou"])
        if x["iniciais"] != "F.B.T." or not x.get("lido_do_dicom"):
            falhas.append("download: iniciais/marca %r" % x)
        texto = json.dumps(fila, ensure_ascii=False)
        for p in PROIBIDOS + ["IM000001", "PA000001"]:
            if p.lower() in texto.lower():
                falhas.append("download: a fila vazou %s" % p)
        # 4) apagar e baixar de novo: o exame volta para a lista
        radius.apagar(pasta, [x["id"]], {}, [downloads])
        if [y for y in radius.ler_fila(pasta, [downloads]) if y["id"] == x["id"]]:
            falhas.append("download: apagado continuou na lista")
        with zipfile.ZipFile(zipado, "w") as z:
            z.writestr("DICOM/IM000001", bruto)
        os.utime(zipado, (time.time() + 10, time.time() + 10))
        radius._CACHE.update(chave=None)
        radius._CAB.clear()
        if not [y for y in radius.ler_fila(pasta, [downloads]) if y["id"] == x["id"]]:
            falhas.append("download: baixado de novo, o exame devia voltar para a lista")
    finally:
        shutil.rmtree(pasta, ignore_errors=True)
        shutil.rmtree(downloads, ignore_errors=True)



def oficina_de_mascaras(falhas):
    """A aba Máscaras muda o banco de verdade: escolhe a máscara certa, valida a
    proposta, grava em mascaras_usuario e desfaz."""
    import oficina

    colado = ("RADIOGRAFIA DO JOELHO DIREITO\n"
              "TÉCNICA: incidências anteroposterior e perfil.\n"
              "ANÁLISE:\nEspaços articulares femorotibiais reduzidos.\n"
              "CONCLUSÃO:\nGonartrose.")
    esc = oficina.escolher(roteador.BANCO, "corrige essa máscara", colado, "", 8)
    if not esc:
        falhas.append("oficina: colando uma máscara de joelho, não achou nenhuma parecida")
        return
    if not any("joelho" in d["titulo"] for d in esc[:3]):
        falhas.append("oficina: a máscara certa não ficou entre as 3 primeiras: %s"
                      % [d["titulo"] for d in esc[:3]])
    alvo = next((d for d in esc if "joelho" in d["titulo"]), esc[0])

    # a IA responde em JSON; o validador aceita o que dá para aplicar e recusa o resto
    texto_novo = ("**RADIOGRAFIA DO JOELHO {lado}**\n\n**TÉCNICA:** incidências "
                  "anteroposterior e perfil.\n\n**ANÁLISE:**\nEspaços articulares "
                  "preservados.\n\n**CONCLUSÃO:**\nExame sem alterações.")
    bruto = json.dumps({"operacoes": [
        {"acao": "substituir", "titulo": alvo["titulo"], "texto": texto_novo, "porque": "padroniza"},
        {"acao": "substituir", "titulo": "nao/existe", "texto": "x" * 40, "porque": "-"},
        {"acao": "criar", "nome": "rx joelho com protese total", "modalidade": "rx",
         "regiao": "joelho", "gatilhos": ["raio x de joelho com protese"],
         "texto": "**RADIOGRAFIA DO JOELHO {lado}**\n\n**ANÁLISE:**\nPrótese total do "
                  "joelho, com componentes bem posicionados.", "porque": "faltava"},
        {"acao": "trocar_frase", "titulo": "todas", "de": "zzz nao existe", "para": "y", "porque": "-"},
    ]}, ensure_ascii=False)
    props, recusadas = oficina.validar(oficina._so_json("```json\n" + bruto + "\n```"), esc)
    if len(props) != 2:
        falhas.append("oficina: esperava 2 propostas boas, veio %d" % len(props))
        return
    if len(recusadas) != 2:
        falhas.append("oficina: as duas operações inventadas deviam ser recusadas (%d)" % len(recusadas))

    # aplicar de verdade, em pastas de teste
    usuario = tempfile.mkdtemp(prefix="v2_masc_usuario_")
    copias = tempfile.mkdtemp(prefix="v2_masc_copias_")
    guarda = (oficina.PASTA_USUARIO, oficina.PASTA_COPIAS)
    oficina.PASTA_USUARIO, oficina.PASTA_COPIAS = usuario, copias
    refeita = {"n": 0}

    def refazer_falso():
        refeita["n"] += 1
        return True, "base refeita (teste)"

    try:
        r = oficina.aplicar(props, None, refazer_falso)
        if not r.get("ok") or r.get("aplicadas") != 2:
            falhas.append("oficina: aplicar respondeu %r" % {k: r[k] for k in ("ok", "aplicadas", "erros")})
            return
        if refeita["n"] != 1:
            falhas.append("oficina: a base não foi refeita depois de gravar")
        escritos = []
        for raiz, _d, arqs in os.walk(usuario):
            escritos += [os.path.join(raiz, a) for a in arqs if a.endswith(".txt")]
        if len(escritos) != 2:
            falhas.append("oficina: esperava 2 arquivos gravados, vieram %d" % len(escritos))
            return
        conteudo = open(escritos[0], encoding="utf-8").read()
        if not conteudo.startswith("# gatilhos:"):
            falhas.append("oficina: arquivo gravado sem o cabeçalho de gatilhos")
        if "categoria: usuario" not in conteudo:
            falhas.append("oficina: arquivo gravado sem a marca de máscara do usuário")
        # a máscara do Rotrix não pode ter sido tocada
        original = oficina.caminho_da_mascara(alvo["titulo"])
        if original and os.path.exists(original):
            if "oficina " in open(original, encoding="utf-8").read():
                falhas.append("oficina: escreveu por cima da máscara original do Rotrix")
        # desfazer apaga o que foi escrito
        d = oficina.desfazer(r["desfazer"], None, refazer_falso)
        if not d.get("ok") or d.get("apagados") != 2:
            falhas.append("oficina: desfazer respondeu %r" % d)
        sobrou = [a for raiz, _x, arqs in os.walk(usuario) for a in arqs if a.endswith(".txt")]
        if sobrou:
            falhas.append("oficina: depois de desfazer sobrou %s" % sobrou)
        if oficina.aplicar([], None, refazer_falso).get("ok"):
            falhas.append("oficina: aplicar sem proposta não pode dar ok")
    finally:
        oficina.PASTA_USUARIO, oficina.PASTA_COPIAS = guarda
        shutil.rmtree(usuario, ignore_errors=True)
        shutil.rmtree(copias, ignore_errors=True)


def adendos(falhas):
    """Aba Adendos: as recusas e, sobretudo, a triagem de identificador.

    O laudo assinado é colado inteiro nessa aba. Se vier com CPF, prontuário ou
    "Paciente: Fulano", nada pode sair do computador."""
    if roteador.adendo("", "acrescenta um achado").get("motivo") != "laudo_vazio":
        falhas.append("adendo: laudo vazio deveria dizer laudo_vazio")
    if roteador.adendo("TC de tórax normal.", "  ").get("motivo") != "pedido_vazio":
        falhas.append("adendo: pedido vazio deveria dizer pedido_vazio")

    # cabeçalho de paciente: sai fora antes de qualquer envio
    com_cabecalho = ("Paciente: FULANO BELTRANO DE TAL\nCPF 123.456.789-00\n\n"
                     "TC DE TÓRAX\nExame dentro dos limites da normalidade.")
    import importar_usuario
    corpo = importar_usuario.tirar_cabecalho_paciente(com_cabecalho) or ""
    for p in ("FULANO", "BELTRANO", "123.456.789"):
        if p in corpo:
            falhas.append("adendo: o cabeçalho de paciente sobreviveu (%r)" % p)

    # identificador no meio do laudo (não dá para tirar): tem que barrar
    sujo = ("TC DE TÓRAX\nProntuário 987654321.\n"
            "Exame dentro dos limites da normalidade.")
    r = roteador.adendo(sujo, "acrescenta um nódulo de 6 mm no lobo inferior esquerdo")
    if r.get("ok"):
        falhas.append("adendo: laudo com identificador não pode ser aceito")
    if r.get("motivo") != "tem_identificador":
        falhas.append("adendo: identificador passou pela triagem (%r)" % r.get("motivo"))
    if not r.get("achados"):
        falhas.append("adendo: recusou sem dizer o que achou")
    # a resposta da recusa não pode devolver o conteúdo do laudo para a tela
    bruto = json.dumps(r, ensure_ascii=False).upper()
    for p in PROIBIDOS:
        if p.upper() in bruto:
            falhas.append("adendo: a recusa devolveu %r" % p)

    # limpo: sem chave/sem internet tem que responder, não levantar exceção
    limpo = "TC DE TÓRAX\n\nExame dentro dos limites da normalidade."
    r = roteador.adendo(limpo, "acrescenta um nódulo de 6 mm no lobo inferior esquerdo",
                        "achado_adicional")
    if r.get("ok"):
        falhas.append("adendo: sem chave não pode dar ok")
    if not r.get("motivo"):
        falhas.append("adendo: falhou sem dizer o motivo")
    if r.get("motivo") == "tem_identificador":
        falhas.append("adendo: laudo limpo foi barrado como identificável")
    # tipo desconhecido não pode quebrar: cai no livre
    if not roteador.adendo(limpo, "refuta o pedido", "coisa_que_nao_existe").get("motivo"):
        falhas.append("adendo: tipo desconhecido deveria cair no livre e responder")


def main():
    falhas = []
    banco(falhas)
    ia(falhas)
    abrir_estudos(falhas)
    iniciais_e_soltos(falhas)
    pasta_de_downloads(falhas)
    download_de_dicom(falhas)
    oficina_de_mascaras(falhas)
    adendos(falhas)
    for f in falhas:
        print("FALHOU", f)
    print("v2: tudo certo" if not falhas else "v2: %d falha(s)" % len(falhas))
    sys.exit(1 if falhas else 0)


if __name__ == "__main__":
    main()

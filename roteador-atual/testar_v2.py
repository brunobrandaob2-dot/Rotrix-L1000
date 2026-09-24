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
import re
import shutil
import sys
import tempfile
import time

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import radius  # noqa: E402

AQUI_APP = os.path.dirname(os.path.abspath(__file__))
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
        # a fila segue a ORDEM DE DOWNLOAD: "entrou" é quando o arquivo chegou
        # aqui, não a hora da aquisição. A do exame vai em "quando_exame".
        if x.get("quando_exame") != "2026-09-23T14:05:12":
            falhas.append("download: hora do exame %r" % x.get("quando_exame"))
        if x["entrou"] == "2026-09-23T14:05:12":
            falhas.append("download: 'entrou' voltou a ser a hora do exame")
        if not re.match(r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d$", x["entrou"] or ""):
            falhas.append("download: 'entrou' fora do formato %r" % x["entrou"])
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
        # a recompilação aqui é simulada: a conferência no banco tem o seu
        # próprio teste, com construir_base de verdade
        r = oficina.aplicar(props, None, refazer_falso, conferir_no_banco=False)
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
        if oficina.aplicar([], None, refazer_falso, conferir_no_banco=False).get("ok"):
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


def ordem_da_mascara_rx(falhas):
    """A máscara normal de RX sai na ordem do arquivo, mesmo com lacuna na linha.

    O motor de RX sobe para o topo da ANÁLISE toda frase que ele lê como
    alteração. Uma linha da própria máscara com lacuna — a tabela de medidas da
    escanometria, as medidas da panorâmica — deixava de casar com o arquivo cru
    e era promovida, embaralhando o laudo. Isto trava esse comportamento."""
    casos = {
        "escanometria de membros inferiores": [
            "Os seguintes aspectos foram observados.",
            "Medidas em cm:",
            "DIREITO",
            "FÊMUR",
            "TÍBIA",
            "MEMBRO INFERIOR",
            "Estruturas ósseas avaliadas",
        ],
        "radiografia digital panoramica da coluna vertebral": [
            "Alinhamento preservado",
            "Índice de Risser",
            "Báscula ilíaca",
            "Balanço sagital",
            "Ângulo da cifose torácica",
            "Ângulo de Ferguson",
            "Ângulo da lordose lombar",
            "Corpos vertebrais",
            "Espaços discais",
            "Elementos posteriores",
        ],
        "radiografia digital panoramica dos membros inferiores": [
            "Eixo mecânico do membro inferior direito",
            "Eixo mecânico do membro inferior esquerdo",
            "Ângulo anatômico femorotibial direito",
            "Ângulo anatômico femorotibial esquerdo",
            "Comprimento femorotibial direito",
            "Comprimento femorotibial esquerdo",
            "O membro inferior",
        ],
    }
    for ditado, esperado in casos.items():
        saida, origem = roteador.rotear(ditado)
        if not origem.startswith("mascara:"):
            falhas.append("ordem rx: %r não caiu na máscara (%s)" % (ditado, origem))
            continue
        pos, anterior = -1, None
        for pedaco in esperado:
            i = saida.find(pedaco)
            if i < 0:
                falhas.append("ordem rx: %r perdeu %r" % (ditado, pedaco))
                break
            if i < pos:
                falhas.append("ordem rx: %r trocou %r de lugar (veio antes de %r)"
                              % (ditado, pedaco, anterior))
                break
            pos, anterior = i, pedaco


def idade_ossea_calc(falhas):
    """Idade óssea: aritmética local, conferida contra o formulário dele.

    O caso de referência é o print que ele mandou — 15/04/2025, exame em
    24/09/2026, masculino, idade óssea observada de 1 ano e 5 meses. O
    formulário dele devolve DP 3,26 meses, faixa de 10 a 24 meses, Z 0,00 e
    percentil 50%. Se algum destes quatro mudar, a tabela ou a interpolação
    foi mexida."""
    import idade_ossea as io
    r = io.laudo("15/04/2025", "24/09/2026", "Masculino", 1, 5)
    for campo, esperado in (("cronologica_meses", 17), ("dp_meses", 3.26),
                            ("limite_inferior_meses", 10), ("limite_superior_meses", 24),
                            ("z", 0.0), ("percentil", 50.0)):
        if r[campo] != esperado:
            falhas.append("idade óssea: %s deu %r, esperado %r" % (campo, r[campo], esperado))
    if "12 meses (24 meses)" in r["texto"]:
        falhas.append("idade óssea: 24 meses saiu como '1 ano e 12 meses'")
    if "2 anos (24 meses)" not in r["texto"]:
        falhas.append("idade óssea: o limite superior não saiu por extenso")

    # o DP é interpolado: no ponto da tabela tem que bater exato
    if round(io.desvio_padrao(18, "masculino"), 2) != 3.52:
        falhas.append("idade óssea: DP masculino em 18 meses fora da tabela")
    if round(io.desvio_padrao(120, "feminino"), 2) != 11.73:
        falhas.append("idade óssea: DP feminino em 10 anos fora da tabela")
    # fora da tabela: não extrapola, segura na ponta
    if io.desvio_padrao(1, "masculino") != io.desvio_padrao(3, "masculino"):
        falhas.append("idade óssea: abaixo do primeiro ponto deveria repetir a ponta")
    if io.desvio_padrao(400, "feminino") != io.desvio_padrao(204, "feminino"):
        falhas.append("idade óssea: acima do último ponto deveria repetir a ponta")

    # as três faixas
    atrasada = io.laudo("15/04/2015", "24/09/2026", "Masculino", 7, 0)
    if io.classificar(atrasada) != "atrasada":
        falhas.append("idade óssea: 7 anos aos 11 deveria ser atrasada")
    avancada = io.laudo("15/04/2015", "24/09/2026", "Masculino", 14, 0)
    if io.classificar(avancada) != "avancada":
        falhas.append("idade óssea: 14 anos aos 11 deveria ser avançada")
    # menina e menino na mesma idade não têm o mesmo DP
    if io.desvio_padrao(60, "feminino") == io.desvio_padrao(60, "masculino"):
        falhas.append("idade óssea: o DP não está separado por sexo")

    # nada de rede: o cálculo é local
    aqui = os.path.dirname(os.path.abspath(__file__))
    fonte = open(os.path.join(aqui, "idade_ossea.py"), encoding="utf-8").read()
    for proibido in ("import nuvem", "import requests", "import urllib", "import http",
                     "import socket", "urlopen", "requests.post"):
        if proibido in fonte:
            falhas.append("idade óssea: o módulo não pode sair da máquina (%s)" % proibido)


def exames_de_medida(falhas):
    """Escanometria, panorâmica de MMII e da coluna: a conta é local.

    A IA só devolve números lidos do print. Se ela escrevesse o laudo, cada
    exame sairia com uma redação e a aritmética dependeria do modelo."""
    import medidas

    # arredondamento em quartos, na LEITURA (regra da habilidade)
    for bruto, esperado in ((92.1, 92.0), (48.85, 48.75), (13.2, 13.25),
                            (13.4, 13.5), (13.6, 13.5), (13.9, 14.0)):
        if medidas.quarto(bruto) != esperado:
            falhas.append("medidas: quarto(%s) deu %s, esperado %s"
                          % (bruto, medidas.quarto(bruto), esperado))

    leituras = {"quadril_d": 92.1, "quadril_e": 92.0, "joelho_d": 48.85,
                "joelho_e": 49.0, "tornozelo_d": 13.0, "tornozelo_e": 13.2}
    r = medidas.montar("escanometria", leituras)
    if not r.get("ok"):
        falhas.append("medidas: escanometria não montou (%r)" % r.get("motivo"))
        return
    v = r["valores"]
    # subtração, não leitura direta
    for k, esperado in (("femur_d", 43.25), ("femur_e", 43.0),
                        ("tibia_d", 35.75), ("tibia_e", 35.75),
                        ("mi_d", 79.0), ("mi_e", 78.75)):
        if abs(v[k] - esperado) > 1e-9:
            falhas.append("medidas: %s deu %s, esperado %s" % (k, v[k], esperado))
    if v["lado_maior"] != "direito" or abs(v["dismetria"] - 0.25) > 1e-9:
        falhas.append("medidas: dismetria errada (%r, %r)" % (v["lado_maior"], v["dismetria"]))
    # todo derivado cai na grade do quarto de centímetro
    for k in ("femur_d", "femur_e", "tibia_d", "tibia_e", "mi_d", "mi_e", "dismetria"):
        if abs(v[k] * 4 - round(v[k] * 4)) > 1e-9:
            falhas.append("medidas: %s saiu fora da grade de quartos (%s)" % (k, v[k]))

    # a tabela tem que continuar nas colunas da habilidade
    for linha in r["texto"].split("\n"):
        m = medidas._LINHA_TABELA.match(linha)
        if m:
            if linha.index(m.group(2)) != medidas.COL_1:
                falhas.append("medidas: coluna DIREITO fora do lugar (%r)" % linha)
            if linha.index(m.group(3), medidas.COL_1 + 1) != medidas.COL_2:
                falhas.append("medidas: coluna ESQUERDO fora do lugar (%r)" % linha)
    if "___" in r["texto"]:
        falhas.append("medidas: sobrou lacuna vazia no laudo preenchido")
    # o texto é o da máscara, não escrito na hora
    for pedaco in ("Os seguintes aspectos foram observados.", "Medidas em cm:",
                   "              DIREITO    ESQUERDO", "Estruturas ósseas avaliadas"):
        if pedaco not in r["texto"]:
            falhas.append("medidas: o laudo perdeu %r" % pedaco)

    # nível ausente: não inventa, diz o que falta
    faltando = dict(leituras); faltando.pop("tornozelo_e")
    r2 = medidas.montar("escanometria", faltando)
    if r2.get("ok") or r2.get("motivo") != "nivel_ausente":
        falhas.append("medidas: sem um nível deveria recusar, não estimar")
    if "tornozelo_e" not in (r2.get("faltando") or []):
        falhas.append("medidas: não disse qual nível faltou")

    # sanidade: número fora de ordem de grandeza vira aviso, não laudo calado
    torto = dict(leituras, joelho_d=80.0)
    r3 = medidas.montar("escanometria", torto)
    if not any("sanidade" in a for a in r3.get("avisos", [])):
        falhas.append("medidas: fêmur absurdo passou sem aviso de sanidade")

    # a borda de 1,00 cm é a única que muda conduta
    borda = dict(leituras, tornozelo_e=13.95)
    r4 = medidas.montar("escanometria", borda)
    if not any("1,00 cm" in a for a in r4.get("avisos", [])):
        falhas.append("medidas: dismetria na borda de 1 cm sem ressalva")

    # panorâmica de MMII: a dismetria sai de conta, não do ditado
    r5 = medidas.montar("panoramica_mmii", {
        "relacao_d": "medial", "relacao_e": "medial", "desvio_d": "9", "desvio_e": "5",
        "geno_d": "varo", "geno_e": "varo", "aft_d": "5,4", "aft_e": "6,1",
        "comp_d": "78,4", "comp_e": "79,0"})
    if r5["valores"].get("lado_menor") != "direito":
        falhas.append("medidas: lado menor da panorâmica de MMII errado")
    if abs(r5["valores"]["dismetria"] - 0.6) > 0.001:
        falhas.append("medidas: dismetria da panorâmica de MMII errada")

    # panorâmica da coluna: preenche sem inventar campo que não veio
    r6 = medidas.montar("panoramica_coluna", {"cobb": "8", "risser": "V"})
    if "{cobb}" in r6["texto"] or "8" not in r6["texto"]:
        falhas.append("medidas: a coluna não preencheu o Cobb")
    if "{sva}" not in r6["texto"]:
        falhas.append("medidas: campo não informado deveria continuar lacuna")

    # o módulo não fala com a nuvem: quem fala é a rota da imagem
    fonte = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              "medidas.py"), encoding="utf-8").read()
    for proibido in ("import nuvem", "import requests", "import urllib", "urlopen"):
        if proibido in fonte:
            falhas.append("medidas: o módulo não pode sair da máquina (%s)" % proibido)


def oficina_grava_no_banco(falhas):
    """O teste que teria pego o defeito: máscara da oficina TEM que virar gatilho.

    A oficina grava sempre em dados/mascaras_usuario. Antes, com o
    `fonte_mascaras` no padrão ("rotrix") — que é o caso de quem nunca mexeu no
    ajuste —, essa pasta não era percorrida na compilação: o arquivo existia no
    disco e não existia no banco, e a oficina dizia "aplicado".

    Roda nas TRÊS fontes. Em qualquer uma, a máscara do usuário tem que estar
    no banco; a fonte decide só quem vence o gatilho repetido."""
    import subprocess
    pasta = os.path.join(AQUI_APP, "dados", "mascaras_usuario", "tc", "_regressao")
    arq = os.path.join(pasta, "m.txt")
    gatilho = "tomografia de regressao da oficina"
    os.makedirs(pasta, exist_ok=True)
    io.open(arq, "w", encoding="utf-8").write(
        "# gatilhos: %s\n"
        "# categoria: medicina_interna\n# modalidade: tc\n# regiao: _regressao\n"
        "# tipo_mascara: normal\n"
        "**TOMOGRAFIA DE REGRESSAO**\n\n"
        "**TÉCNICA:**  aquisição de teste.\n\n"
        "**INDICAÇÃO CLÍNICA:**  Em anexo.\n\n"
        "**ANÁLISE:**\nTeste:  máscara escrita pela oficina.\n\n"
        "**COMPARAÇÃO:**  estudos anteriores não disponíveis para análise comparativa.\n\n"
        "**CONCLUSÃO:**\nExame sem alterações significativas.\n" % gatilho)
    try:
        for fonte in ("rotrix", "minhas", "ambas"):
            fd, base = tempfile.mkstemp(suffix=".sqlite"); os.close(fd)
            env = dict(os.environ, LAUDO_BASE=base, LAUDO_CATALOGO=base + ".txt",
                       LAUDO_FONTE=fonte)
            r = subprocess.run([sys.executable, "construir_base.py"], cwd=AQUI_APP,
                               env=env, capture_output=True, text=True)
            if r.returncode != 0:
                falhas.append("oficina/regressão: construir_base falhou em fonte=%s" % fonte)
                continue
            b = roteador.Banco(base)
            achou = [it for it in b.itens
                     if it[0] == "mascara" and it[1] == roteador.normalizar(gatilho)]
            if not achou:
                falhas.append("oficina/regressão: com fonte=%s a máscara do usuário "
                              "não entrou no banco" % fonte)
            elif not achou[0][2].startswith("usuario/"):
                falhas.append("oficina/regressão: com fonte=%s o gatilho caiu em %s"
                              % (fonte, achou[0][2]))
            for x in (base, base + ".txt"):
                try: os.remove(x)
                except OSError: pass
    finally:
        shutil.rmtree(pasta, ignore_errors=True)

    # a armadilha do comando no começo do gatilho
    import oficina
    if not oficina.comando_no_comeco("mascara de joelho direito"):
        falhas.append("oficina: gatilho que começa com 'mascara' tem que ser recusado")
    if oficina.comando_no_comeco("raio x de joelho direito"):
        falhas.append("oficina: gatilho normal foi recusado à toa")
    if oficina.sem_a_palavra_de_comando("mascara de joelho direito") != "de joelho direito":
        falhas.append("oficina: a sugestão sem a palavra de comando saiu errada")

    # a conferência de ponta a ponta não pode dizer que confere o que não existe
    fantasma = oficina.conferir([{"arquivo": "mascaras_usuario/tc/nao_existe/x.txt"}])
    if fantasma[0].get("confere"):
        falhas.append("oficina: conferiu uma máscara que não existe")

    # a auditoria responde sem levantar
    a = oficina.auditar()
    for campo in ("fora_do_banco", "sem_gatilho", "gatilho_disputado", "comeca_com_comando"):
        if campo not in a:
            falhas.append("oficina: auditoria sem o campo %s" % campo)


def oficina_ponta_a_ponta(falhas):
    """O caminho de verdade: oficina grava -> base recompila -> gatilho acha.

    Sem recompilação simulada e sem pasta de mentira. É este teste que responde
    à queixa "mando gerar a máscara, ela diz que gravou, e o comando não acha"."""
    import subprocess, oficina
    conf = os.path.join(AQUI_APP, "config.json")
    guarda_conf = io.open(conf, encoding="utf-8").read()
    # _arquivo_do_usuario() passa a região pelo slug: "_e2e" vira "e2e"
    alvos = [os.path.join(oficina.PASTA_USUARIO, "rx", n) for n in ("_e2e", "e2e")]
    gatilho = "raio x de teste de ponta a ponta da oficina"

    def refazer_real():
        r = subprocess.run([sys.executable, "construir_base.py"], cwd=AQUI_APP,
                           capture_output=True, text=True)
        return r.returncode == 0, (r.stdout or r.stderr or "").strip().splitlines()[-1:]

    props = [{"acao": "criar", "nome": "teste ponta a ponta", "modalidade": "rx",
              "regiao": "_e2e", "gatilhos": [gatilho],
              "depois": "**RADIOGRAFIA DE TESTE**\n\n**TÉCNICA:**  incidência única.\n\n"
                        "**ANÁLISE:**\nMarca unica do teste de ponta a ponta."}]
    try:
        r = oficina.aplicar(props, roteador.BANCO, refazer_real)
        if not r.get("ok"):
            falhas.append("oficina e2e: aplicar não deu ok (%r)" % r.get("erros"))
        item = (r.get("itens") or [{}])[0]
        if not item.get("confere"):
            falhas.append("oficina e2e: gravou e o comando não acha (%s)" % item.get("porque"))
        if item.get("gatilho_testado") != gatilho:
            falhas.append("oficina e2e: testou outro gatilho (%r)" % item.get("gatilho_testado"))
        # e o comando realmente traz o texto novo
        texto, origem = roteador.rotear(gatilho)
        if "Marca unica do teste" not in texto:
            falhas.append("oficina e2e: o texto escrito não saiu no laudo (%s)" % origem)
        # a fonte sobe sozinha para "ambas": senão a edição fica escrita e não vale
        if r.get("fonte_mudou") not in ("", "ambas"):
            falhas.append("oficina e2e: fonte_mudou inesperado (%r)" % r.get("fonte_mudou"))
        import importar_usuario
        if importar_usuario.fonte_atual() == "rotrix":
            falhas.append("oficina e2e: depois de gravar, a fonte não podia seguir em rotrix")
        # a auditoria não pode acusar o que acabou de entrar certo
        a = oficina.auditar(roteador.BANCO)
        if any("_e2e" in x for x in a["fora_do_banco"]):
            falhas.append("oficina e2e: a auditoria disse que está fora do banco")
    finally:
        for a in alvos:
            shutil.rmtree(a, ignore_errors=True)
        io.open(conf, "w", encoding="utf-8").write(guarda_conf)
        subprocess.run([sys.executable, "construir_base.py"], cwd=AQUI_APP,
                       capture_output=True, text=True)
        try:
            roteador.BANCO.carregar()
        except Exception:
            pass


def rotas_novas(falhas):
    """As rotas que o app vai chamar: medidas, idade óssea e auditoria.

    Todas locais. Nenhuma delas pode mandar nada para fora, e nenhuma pode
    quebrar com entrada torta — o app manda o que o médico digitou."""
    c = roteador.medidas_campos()
    if not c.get("ok") or sorted(c["exames"]) != ["escanometria", "panoramica_coluna", "panoramica_mmii"]:
        falhas.append("rotas: /medidas/campos não trouxe os três exames (%r)" % c.get("exames"))
    for nome, conf in (c.get("exames") or {}).items():
        if not conf.get("mascara") or not conf.get("titulo"):
            falhas.append("rotas: o exame %s veio sem máscara ou título" % nome)

    r = roteador.medidas_exame("escanometria", {
        "quadril_d": 92.1, "quadril_e": 92.0, "joelho_d": 48.85,
        "joelho_e": 49.0, "tornozelo_d": 13.0, "tornozelo_e": 13.2})
    if not r.get("ok") or "EXAME RADIOLÓGICO DE ESCANOMETRIA" not in r.get("texto", ""):
        falhas.append("rotas: /medidas não montou a escanometria")
    if abs(r["valores"]["dismetria"] - 0.25) > 1e-9:
        falhas.append("rotas: a dismetria da rota saiu diferente da do módulo")

    # entradas tortas não podem levantar
    for ruim in ({}, {"exame": "coisa"}, {"exame": "escanometria", "valores": "texto"}):
        out = roteador.medidas_exame(ruim.get("exame") or "", ruim.get("valores") or {})
        if out.get("ok"):
            falhas.append("rotas: /medidas aceitou entrada inválida (%r)" % ruim)

    i = roteador.idade_ossea_laudo({"nascimento": "15/04/2025", "exame": "24/09/2026",
                                    "sexo": "Masculino", "anos": 1, "meses": 5})
    if not i.get("ok") or i.get("dp_meses") != 3.26 or i.get("classificacao") != "compativel":
        falhas.append("rotas: /idade_ossea saiu diferente do formulário dele (%r)" % i)
    if not isinstance(i.get("nascimento"), str):
        falhas.append("rotas: /idade_ossea devolveu data que não vira JSON")
    ruim = roteador.idade_ossea_laudo({"nascimento": "trinta e um", "exame": "24/09/2026"})
    if ruim.get("ok") or ruim.get("motivo") != "dados_invalidos":
        falhas.append("rotas: /idade_ossea aceitou data inválida")

    a = roteador.auditar_banco()
    for campo in ("fora_do_banco", "sem_gatilho", "gatilho_disputado", "comeca_com_comando"):
        if campo not in a:
            falhas.append("rotas: /mascaras/auditar sem o campo %s" % campo)

    # nada das três rotas pode vazar identificador para fora
    bruto = json.dumps([r, i, a], ensure_ascii=False, default=str).upper()
    for p in PROIBIDOS:
        if p.upper() in bruto:
            falhas.append("rotas: uma das rotas novas devolveu %r" % p)


def calculos_de_volume(falhas):
    """Volume por elipsoide: a conta é aqui, e a frase sai na forma dele.

    Multiplicar três números não se terceiriza para modelo de linguagem: o
    resultado tem que ser o mesmo toda vez."""
    import calculos as C

    # a fórmula, conferida na mão: 4,2 x 3,8 x 4,0 = 63,84; x 0,523 = 33,38832
    v = C.volume("4,2", "3,8", "4,0")
    if abs(v - 33.38832) > 0.0001:
        falhas.append("cálculos: elipsoide deu %r" % v)
    if C.FATOR != 0.523:
        falhas.append("cálculos: o fator do elipsoide mudou (%r)" % C.FATOR)
    # vírgula e ponto valem igual: ele digita com vírgula
    if C.volume("4,2", "3,8", "4,0") != C.volume(4.2, 3.8, 4.0):
        falhas.append("cálculos: vírgula e ponto deram resultados diferentes")
    # mm vira cm antes de multiplicar
    if abs(C.volume(42, 38, 40, em_mm=True) - C.volume(4.2, 3.8, 4.0)) > 1e-9:
        falhas.append("cálculos: a conversão de mm não bateu")

    # medida que não é número não pode virar volume
    for ruim in (("abc", 2, 3), (0, 2, 3), (-1, 2, 3), (None, 2, 3), ("", 2, 3)):
        if C.volume(*ruim) is not None:
            falhas.append("cálculos: aceitou medida inválida %r" % (ruim,))

    # densidade de PSA
    r = C.calcular("prostata", "4,2", "3,8", "4,0", psa="6,2")
    if not r.get("ok") or abs(r["densidade_psa"] - 0.186) > 0.001:
        falhas.append("cálculos: densidade de PSA deu %r" % r.get("densidade_psa"))
    if "Densidade de PSA" not in r["frase"] or "33,4" not in r["frase"]:
        falhas.append("cálculos: a frase da próstata saiu errada (%r)" % r["frase"])
    # sem PSA, não inventa densidade
    if "densidade_psa" in C.calcular("prostata", 4.2, 3.8, 4.0):
        falhas.append("cálculos: calculou densidade sem PSA")

    # comparação com o anterior: a ressalva do diâmetro é o que evita laudo errado
    r = C.calcular("lesao", 2.1, 1.8, 1.9, anterior=6.5)
    if abs(r["variacao_pct"] + 42.2) > 0.2:
        falhas.append("cálculos: variação de volume deu %r" % r.get("variacao_pct"))
    if "redução de 42,2%" not in r["frase"]:
        falhas.append("cálculos: a frase da comparação saiu errada (%r)" % r["frase"])
    # 20% de volume é ~6% de diâmetro: tem que avisar, senão vira "crescimento"
    quase = C.calcular("lesao", 2.1, 1.8, 1.9, anterior=3.4)
    if not any("erro de medida" in a for a in quase["avisos"]):
        falhas.append("cálculos: variação pequena passou sem a ressalva do diâmetro")
    grande = C.calcular("lesao", 3.0, 2.8, 2.9, anterior=3.4)
    if any("erro de medida" in a for a in grande["avisos"]):
        falhas.append("cálculos: variação grande não devia levar a ressalva")
    # sem anterior, nada de comparação inventada
    if "variacao_pct" in C.calcular("lesao", 2.1, 1.8, 1.9):
        falhas.append("cálculos: comparou sem exame anterior")

    # lado: só onde faz sentido, e com valor válido
    r = C.calcular("rim", 10.2, 4.8, 5.1, lado="esquerdo")
    if "Rim esquerdo" not in r["frase"]:
        falhas.append("cálculos: o lado não entrou na frase (%r)" % r["frase"])
    r = C.calcular("rim", 10.2, 4.8, 5.1, lado="dos fundos")
    if "Rim direito" not in r["frase"]:
        falhas.append("cálculos: lado inválido devia cair no padrão (%r)" % r["frase"])

    # órgão que não existe não pode virar frase
    ruim = C.calcular("figado_gordo", 1, 2, 3)
    if ruim.get("ok") or ruim.get("motivo") != "orgao_desconhecido":
        falhas.append("cálculos: aceitou órgão inexistente")

    # a rota responde e não quebra com entrada torta
    if not roteador.calcular_volume({"orgao": "baco", "l": 12, "ap": 5, "t": 6}).get("ok"):
        falhas.append("cálculos: a rota não calculou o baço")
    for ruim in ({}, {"orgao": "rim"}, {"orgao": "rim", "l": "x", "ap": "y", "t": "z"}):
        if roteador.calcular_volume(ruim).get("ok"):
            falhas.append("cálculos: a rota aceitou %r" % ruim)
    campos = C.campos()
    if not campos.get("ok") or len(campos["orgaos"]) < 8:
        falhas.append("cálculos: a lista de órgãos veio curta")

    # nada de rede neste módulo
    fonte = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              "calculos.py"), encoding="utf-8").read()
    for proibido in ("import nuvem", "import requests", "import urllib", "urlopen"):
        if proibido in fonte:
            falhas.append("cálculos: o módulo não pode sair da máquina (%s)" % proibido)


def main():
    falhas = []
    banco(falhas)
    ia(falhas)
    abrir_estudos(falhas)
    iniciais_e_soltos(falhas)
    pasta_de_downloads(falhas)
    download_de_dicom(falhas)
    oficina_de_mascaras(falhas)
    oficina_grava_no_banco(falhas)
    oficina_ponta_a_ponta(falhas)
    adendos(falhas)
    ordem_da_mascara_rx(falhas)
    idade_ossea_calc(falhas)
    exames_de_medida(falhas)
    rotas_novas(falhas)
    calculos_de_volume(falhas)
    for f in falhas:
        print("FALHOU", f)
    print("v2: tudo certo" if not falhas else "v2: %d falha(s)" % len(falhas))
    sys.exit(1 if falhas else 0)


if __name__ == "__main__":
    main()

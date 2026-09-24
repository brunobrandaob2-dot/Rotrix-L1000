# -*- coding: utf-8 -*-
"""Testes da fila do Radius com arquivos FALSOS (python testar_radius.py).
Confere que nome e número de acesso nunca saem da leitura nem do diagnóstico."""
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

PROIBIDOS = ["FULANO", "BELTRANO", "CICLANO", "SOUZA", "123456789", "987654321", "555444333",
             "1.2.840.99999", "SEGREDO", "estudo.zip", "111222333"]


def _estudo(nome, acesso, mod, desc, status, laudado, quando):
    return {"PatientName": nome, "AccessionNumber": acesso, "PatientBirthDate": "19500101",
            "Modality": mod, "StudyDescription": desc, "Status": status,
            "IsReported": laudado, "QueueEnteredAt": quando}


def montar(pasta):
    # formato 1: lista dentro de um objeto
    a = {"Version": 3, "Studies": [
        _estudo("FULANO BELTRANO DE TAL", "123456789", "CT", "TC DE TORAX", "Downloaded", False,
                "2026-09-21T10:00:00"),
        _estudo("CICLANO SOUZA", "987654321", "CR", "RX TORAX PA E PERFIL", "Opened", False,
                "2026-09-21T10:05:00"),
        _estudo("FULANO BELTRANO DE TAL", "555444333", "CR", "RX JOELHO FULANO", "Downloaded", True,
                "2026-09-21T09:00:00"),
    ]}
    # formato 2: dicionário com o número de acesso como chave
    b = {"123456789": {"Patient": {"Name": "FULANO BELTRANO"}, "Modality": "CT",
                       "StudyDescription": "TC DE TORAX", "Status": "Downloaded",
                       "IsReported": "true", "StudyInstanceUID": "1.2.840.99999.1"}}
    os.makedirs(os.path.join(pasta, "FULANO BELTRANO 123456789"))
    with open(os.path.join(pasta, "state.beta-v3.json"), "w", encoding="utf-8-sig") as f:
        json.dump(a, f)
    with open(os.path.join(pasta, "other-dicoms-state.json"), "w", encoding="utf-8") as f:
        json.dump(b, f)
    # pacote DICOM com nome de paciente: nunca pode ser aberto
    with open(os.path.join(pasta, "FULANO BELTRANO 123456789", "estudo.zip"), "wb") as f:
        f.write(b"PK\x03\x04 nao abrir")
    with open(os.path.join(pasta, "statistics.json"), "w", encoding="utf-8") as f:
        json.dump({"Total": 3, "PorModalidade": {"CT": 1, "CR": 2}}, f)


def _real(nome, acesso, mod, desc, status, laudado, quando, com_status=True):
    """Formato visto no Radius de verdade (radius_estrutura.txt de 22/09/2026)."""
    d = {"AccessionNumber": acesso, "CompletedAt": quando, "CreatedAt": quando,
         "FilePath": "C:\\Users\\x\\Downloads\\Radius Downloads\\%s %s\\estudo.zip" % (nome, acesso),
         "Id": "id-" + acesso, "IsReported": laudado, "Modality": mod, "PatientName": nome,
         "QueueEnteredAt": quando, "Sequence": 3, "SizeBytes": 123456789,
         "StudyDescription": desc, "StudyInstanceUID": "1.2.840.99999." + acesso}
    if com_status:
        d.update({"Status": status, "Token": "SEGREDO-" + acesso, "ComboGroupId": "g1", "Error": ""})
    return d


def montar_real(pasta):
    # estudo da vez: um objeto só, sem descrição, status Ready
    with open(os.path.join(pasta, "state.beta-v3.json"), "w", encoding="utf-8") as f:
        json.dump(_real("FULANO BELTRANO", "123456789", "CR", "", "Ready", False,
                        "2026-09-22T10:40:00.1234567-03:00"), f)
    # cópia de segurança: estudo ANTIGO, fica fora da fila
    with open(os.path.join(pasta, "state.beta-v3.backup.json"), "w", encoding="utf-8") as f:
        json.dump(_real("CICLANO SOUZA", "111222333", "CT", "", "Ready", False,
                        "2026-09-22T09:00:00.0000000-03:00"), f)
    # outros estudos: lista sem Status; o da vez aparece aqui com a descrição
    outros = [
        _real("FULANO BELTRANO", "123456789", "CR", "RX TORAX PA E PERFIL", "", False,
              "2026-09-22T10:40:00.1234567-03:00", com_status=False),
        _real("CICLANO SOUZA", "987654321", "CT", "TORAX E ABD TOTAL", "", False,
              "2026-09-22T10:10:00.0000000-03:00", com_status=False),
        _real("BELTRANO SOUZA", "555444333", "CT", "e+2 Angio AABD VENOSA", "", True,
              "2026-09-22T08:10:00.0000000-03:00", com_status=False),
    ]
    with open(os.path.join(pasta, "other-dicoms-state.json"), "w", encoding="utf-8") as f:
        json.dump(outros, f)
    stats = [{"Key": "k%d" % i, "Modality": "CT" if i % 2 else "CR", "QueueEnteredAt": "2026-09-2%dT10:00:00" % (i % 3),
              "RecordedAt": "2026-09-22T10:00:00", "Source": "Radius", "StudyInstanceUID": "1.2.840.99999.%d" % i}
             for i in range(3)]
    with open(os.path.join(pasta, "statistics.json"), "w", encoding="utf-8") as f:
        json.dump(stats, f)


def cenario_real(falhas):
    pasta = tempfile.mkdtemp(prefix="radius_real_")
    try:
        montar_real(pasta)
        fila = radius.ler_fila(pasta)
        txt = json.dumps(fila, ensure_ascii=False)
        diag = radius.diagnostico(pasta)
        for p in PROIBIDOS:
            if p.lower() in txt.lower():
                falhas.append("real: fila vazou " + p)
            if p.lower() in diag.lower():
                falhas.append("real: diagnóstico vazou " + p)
        if len(fila) != 3:
            falhas.append("real: esperava 3 estudos (cópia de segurança fora), veio %d" % len(fila))
        at = radius.atual(fila)
        if not at or at["modalidade"] != "CR":
            falhas.append("real: estudo da vez errado: %s" % at)
        elif at["descricao"] != "RX TORAX PA E PERFIL":
            falhas.append("real: descrição do estudo da vez não veio do outro arquivo: %r" % at["descricao"])
        elif radius.cabecalho(at) != "raio x de torax pa e perfil":
            falhas.append("real: cabeçalho %r" % radius.cabecalho(at))
        elif at["entrou"] != "2026-09-22T10:40:00":
            falhas.append("real: hora de entrada %r" % at["entrou"])
        for trecho in ("[cópia de segurança", "estudo da vez: CR", "registros: 3", "Source: Radius: 3",
                       "em mais de um arquivo: 1"):
            if trecho not in diag:
                falhas.append("real: diagnóstico sem %r" % trecho)
        # estudo da vez laudado: nenhum aberto
        with open(os.path.join(pasta, "state.beta-v3.json"), "w", encoding="utf-8") as f:
            json.dump(_real("FULANO BELTRANO", "123456789", "CR", "", "Ready", True,
                            "2026-09-22T10:40:00.1234567-03:00"), f)
        os.utime(os.path.join(pasta, "state.beta-v3.json"), (time.time() + 5, time.time() + 5))
        if radius.atual(radius.ler_fila(pasta)) is not None:
            falhas.append("real: estudo laudado continuou como o da vez")
    finally:
        shutil.rmtree(pasta, ignore_errors=True)
    # descrições do Radius -> cabeçalho
    casos = [({"modalidade": "CT", "descricao": "TORAX E ABD TOTAL"}, "tomografia de torax e abdome total"),
             ({"modalidade": "CT", "descricao": "e+2 Angio AABD VENOSA"}, "angiotomografia de abdome venosa"),
             ({"modalidade": "CR", "descricao": "RADIOGRAFIA DE CAVUM (LATERAL+HIRTZ)"},
              "raio x de cavum lateral hirtz"),
             ({"modalidade": "CR", "descricao": ""}, ""),
             ({"modalidade": "CT", "descricao": "Tc Cranio"}, "tomografia de cranio")]
    for item, esperado in casos:
        if radius.cabecalho(item) != esperado:
            falhas.append("cabeçalho de %r: %r" % (item["descricao"], radius.cabecalho(item)))



def comando_do_radiant(falhas):
    """Dois exames marcados têm que abrir na MESMA janela do RadiAnt.

    O manual do RadiAnt: `-f` recebe vários ARQUIVOS de uma vez, `-d` recebe
    várias PASTAS. Repetir `-f` a cada caminho — e mandar pasta como arquivo —
    era o que fazia os exames marcados abrirem separados."""
    import tempfile, os as _os
    d = tempfile.mkdtemp()
    pa = _os.path.join(d, "a"); _os.makedirs(pa)
    pb = _os.path.join(d, "b"); _os.makedirs(pb)
    fa = _os.path.join(d, "c.dcm"); open(fa, "wb").write(b"x")
    exe = "RadiAntViewer.exe"

    args = radius.montar_comando(exe, [pa, pb, fa])
    if args.count("-f") != 1 or args.count("-d") != 1:
        falhas.append("radiant: tem que ser um -d e um -f só (%r)" % args)
    if args.index("-d") > args.index("-f"):
        falhas.append("radiant: as pastas vêm antes dos arquivos")
    for pasta in (pa, pb):
        i = args.index(pasta)
        if args[i - 1] not in ("-d", pa, pb):
            falhas.append("radiant: pasta %r não entrou depois do -d" % pasta)
    if args[args.index(fa) - 1] != "-f":
        falhas.append("radiant: arquivo não entrou depois do -f")
    if args[1] != "-cl":
        falhas.append("radiant: sem -cl o exame cai numa janela velha")

    # uma chamada só: nada de abrir o exe duas vezes
    if sum(1 for a in args if a.endswith(".exe")) != 1:
        falhas.append("radiant: mais de uma chamada do executável")

    # só pastas, só arquivos: não sobra flag vazia
    so_pastas = radius.montar_comando(exe, [pa, pb], fechar_outras=False)
    if "-f" in so_pastas:
        falhas.append("radiant: -f sozinho sem nenhum arquivo")
    if so_pastas[0] != exe or so_pastas[1] != "-d":
        falhas.append("radiant: fechar_outras=False deveria tirar o -cl")
    so_arq = radius.montar_comando(exe, [fa])
    if "-d" in so_arq:
        falhas.append("radiant: -d sozinho sem nenhuma pasta")
    if "-b" in so_arq:
        falhas.append("radiant: -b não deveria entrar sem pasta")
    if "-b" not in radius.montar_comando(exe, [pa], arvore=True):
        falhas.append("radiant: arvore=True deveria pôr o -b")


def ordem_de_download(falhas):
    """A fila segue a ordem de DOWNLOAD, não a hora do exame no DICOM.

    O caso que ele descreveu: exame antigo baixado agora tem que aparecer
    DEPOIS de um exame recente baixado antes. Antes, "entrou" vinha do
    cabeçalho DICOM e a fila saía na ordem da aquisição."""
    import tempfile, os as _os, time as _time
    pasta = tempfile.mkdtemp(prefix="radius_ordem_")
    try:
        # três exames, criados em ordem conhecida; o do meio tem data de exame
        # muito antiga, como um estudo de comparação baixado hoje
        nomes = ["exame_recente", "exame_antigo_baixado_depois", "ultimo"]
        for i, nome in enumerate(nomes):
            d = _os.path.join(pasta, nome)
            _os.makedirs(d)
            with open(_os.path.join(d, "IM0001.dcm"), "wb") as f:
                f.write(b"DICM" + b"\0" * 64)
            # relógio do sistema de arquivos anda para frente a cada um
            quando = _time.time() - (len(nomes) - i) * 3600
            _os.utime(d, (quando, quando))

        soltos = radius.soltos(pasta)
        if len(soltos) != 3:
            falhas.append("ordem: esperava 3 exames soltos, vieram %d" % len(soltos))
            return
        ordem = [x["entrou"] for x in sorted(soltos, key=lambda x: x["entrou"])]
        if ordem != sorted(ordem):
            falhas.append("ordem: a fila não saiu em ordem crescente de chegada")
        # nenhum "entrou" pode ter vindo do cabeçalho do exame
        for x in soltos:
            if "quando_exame" not in x:
                falhas.append("ordem: a hora do exame precisa ir num campo à parte")
                break
        # a hora de chegada nunca é anterior à criação do arquivo
        for x in soltos:
            if not x["entrou"] or len(x["entrou"]) < 19:
                falhas.append("ordem: 'entrou' fora do formato (%r)" % x["entrou"])

        # ZIP extraído: o mtime vem de dentro do pacote, lá atrás. A chegada
        # tem que ser a mais recente das duas datas, não o mtime cru.
        velho = _os.path.join(pasta, "exame_recente")
        antigo = _time.time() - 400 * 24 * 3600
        _os.utime(velho, (antigo, antigo))
        st = _os.stat(velho)
        if radius._baixado_em(velho, st) < st.st_mtime:
            falhas.append("ordem: a chegada não pode ser anterior ao mtime")
    finally:
        shutil.rmtree(pasta, ignore_errors=True)

def main():
    falhas = []
    pasta = tempfile.mkdtemp(prefix="radius_teste_")
    # o teste não deixa segredo na pasta do roteador (o instalador leva a pasta)
    radius._ARQ_SAL = os.path.join(pasta, ".radius_sal_teste")
    try:
        montar(pasta)
        arqs = [os.path.basename(a) for a in radius.achar_arquivos(pasta)]
        if sorted(arqs) != ["other-dicoms-state.json", "state.beta-v3.json", "statistics.json"]:
            falhas.append("arquivos de estado: %s" % arqs)
        fila = radius.ler_fila(pasta)
        txt_fila = json.dumps(fila, ensure_ascii=False)
        diag = radius.diagnostico(pasta)
        for p in PROIBIDOS:
            if p.lower() in txt_fila.lower():
                falhas.append("fila vazou: " + p)
            if p.lower() in diag.lower():
                falhas.append("diagnóstico vazou: " + p)
        if len(fila) != 4:
            falhas.append("esperava 4 estudos, veio %d" % len(fila))
        descr = sorted(x["descricao"] for x in fila)
        if "RX JOELHO •••" not in descr:
            falhas.append("nome dentro da descrição não foi apagado: %s" % descr)
        at = radius.atual(fila)
        if not at or at["descricao"] != "RX TORAX PA E PERFIL":
            falhas.append("estudo aberto errado: %s" % at)
        if radius.cabecalho(at) != "raio x de torax pa e perfil":
            falhas.append("cabeçalho: %r" % radius.cabecalho(at))
        if radius.cabecalho({"modalidade": "CT", "descricao": "TC DE TORAX"}) != "tomografia de torax":
            falhas.append("cabeçalho TC")
        if "{*}" not in diag:
            falhas.append("chave com número de acesso deveria virar {*} no diagnóstico")
        if "estudos reconhecidos: 3" not in diag or "estudos reconhecidos: 1" not in diag:
            falhas.append("contagem de estudos no diagnóstico")
        # a fila relida sem mudança vem do cache e igual
        if radius.ler_fila(pasta) != fila:
            falhas.append("cache mudou a fila")
        cenario_real(falhas)
        comando_do_radiant(falhas)
        ordem_de_download(falhas)
    finally:
        shutil.rmtree(pasta, ignore_errors=True)
    # pasta que não existe: fila vazia, sem erro
    if radius.ler_fila(os.path.join(pasta, "nao_existe")) != []:
        falhas.append("pasta inexistente")
    for f in falhas:
        print("FALHOU", f)
    print("radius: tudo certo" if not falhas else "radius: %d falha(s)" % len(falhas))
    sys.exit(1 if falhas else 0)


if __name__ == "__main__":
    main()

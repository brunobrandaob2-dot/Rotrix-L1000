# -*- coding: utf-8 -*-
"""Testes da fila do Radius com arquivos FALSOS (python testar_radius.py).
Confere que nome e número de acesso nunca saem da leitura nem do diagnóstico."""
import io
import json
import os
import shutil
import sys
import tempfile

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import radius  # noqa: E402

PROIBIDOS = ["FULANO", "BELTRANO", "CICLANO", "SOUZA", "123456789", "987654321", "555444333",
             "1.2.840.99999"]


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

# -*- coding: utf-8 -*-
"""Testes do modo estação e do perfil (python testar_estacao.py).

Estação: o exame da vez, o "próximo exame" e o perfil automático usando o
exame escolhido. Perfil: exportar e importar sem levar chave nem laudo."""
import io
import json
import os
import shutil
import sys
import tempfile
import zipfile

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import roteador as r  # noqa: E402
import radius  # noqa: E402
import perfil  # noqa: E402


def _estudo(nome, acesso, mod, desc, laudado, quando, status=""):
    d = {"AccessionNumber": acesso, "PatientName": nome, "Modality": mod, "StudyDescription": desc,
         "IsReported": laudado, "QueueEnteredAt": quando, "StudyInstanceUID": "1.2.840.9." + acesso}
    if status:
        d["Status"] = status
    return d


def montar_radius(pasta):
    with open(os.path.join(pasta, "state.beta-v3.json"), "w", encoding="utf-8") as f:
        json.dump(_estudo("FULANO", "111", "CR", "", False, "2026-09-22T10:40:00", "Ready"), f)
    outros = [_estudo("FULANO", "111", "CR", "RX TORAX PA E PERFIL", False, "2026-09-22T10:40:00"),
              _estudo("CICLANO", "222", "CR", "RX JOELHO D", False, "2026-09-22T10:50:00"),
              _estudo("BELTRANO", "333", "CT", "TC DE CRANIO", False, "2026-09-22T11:00:00"),
              _estudo("SICRANO", "444", "CR", "RX TORAX", True, "2026-09-22T09:00:00")]
    with open(os.path.join(pasta, "other-dicoms-state.json"), "w", encoding="utf-8") as f:
        json.dump(outros, f)


def cenario_estacao(falhas):
    pasta = tempfile.mkdtemp(prefix="estacao_")
    montar_radius(pasta)
    radius._ARQ_SAL = os.path.join(pasta, ".sal")
    r._ESTACAO_ARQ = os.path.join(pasta, "estacao.json")
    cfg_real = r._config
    r._config = lambda: {"radius_pasta": pasta, "perfil_automatico": True}
    try:
        fila = r.fila_radius()
        if len(fila["itens"]) != 4:
            falhas.append("estação: esperava 4 estudos, veio %d" % len(fila["itens"]))
        vez = next((x for x in fila["itens"] if x["id"] == fila["vez"]), None)
        if not vez or vez["descricao"] != "RX TORAX PA E PERFIL":
            falhas.append("estação: exame da vez errado: %s" % (vez and vez["descricao"]))
        # o perfil automático usa o exame da vez
        t, o = r.rotear("opacidade na base direita")
        if "RADIOGRAFIA DO TÓRAX" not in t or "Opacidade na base direita." not in t:
            falhas.append("estação: perfil automático não usou o exame da vez: %r" % t[:80])
        # próximo exame: o da vez fica feito e vem o seguinte
        p = r.estacao_proximo()
        if not p["ok"] or not p["item"] or p["item"]["descricao"] != "RX JOELHO D":
            falhas.append("estação: próximo exame errado: %s" % (p.get("item") or {}).get("descricao"))
        fila = r.fila_radius()
        if fila["vez"] != p["item"]["id"]:
            falhas.append("estação: o exame da vez não seguiu o próximo")
        if not next(x["feito"] for x in fila["itens"] if x["descricao"] == "RX TORAX PA E PERFIL"):
            falhas.append("estação: o exame anterior não ficou marcado como feito")
        t, o = r.rotear("derrame articular")
        if "JOELHO" not in t:
            falhas.append("estação: o ditado seguinte não usou o joelho: %r" % t[:80])
        # escolher na mão
        alvo = next(x for x in fila["itens"] if x["descricao"] == "TC DE CRANIO")
        r.estacao_escolher(alvo["id"])
        if r.fila_radius()["vez"] != alvo["id"]:
            falhas.append("estação: escolher não mudou o exame da vez")
        # TC não liga o perfil automático (só radiografia)
        t, o = r.rotear("hipodensidade no lobo temporal esquerdo")
        if "TOMOGRAFIA" in t:
            falhas.append("estação: perfil automático agiu numa TC")
        # marcar feito volta para o pendente seguinte
        r.estacao_feito(alvo["id"])
        if r.fila_radius()["vez"] == alvo["id"]:
            falhas.append("estação: exame marcado como feito continuou sendo o da vez")
    finally:
        r._config = cfg_real
        shutil.rmtree(pasta, ignore_errors=True)


def cenario_perfil(falhas):
    casa = tempfile.mkdtemp(prefix="perfil_")
    dados = os.path.join(casa, "dados")
    os.makedirs(os.path.join(dados, "mascaras_usuario", "rx", "torax"))
    os.makedirs(os.path.join(dados, "estilo"))
    perfil.AQUI, perfil.DADOS = casa, dados
    try:
        with open(os.path.join(dados, "mascaras_usuario", "rx", "torax", "normal.txt"),
                  "w", encoding="utf-8") as f:
            f.write("# gatilhos: meu rx de torax\n**RADIOGRAFIA DO TÓRAX**\n")
        with open(os.path.join(dados, "ouvido.tsv"), "w", encoding="utf-8") as f:
            f.write("# minhas regras\nmeu erro\tminha correção\n")
        with open(os.path.join(dados, "estilo", "usuario_abc.txt"), "w", encoding="utf-8") as f:
            f.write("laudo de estilo do usuário\n")
        with open(os.path.join(casa, "config.json"), "w", encoding="utf-8") as f:
            json.dump({"prompt_perfil": "meu jeito", "limite_mes_usd": 25,
                       "arquivo_da_chave": "chave_anthropic.txt", "chave_openai": "sk-SEGREDO"}, f)
        with open(os.path.join(casa, "chave_anthropic.txt"), "w", encoding="utf-8") as f:
            f.write("sk-SEGREDO-NAO-PODE-SAIR")
        destino = os.path.join(casa, "perfil.rotrix.zip")
        res = perfil.exportar(destino)
        if not res.get("ok") or res["mascaras"] != 1 or res["laudos_de_estilo"] != 0:
            falhas.append("perfil: exportação errada: %s" % res)
        with zipfile.ZipFile(destino) as z:
            tudo = b" ".join(z.read(n) for n in z.namelist()) + " ".join(z.namelist()).encode()
        for proibido in (b"SEGREDO", b"chave_openai", b"laudo de estilo"):
            if proibido.lower() in tudo.lower():
                falhas.append("perfil: vazou %r no arquivo" % proibido)
        res = perfil.exportar(destino, incluir_estilo=True)
        if res["laudos_de_estilo"] != 1:
            falhas.append("perfil: com --estilo deveria levar 1 laudo")
        # importar noutra "máquina"
        casa2 = tempfile.mkdtemp(prefix="perfil2_")
        os.makedirs(os.path.join(casa2, "dados"))
        with open(os.path.join(casa2, "dados", "ouvido.tsv"), "w", encoding="utf-8") as f:
            f.write("outra maquina\tja existia\n")
        with open(os.path.join(casa2, "config.json"), "w", encoding="utf-8") as f:
            json.dump({"limite_mes_usd": 10}, f)
        perfil.AQUI, perfil.DADOS = casa2, os.path.join(casa2, "dados")
        r_imp = perfil.importar(destino)
        if not r_imp.get("ok") and r_imp.get("motivo") != "falha_ao_gerar_a_base":
            falhas.append("perfil: importação falhou: %s" % r_imp)
        if r_imp.get("mascaras") != 1 or r_imp.get("ouvido") != 1:
            falhas.append("perfil: importação trouxe %s" % r_imp)
        cfg2 = json.load(open(os.path.join(casa2, "config.json"), encoding="utf-8"))
        if cfg2.get("prompt_perfil") != "meu jeito" or cfg2.get("limite_mes_usd") != 25:
            falhas.append("perfil: config não foi aplicada: %s" % cfg2)
        ouv = open(os.path.join(casa2, "dados", "ouvido.tsv"), encoding="utf-8").read()
        if "ja existia" not in ouv or "minha correção" not in ouv:
            falhas.append("perfil: ouvido.tsv não juntou as regras")
        # arquivo estranho não é aceito
        falso = os.path.join(casa2, "falso.zip")
        with zipfile.ZipFile(falso, "w") as z:
            z.writestr("perfil.json", json.dumps({"marca": "outro"}))
            z.writestr("../fora.txt", "nao pode")
        if perfil.importar(falso).get("ok"):
            falhas.append("perfil: aceitou um arquivo que não é perfil")
        shutil.rmtree(casa2, ignore_errors=True)
    finally:
        shutil.rmtree(casa, ignore_errors=True)


def main():
    falhas = []
    cenario_estacao(falhas)
    cenario_perfil(falhas)
    for f in falhas:
        print("FALHOU", f)
    print("estação e perfil: tudo certo" if not falhas else "estação e perfil: %d falha(s)" % len(falhas))
    sys.exit(1 if falhas else 0)


if __name__ == "__main__":
    main()

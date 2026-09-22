# -*- coding: utf-8 -*-
"""Perfil do radiologista: levar o que é SEU para outro computador.

Entra no arquivo (.rotrix.zip):
  - dados/mascaras_usuario/**      as suas máscaras
  - dados/ouvido.tsv               as suas correções de ouvido
  - config.json                    ajustes, prompt do perfil e rota de IA por exame
  - aprendizado.json               pares de palavras aprendidos
  - dados/estilo/usuario_*.txt     SÓ se você pedir (são laudos seus)

Nunca entra: chave de IA (chave_*.txt), gasto, base.sqlite (é gerada),
o diagnóstico do Radius, a fila da estação e o sal do Radius.
"""
import json
import os
import shutil
import subprocess
import sys
import time
import zipfile

AQUI = os.path.dirname(os.path.abspath(__file__))
DADOS = os.path.join(AQUI, "dados")
MARCA = "rotrix-perfil"
VERSAO_PERFIL = 1

# config.json: o que é do radiologista (o resto é do pacote e fica como está)
CHAVES_CONFIG = ("prompt_perfil", "prompt_por_exame", "ia_por_exame", "modelo", "provedor",
                 "ativa", "gatilhos", "gatilhos_revisao", "limite_mes_usd", "marcar_saida",
                 "marca_inicio", "marca_fim", "rx_literal", "tc_literal", "alteradas_primeiro",
                 "perfil_automatico", "processador_colagem", "modo_ia", "temperatura",
                 "max_tokens", "timeout_s")
# nunca sai daqui
PROIBIDO = ("chave", "api_key", "apikey", "token", "secret", "senha")


def _sem_chave(cfg):
    fora = {}
    for k, v in (cfg or {}).items():
        if k not in CHAVES_CONFIG:
            continue
        if any(p in k.lower() for p in PROIBIDO):
            continue
        fora[k] = v
    return fora


def _arquivos_usuario(incluir_estilo=False):
    itens = []                                   # (caminho_no_disco, nome_no_zip)
    pasta_masc = os.path.join(DADOS, "mascaras_usuario")
    if os.path.isdir(pasta_masc):
        for raiz, _d, arqs in os.walk(pasta_masc):
            for a in arqs:
                if a.lower().endswith(".txt"):
                    caminho = os.path.join(raiz, a)
                    itens.append((caminho, os.path.relpath(caminho, AQUI).replace("\\", "/")))
    ouvido = os.path.join(DADOS, "ouvido.tsv")
    if os.path.exists(ouvido):
        itens.append((ouvido, "dados/ouvido.tsv"))
    apr = os.path.join(AQUI, "aprendizado.json")
    if os.path.exists(apr):
        itens.append((apr, "aprendizado.json"))
    if incluir_estilo:
        pasta_estilo = os.path.join(DADOS, "estilo")
        if os.path.isdir(pasta_estilo):
            for a in sorted(os.listdir(pasta_estilo)):
                if a.startswith("usuario_") and a.lower().endswith(".txt"):
                    itens.append((os.path.join(pasta_estilo, a), "dados/estilo/" + a))
    return itens


def _config():
    try:
        with open(os.path.join(AQUI, "config.json"), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def exportar(destino=None, incluir_estilo=False):
    """Grava o perfil num .rotrix.zip. Devolve {ok, arquivo, mascaras, laudos, ...}."""
    destino = destino or os.path.join(AQUI, "pacote",
                                      "perfil-rotrix-%s.rotrix.zip" % time.strftime("%Y%m%d-%H%M"))
    destino = os.path.expandvars(os.path.expanduser(destino))
    if os.path.isdir(destino):
        destino = os.path.join(destino, "perfil-rotrix-%s.rotrix.zip" % time.strftime("%Y%m%d-%H%M"))
    os.makedirs(os.path.dirname(destino) or ".", exist_ok=True)
    itens = _arquivos_usuario(incluir_estilo)
    manifesto = {
        "marca": MARCA, "versao": VERSAO_PERFIL, "gerado_em": time.strftime("%Y-%m-%d %H:%M"),
        "mascaras": sum(1 for _c, n in itens if n.startswith("dados/mascaras_usuario/")),
        "laudos_de_estilo": sum(1 for _c, n in itens if n.startswith("dados/estilo/")),
        "ouvido": any(n == "dados/ouvido.tsv" for _c, n in itens),
        "config": True,
    }
    tmp = destino + ".tmp"
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("perfil.json", json.dumps(manifesto, ensure_ascii=False, indent=2))
        z.writestr("config.json", json.dumps(_sem_chave(_config()), ensure_ascii=False, indent=2))
        for caminho, nome in itens:
            z.write(caminho, nome)
    os.replace(tmp, destino)
    manifesto.update(ok=True, arquivo=destino)
    return manifesto


def _seguro(nome):
    """Só os caminhos que este formato usa (nada de .., nada de caminho absoluto)."""
    n = nome.replace("\\", "/").lstrip("/")
    if ".." in n.split("/"):
        return None
    if n in ("perfil.json", "config.json", "aprendizado.json", "dados/ouvido.tsv"):
        return n
    if n.startswith("dados/mascaras_usuario/") and n.lower().endswith(".txt"):
        return n
    if n.startswith("dados/estilo/usuario_") and n.lower().endswith(".txt"):
        return n
    return None


def _juntar_ouvido(novo_texto):
    """As regras do arquivo que chega entram por baixo; as suas ficam."""
    destino = os.path.join(DADOS, "ouvido.tsv")
    atuais = []
    if os.path.exists(destino):
        with open(destino, encoding="utf-8") as f:
            atuais = f.read().splitlines()
    tem = {l.split("\t")[0].strip().lower() for l in atuais if "\t" in l and not l.startswith("#")}
    novas = [l for l in novo_texto.splitlines()
             if "\t" in l and not l.startswith("#") and l.split("\t")[0].strip().lower() not in tem]
    if not novas:
        return 0
    with open(destino, "a", encoding="utf-8") as f:
        f.write("\n# regras que vieram do perfil importado\n" + "\n".join(novas) + "\n")
    return len(novas)


def importar(arquivo, modo="juntar"):
    """modo: "juntar" (soma ao que já existe) ou "substituir" (troca as suas máscaras).
    Devolve {ok, mascaras, laudos_de_estilo, ouvido, config, base}."""
    arquivo = os.path.expandvars(os.path.expanduser(arquivo or ""))
    if not os.path.exists(arquivo):
        return {"ok": False, "motivo": "arquivo_nao_encontrado"}
    res = {"ok": True, "mascaras": 0, "laudos_de_estilo": 0, "ouvido": 0, "config": False}
    with zipfile.ZipFile(arquivo) as z:
        nomes = [n for n in z.namelist() if not n.endswith("/")]
        try:
            manifesto = json.loads(z.read("perfil.json").decode("utf-8"))
        except (KeyError, ValueError):
            return {"ok": False, "motivo": "nao_e_um_perfil_rotrix"}
        if manifesto.get("marca") != MARCA:
            return {"ok": False, "motivo": "nao_e_um_perfil_rotrix"}
        if modo == "substituir":
            shutil.rmtree(os.path.join(DADOS, "mascaras_usuario"), ignore_errors=True)
        for n in nomes:
            seguro = _seguro(n)
            if seguro is None:
                continue
            dados = z.read(n)
            if seguro == "perfil.json":
                continue
            if seguro == "dados/ouvido.tsv":
                res["ouvido"] = _juntar_ouvido(dados.decode("utf-8", "replace"))
                continue
            if seguro == "config.json":
                atual = _config()
                atual.update(_sem_chave(json.loads(dados.decode("utf-8", "replace"))))
                with open(os.path.join(AQUI, "config.json"), "w", encoding="utf-8") as f:
                    json.dump(atual, f, ensure_ascii=False, indent=2)
                res["config"] = True
                continue
            destino = os.path.join(AQUI, *seguro.split("/"))
            os.makedirs(os.path.dirname(destino), exist_ok=True)
            with open(destino, "wb") as f:
                f.write(dados)
            if seguro.startswith("dados/mascaras_usuario/"):
                res["mascaras"] += 1
            elif seguro.startswith("dados/estilo/"):
                res["laudos_de_estilo"] += 1
    if res["mascaras"]:
        r = subprocess.run([sys.executable, os.path.join(AQUI, "construir_base.py")], cwd=AQUI,
                           capture_output=True, text=True, timeout=900)
        res["base"] = (r.returncode == 0)
        if r.returncode != 0:
            res["ok"] = False
            res["motivo"] = "falha_ao_gerar_a_base"
    return res


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "exportar":
        print(json.dumps(exportar(sys.argv[2] if len(sys.argv) > 2 else None,
                                  "--estilo" in sys.argv), ensure_ascii=False))
    elif len(sys.argv) > 2 and sys.argv[1] == "importar":
        print(json.dumps(importar(sys.argv[2], "substituir" if "--substituir" in sys.argv else "juntar"),
                         ensure_ascii=False))
    else:
        print(__doc__)

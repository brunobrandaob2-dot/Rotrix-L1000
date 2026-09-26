# -*- coding: utf-8 -*-
"""Por que a IA de um provedor não entra na tela?  python diagnosticar_ia.py

26/09: ele gravou a chave da OpenAI, trocou para OpenAI, voltou ao Laudo — e a
tela voltava para a Anthropic. A tela só mostra o modelo de um provedor quando a
lista de modelos DELE responde; se não responde, o botão cai no que existe.
Este diagnóstico mostra, para cada provedor com chave nesta máquina:
  - de onde vem a chave (arquivo ou variável do Windows)
  - se o começo da chave é de chave daquele provedor (chave trocada de arquivo)
  - tamanho, espaço, quebra de linha e BOM (chave colada com sujeira)
  - o que a API respondeu agora

NUNCA mostra a chave, nem pedaço dela. Não grava nada além do que a tela já grava.
"""
import io
import json
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)

import nuvem  # noqa: E402

EXPLICA = {
    "http_401": "a API RECUSOU a chave: chave errada, incompleta ou revogada. Gere outra no site do provedor.",
    "http_403": "a chave existe mas não tem permissão (projeto/organização sem acesso aos modelos).",
    "http_429": "limite ou saldo: a conta está sem crédito ou estourou o limite por minuto.",
    "http_404": "endereço da API errado para este provedor.",
    "URLError": "não chegou na API: internet, firewall, antivírus ou proxy da rede bloqueando.",
    "timeout": "a API não respondeu a tempo: rede lenta ou bloqueada.",
    "TimeoutError": "a API não respondeu a tempo: rede lenta ou bloqueada.",
    "sem_chave": "não há chave para este provedor nesta pasta nem no Windows.",
}


def main():
    c = nuvem.config()
    print("pasta:               %s" % AQUI)
    print("provedor no config:  %s" % (c.get("provedor") or "(não escrito -> anthropic)"))
    print("modelo no config:    %s" % (c.get("modelo") or "(vazio)"))
    print("provedores com chave: %s" % ", ".join(nuvem.provedores_com_chave(c)))
    vistos = sorted((c.get("modelos_vistos") or {}).keys())
    print("lista de modelos que JÁ funcionou alguma vez: %s" % (", ".join(vistos) or "nenhuma"))

    for nome in ("anthropic", "openai", "gemini", "openrouter"):
        chave, origem = nuvem.chave_e_origem(c, nome)
        print()
        if not chave:
            print("[%s] sem chave" % nome)
            continue
        tipo = nuvem.provedor_da_chave(chave) or "desconhecido"
        bate = tipo == nome
        print("[%s] chave vem de: %s" % (nome, origem))
        print("    %d caracteres; o começo é de chave de: %s%s"
              % (len(chave), tipo, "" if bate else "   <-- NÃO BATE COM " + nome.upper()))
        print("    espaço no meio: %s" % ("SIM (colou com sujeira)" if any(ch.isspace() for ch in chave) else "não"))
        if origem.startswith("arquivo:"):
            arq = os.path.join(AQUI, origem.split(":", 1)[1])
            try:
                b = open(arq, "rb").read()
                bom = b[:3] == b"\xef\xbb\xbf" or b[:2] in (b"\xff\xfe", b"\xfe\xff")
                print("    arquivo: %d bytes; BOM: %s; quebra de linha: %s"
                      % (len(b), "sim" if bom else "não",
                         "sim" if (b"\n" in b or b"\r" in b) else "não"))
            except OSError as e:
                print("    arquivo: não consegui ler (%s)" % type(e).__name__)
        r = nuvem.testar(c, nome, timeout=20)
        if r.get("ok"):
            print("    API: OK em %s ms, %s modelos" % (r.get("ms"), r.get("quantos")))
        else:
            m = str(r.get("motivo") or "")
            print("    API: FALHOU -> %s (%s ms)" % (m, r.get("ms")))
            print("    o que quer dizer: %s" % EXPLICA.get(m, "ver o motivo acima."))
    print()
    print("Resumo em JSON (para o Claude): %s" % json.dumps({
        "provedor": c.get("provedor") or "", "modelo": c.get("modelo") or "",
        "vistos": vistos}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

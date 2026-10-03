# -*- coding: utf-8 -*-
"""Aba Máscaras: caixa editável, "Pôr no laudo" e a máscara de voz do Lyon.

    python testar_mascaras_editar.py

03/10, pedidos dele:
  - "quando eu seleciono uma máscara, eu quero um botão em que eu possa jogar ela
    direto na caixa de laudo"
  - "eu quero poder editar os gatilhos, alguma frase na máscara ... eu quero que
    essa caixa de texto seja editável"
  - "a parte do joelho no protocolo de Lyon ... não está com a máscara mais atual"
Este teste exige:
  1. abrir uma máscara traz o corpo cru (com as lacunas), os comandos como estão
     escritos no arquivo e o texto pronto para a folha (sem lacuna sobrando)
  2. "editar" numa máscara do Rotrix: vira cópia DELE com os comandos novos, o
     tipo (aguda/cronica/normal) é mantido, a do Rotrix fica intacta
  3. "editar" numa máscara dele: reescreve com cópia guardada (desfazer volta)
  4. comando que começa com palavra de comando, texto vazio: recusa
  5. "substituir" também mantém o tipo (antes toda cópia virava "normal")
  6. a máscara de voz do Lyon é a de 28/09 (texto corrido + tabela por joelho)
Tudo numa pasta temporária: nada da pasta real é tocado.
"""
import io
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import oficina  # noqa: E402
import importar_usuario  # noqa: E402
import lyon  # noqa: E402

AQUI = os.path.dirname(os.path.abspath(__file__))
falhas = []


def confere(nome, ok, extra=""):
    print("%-6s  %s%s" % ("ok" if ok else "FALHA", nome, ("\n        " + extra) if (extra and not ok) else ""))
    if not ok:
        falhas.append(nome)


# ---------- 1. o que a tela recebe ao abrir ----------
import roteador  # noqa: E402

tit = "msk/rx/ombro/aguda_fratura_umero_proximal"
r = roteador.mascaras_banco("", tit)
confere("abrir: editável, com o corpo cru e as lacunas", r.get("editavel") is True
        and "{partes|" in r.get("corpo", ""), repr(r.get("corpo", ""))[:200])
confere("abrir: comandos como estão escritos no arquivo (não normalizados)",
        "raio x de ombro com fratura" in (r.get("gatilhos_escritos") or [])
        and len(r.get("gatilhos_escritos") or []) >= 5, repr(r.get("gatilhos_escritos"))[:200])
confere("abrir: é do Rotrix", r.get("eh_sua") is False)
folha = r.get("folha", "")
confere("abrir: o texto para a folha não tem lacuna crua", folha and "{" not in folha and "}" not in folha,
        folha[:300])
normal = roteador.mascaras_banco("", "medicina_interna/tc/torax/normal")
confere("Pôr no laudo: TC de tórax normal sai com título e seções",
        "TOMOGRAFIA" in normal.get("folha", "").upper() and "CONCLUSÃO" in normal.get("folha", "").upper(),
        normal.get("folha", "")[:200])
confere("título desconhecido: não quebra", roteador.mascaras_banco("", "nao/existe").get("ok") is True)

# ---------- 2-5. a oficina numa pasta temporária ----------
tmp = tempfile.mkdtemp()
oficina.DADOS = tmp
oficina.PASTA_ROTRIX = os.path.join(tmp, "mascaras")
oficina.PASTA_USUARIO = os.path.join(tmp, "mascaras_usuario")
oficina.PASTA_COPIAS = os.path.join(tmp, "oficina_copias")
importar_usuario.fonte_atual = lambda: "ambas"          # não mexe no config real
os.makedirs(os.path.join(oficina.PASTA_ROTRIX, "msk", "rx", "ombro"))
shutil.copy(os.path.join(AQUI, "dados", "mascaras", "msk", "rx", "ombro", "aguda_fratura_umero_proximal.txt"),
            os.path.join(oficina.PASTA_ROTRIX, "msk", "rx", "ombro"))
original = io.open(os.path.join(oficina.PASTA_ROTRIX, "msk", "rx", "ombro", "aguda_fratura_umero_proximal.txt"),
                   encoding="utf-8").read()


def ler_usuario(rel):
    return io.open(os.path.join(oficina.PASTA_USUARIO, *rel.split("/")), encoding="utf-8").read()


novo_corpo = r["corpo"].replace("segundo Neer", "segundo a classificação de Neer")
res = oficina.aplicar([{"acao": "editar", "titulo": tit, "gatilhos": ["rx de ombro com fratura do úmero",
                                                                        "raio x do ombro fraturado"],
                        "depois": novo_corpo}], conferir_no_banco=False)
item = (res.get("itens") or [{}])[0]
confere("editar do Rotrix: gravou", res.get("ok") and res.get("aplicadas") == 1, repr(res)[:300])
confere("editar do Rotrix: vira máscara DELE", item.get("arquivo", "").startswith("mascaras_usuario/rx/ombro/")
        and item.get("titulo_novo", "").startswith("usuario/rx/ombro/"), repr(item))
gravado = ler_usuario(item["arquivo"][len("mascaras_usuario/"):]) if item.get("arquivo") else ""
confere("com os comandos novos", "# gatilhos: rx de ombro com fratura do úmero | raio x do ombro fraturado"
        in gravado, gravado[:200])
confere("o tipo da variante fica 'aguda' (não 'normal')", "# tipo_mascara: aguda" in gravado, gravado[:300])
confere("com o texto editado", "segundo a classificação de Neer" in gravado)
confere("a do Rotrix fica intacta", io.open(os.path.join(oficina.PASTA_ROTRIX, "msk", "rx", "ombro",
                                                         "aguda_fratura_umero_proximal.txt"),
                                            encoding="utf-8").read() == original)

# editar a DELE: reescreve com cópia
tit_dele = item["titulo_novo"]
arq_dele = os.path.join(oficina.PASTA_USUARIO, *tit_dele[len("usuario/"):].split("/")) + ".txt"
antes = io.open(arq_dele, encoding="utf-8").read()
res2 = oficina.aplicar([{"acao": "editar", "titulo": tit_dele, "gatilhos": ["raio x do ombro fraturado"],
                         "depois": "**RX DO OMBRO**\nTexto curto."}], conferir_no_banco=False)
depois = io.open(arq_dele, encoding="utf-8").read()
confere("editar a dele: reescreve no mesmo arquivo", res2.get("ok") and "Texto curto." in depois
        and (res2.get("itens") or [{}])[0].get("titulo_novo") == tit_dele, repr(res2)[:200])
confere("e guarda cópia: desfazer volta", oficina.desfazer(res2["desfazer"]).get("ok")
        and io.open(arq_dele, encoding="utf-8").read() == antes)

# recusas
res3 = oficina.aplicar([{"acao": "editar", "titulo": tit_dele, "gatilhos": ["mascara de ombro"],
                         "depois": "x"}], conferir_no_banco=False)
confere("comando que começa com 'mascara': recusa e diz como fica", not res3.get("ok")
        and any('use "de ombro"' in e for e in res3.get("erros", [])), repr(res3.get("erros")))
res4 = oficina.aplicar([{"acao": "editar", "titulo": tit_dele, "gatilhos": ["rx ombro"], "depois": "  "}],
                       conferir_no_banco=False)
confere("texto vazio: recusa", not res4.get("ok") and any("vazio" in e for e in res4.get("erros", [])))
res5 = oficina.aplicar([{"acao": "editar", "titulo": "msk/nao/existe", "depois": "x"}], conferir_no_banco=False)
confere("máscara inexistente: recusa", not res5.get("ok"))
cab_antes = [l for l in io.open(arq_dele, encoding="utf-8").read().splitlines() if l.startswith("# gatilhos:")]
confere("sem comando escrito usa os do arquivo", oficina.aplicar(
    [{"acao": "editar", "titulo": tit_dele, "gatilhos": [], "depois": "Outro texto."}],
    conferir_no_banco=False).get("ok") and cab_antes and cab_antes[0]
    in io.open(arq_dele, encoding="utf-8").read(), repr(cab_antes))

# 5. substituir mantém o tipo
res6 = oficina.aplicar([{"acao": "substituir", "titulo": tit, "depois": "Texto substituído."}],
                       conferir_no_banco=False)
arq6 = os.path.join(tmp, (res6.get("itens") or [{}])[0].get("arquivo", "x"))
confere("substituir também mantém 'aguda'", res6.get("ok") and "# tipo_mascara: aguda"
        in io.open(arq6, encoding="utf-8").read(), repr(res6)[:200])
confere("_tipo pelo nome quando o cabeçalho não diz", oficina._tipo("", "x/cronica_dpoc.txt") == "cronica"
        and oficina._tipo("", "x/tc_coxa.txt") == "normal" and oficina._tipo("# tipo_mascara: aguda", "") == "aguda")

# ---------- 6. Lyon ----------
v = lyon.mascara_de_voz()
confere("Lyon de voz: a de 28/09 (texto corrido)", "morfologia do tipo 2 de Wiberg, bilateral" in v
        and "Planos musculogordurosos íntegros, bilateral." in v)
confere("Lyon de voz: tabela dos dois joelhos com os normais dele",
        v.count("Mensurado") == 2 and "Medidas joelho direito" in v and "Medidas joelho esquerdo" in v
        and all(l[3] in v for l in lyon.LINHAS))
confere("Lyon de voz: nada da de 27/09", not any(x in v for x in ("Caton", "TT-PCL", "Dejour", "{")))
confere("Lyon de voz: tabela antes da COMPARAÇÃO", v.index("Medidas joelho esquerdo") < v.index("COMPARAÇÃO"))

print()
print("máscaras (editar, pôr no laudo, Lyon): %s" % ("tudo certo" if not falhas else "%d FALHA(S)" % len(falhas)))
sys.exit(1 if falhas else 0)

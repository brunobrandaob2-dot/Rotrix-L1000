# -*- coding: utf-8 -*-
"""Teste às cegas das IAs na TC: a mesma folha em três IAs, sem dizer qual é qual.

    python teste_cego_ia.py            (pergunta antes de gastar)
    python teste_cego_ia.py --sim      (não pergunta)
    python teste_cego_ia.py --casos 5  (só os 5 primeiros)

Por que existe (16/10): ele quer saber se dá para ganhar tempo SEM deixar a IA
"mais burra", e deixou em aberto usar o Luna na TC ("muitas vezes são frases tão
simples que o Luna conseguiria organizar o laudo"). Opinião não decide isso; laudo
lado a lado decide.

O que faz
  1. 20 ditados INVENTADOS de TC (nenhum laudo real, nenhum paciente) passam pelo
     roteador local, como no dia a dia: sai a folha montada pelo banco.
  2. Cada folha vai para três IAs, pelo MESMO caminho do botão de IA da folha
     (resposta por diferença incluída):
        Sol, raciocínio padrão  |  Sol, raciocínio baixo  |  Luna, sem raciocínio
  3. Grava em logs_teste\\teste_cego_<data>\\:
        TESTE_CEGO.html   as três respostas embaralhadas (X, Y, Z), sem nome
        GABARITO.html     qual letra é qual IA, tempo e custo — abra DEPOIS
        gabarito.json     o mesmo, para o Claude conferir
Custo: o script mostra a estimativa e pergunta antes de gastar (60 chamadas; perto de
US$ 1). Respeita o limite_mes_usd.
A chave fica onde está (chave_openai.txt); nada além do texto inventado sai daqui.
"""
import datetime
import html
import io
import json
import os
import random
import re
import sys
import threading
import time

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import nuvem  # noqa: E402
import roteador  # noqa: E402

roteador._aprender = lambda *a, **k: None      # teste não ensina par de palavra ao roteador

# (ditado inventado, instrução falada ou "")
CASOS = [
    ("tomografia de tórax com nódulo sólido de 6 mm no lobo superior direito", "melhore a conclusão"),
    ("tomografia de tórax com enfisema centrolobular e bolhas apicais", ""),
    ("tomografia de tórax com derrame pleural bilateral maior à direita com atelectasia passiva", ""),
    ("tomografia de tórax com opacidades em vidro fosco periféricas bilaterais", ""),
    ("tomografia de tórax com bronquiectasias nos lobos inferiores", ""),
    ("tomografia de abdome total com esteatose hepática e colelitíase", ""),
    ("tomografia de abdome total com cisto simples no rim esquerdo de 2 cm", ""),
    ("tomografia de abdome com apendicite aguda", ""),
    ("tomografia de abdome total com diverticulose do cólon sigmoide", ""),
    ("tomografia de abdome total com cálculo de 5 mm no ureter distal direito e hidronefrose leve", ""),
    ("tomografia de crânio com microangiopatia e redução volumétrica encefálica", ""),
    ("tomografia de crânio com hematoma subdural agudo à esquerda", ""),
    ("tomografia de crânio normal", "acrescente calcificações fisiológicas nos plexos coroides"),
    ("tomografia de coluna lombar com abaulamento discal em L4-L5 e L5-S1", ""),
    ("tomografia de coluna cervical com uncoartrose e redução dos forames em C5-C6", ""),
    ("tomografia de seios da face com espessamento mucoso maxilar bilateral", ""),
    ("tomografia de tórax normal", "inclua nódulo calcificado de 4 mm no lobo médio, residual"),
    ("tomografia de abdome total com hérnia umbilical contendo gordura", ""),
    ("tomografia de tórax com linfonodomegalia mediastinal e derrame pericárdico pequeno",
     "organize os achados por importância"),
    ("tomografia de pelve com cisto ovariano simples à direita", ""),
]

# (chave, nome na tela do gabarito, modelo, raciocínio pedido)
VARIANTES = [
    ("sol_padrao", "Sol — raciocínio padrão", "openai:gpt-6-sol", ""),
    ("sol_baixo", "Sol — raciocínio baixo", "openai:gpt-6-sol", "low"),
    ("luna", "Luna — sem raciocínio", "openai:gpt-6-luna", ""),
]
LETRAS = "XYZ"


def _arg(nome, padrao=None):
    if nome in sys.argv:
        i = sys.argv.index(nome)
        return sys.argv[i + 1] if i + 1 < len(sys.argv) else padrao
    return padrao


def folha_do_ditado(ditado):
    texto, origem = roteador.rotear(ditado)
    if str(origem).startswith("nuvem"):
        raise SystemExit("o ditado de teste foi para a nuvem (%s): corrija o caso" % origem)
    return roteador.formatar_saida(texto), origem


def rodar_variante(folha, instrucao, var, saida):
    _k, _nome, modelo, rac = var
    c = nuvem.com_modelo(nuvem.config(), modelo)
    if rac:
        c["raciocinio"] = rac
    pedido = ("INSTRUÇÃO FALADA: %s\n\n" % instrucao if instrucao else "") + \
        "LAUDO NA TELA:\n" + roteador.juntar_rotulos_repetidos(folha)
    t0 = time.time()
    try:
        texto, origem, formato = roteador._laudo_pela_ia(pedido, c)
    except Exception as e:
        texto, origem, formato = None, "erro:%s" % type(e).__name__, ""
    u = nuvem.ultima_desta_chamada()
    saida.update(texto=texto or "", origem=origem, formato=formato, s=round(time.time() - t0, 1),
                 usd=u.get("usd") or 0, modelo=u.get("modelo") or modelo, tokens_out=u.get("tokens_out") or 0)


def estimar(n_casos):
    total = 0.0
    for _k, _n, modelo, _r in VARIANTES:
        prov, _, m = modelo.partition(":")
        try:
            total += n_casos * float(nuvem.custo(m, 4500, 900))
        except Exception:
            total += n_casos * 0.05
    return total


def _linhas_mudadas(entrada, saida):
    base = {l.strip() for l in (entrada or "").split("\n") if l.strip()}
    return [(l, bool(l.strip()) and l.strip() not in base) for l in (saida or "").split("\n")]


def _negrito(t):
    """**TÍTULO** do laudo em negrito na tela (é o que o colador faz no RIS)."""
    return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", html.escape(t))


def _bloco_texto(entrada, saida):
    partes = []
    for l, mudou in _linhas_mudadas(entrada, saida):
        if not l.strip():
            partes.append('<div class="l v"></div>')
            continue
        partes.append('<div class="l%s">%s</div>' % (" m" if mudou else "", _negrito(l)))
    return "".join(partes)        # sem \n entre as linhas: o pre-wrap viraria linha em branco


_CSS = """
:root{--fundo:#f7f7f5;--papel:#fff;--tinta:#1d1d1b;--fraco:#6b6b66;--borda:#ddd;--marca:#fff3c4;--acento:#1f5fa8}
@media (prefers-color-scheme: dark){:root{--fundo:#161615;--papel:#1f1f1e;--tinta:#ecebe6;--fraco:#a3a29c;--borda:#3a3a38;--marca:#4a3f12;--acento:#7fb0ef}}
body{background:var(--fundo);color:var(--tinta);font:15px/1.45 system-ui,Segoe UI,Arial,sans-serif;margin:0;padding:16px}
h1{font-size:20px;margin:0 0 4px} .sub{color:var(--fraco);margin:0 0 18px}
.caso{background:var(--papel);border:1px solid var(--borda);border-radius:8px;padding:14px;margin:0 0 18px}
.caso h2{font-size:16px;margin:0 0 6px} .dit{color:var(--fraco);margin:0 0 8px}
details{margin:0 0 10px} summary{cursor:pointer;color:var(--acento)}
.cols{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:10px}
.col{border:1px solid var(--borda);border-radius:6px;padding:8px;min-width:0}
.col h3{margin:0 0 6px;font-size:15px}
.txt{font:13px/1.4 Consolas,ui-monospace,monospace;white-space:pre-wrap;overflow-wrap:anywhere}
.l.m{background:var(--marca)} .l.v{height:.5em}
.esc{margin-top:8px;font-size:14px} .esc label{margin-right:12px;white-space:nowrap}
textarea{width:100%;box-sizing:border-box;min-height:90px;font:13px monospace;background:var(--papel);color:var(--tinta);border:1px solid var(--borda)}
button{font:inherit;padding:6px 12px;border-radius:6px;border:1px solid var(--borda);background:var(--papel);color:var(--tinta);cursor:pointer}
table{border-collapse:collapse;width:100%;font-size:14px} td,th{border:1px solid var(--borda);padding:4px 6px;text-align:left}
"""


def _html_cego(resultados, quando):
    casos = []
    for i, r in enumerate(resultados, 1):
        cols = []
        for letra in LETRAS:
            v = r["por_letra"][letra]
            corpo = _bloco_texto(r["folha"], v["texto"]) if v["texto"] else \
                '<div class="l">(a IA não respondeu: %s)</div>' % html.escape(v["origem"])
            cols.append('<div class="col"><h3>%s</h3><div class="txt">%s</div>'
                        '<div class="esc"><label><input type="checkbox" data-c="%d" data-erro="%s"> tem erro</label></div></div>'
                        % (letra, corpo, i, letra))
        radios = " ".join('<label><input type="radio" name="m%d" value="%s"> %s</label>' % (i, x, x)
                          for x in list(LETRAS) + ["empate"])
        casos.append(
            '<section class="caso"><h2>Caso %d</h2><p class="dit">ditado (inventado): %s%s</p>'
            '<details><summary>folha que entrou</summary><div class="txt">%s</div></details>'
            '<div class="cols">%s</div><div class="esc"><b>melhor:</b> %s</div></section>'
            % (i, html.escape(r["ditado"]),
               (" &nbsp;|&nbsp; instrução: " + html.escape(r["instrucao"])) if r["instrucao"] else "",
               _bloco_texto(r["folha"], r["folha"]), "".join(cols), radios))
    return """<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Teste às cegas</title><style>%s</style></head><body>
<h1>Teste às cegas — TC</h1>
<p class="sub">%s · %d casos · três IAs embaralhadas em X, Y e Z (a ordem muda a cada caso). Amarelo = linha que a IA mudou.
Escolha a melhor de cada caso, marque as que têm erro e, no fim, copie o resultado para o Claude. Só abra o GABARITO.html depois.</p>
%s
<section class="caso"><h2>Resultado</h2><button id="gerar">Gerar o texto para o Claude</button>
<p></p><textarea id="saida" readonly></textarea></section>
<script>
(function(){
  var CHAVE='teste_cego_%s';
  function salvar(){try{var d={};document.querySelectorAll('input').forEach(function(e){if(e.type==='radio'&&e.checked)d[e.name]=e.value;if(e.type==='checkbox')d['c'+e.dataset.c+e.dataset.erro]=e.checked;});localStorage.setItem(CHAVE,JSON.stringify(d));}catch(e){}}
  function ler(){try{var d=JSON.parse(localStorage.getItem(CHAVE)||'{}');document.querySelectorAll('input').forEach(function(e){if(e.type==='radio'&&d[e.name]===e.value)e.checked=true;if(e.type==='checkbox'&&d['c'+e.dataset.c+e.dataset.erro])e.checked=true;});}catch(e){}}
  ler();document.addEventListener('change',salvar);
  document.getElementById('gerar').onclick=function(){
    var n=%d,l=[];for(var i=1;i<=n;i++){var m=document.querySelector('input[name=m'+i+']:checked');
      var er=[];document.querySelectorAll('input[data-c="'+i+'"]:checked').forEach(function(e){er.push(e.dataset.erro);});
      l.push(i+': melhor='+(m?m.value:'-')+(er.length?' erro='+er.join(','):''));}
    var t=document.getElementById('saida');t.value='teste cego %s\\n'+l.join('\\n');t.select();
    try{navigator.clipboard.writeText(t.value);}catch(e){}
  };
})();
</script></body></html>""" % (_CSS, html.escape(quando), len(resultados), "\n".join(casos), quando.replace(" ", "_"),
                              len(resultados), quando)


def _html_gabarito(resultados, quando, resumo):
    linhas = []
    for i, r in enumerate(resultados, 1):
        for letra in LETRAS:
            v = r["por_letra"][letra]
            linhas.append("<tr><td>%d</td><td>%s</td><td>%s</td><td>%.1f s</td><td>US$ %.4f</td><td>%s</td><td>%s</td></tr>"
                          % (i, letra, html.escape(v["nome"]), v["s"], v["usd"], html.escape(v["formato"] or "-"),
                             html.escape(v["origem"])))
    res = "".join("<tr><td>%s</td><td>%.1f s</td><td>%.1f s</td><td>US$ %.3f</td><td>%d de %d</td></tr>"
                  % (html.escape(n), d["mediana_s"], d["max_s"], d["usd"], d["ok"], d["n"]) for n, d in resumo.items())
    return """<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Gabarito do teste</title><style>%s</style></head><body>
<h1>Gabarito do teste às cegas</h1><p class="sub">%s — abra só depois de escolher no TESTE_CEGO.html.</p>
<section class="caso"><h2>Resumo por IA</h2><table><tr><th>IA</th><th>tempo mediano</th><th>pior tempo</th><th>custo total</th><th>respondeu</th></tr>%s</table></section>
<section class="caso"><h2>Caso a caso</h2><table><tr><th>caso</th><th>letra</th><th>IA</th><th>tempo</th><th>custo</th><th>formato</th><th>origem</th></tr>%s</table></section>
</body></html>""" % (_CSS, html.escape(quando), res, "".join(linhas))


def main():
    c = nuvem.config()
    if not c.get("ativa"):
        print("A IA está desligada no config.json (\"ativa\": false). Nada a fazer.")
        return 1
    n = int(_arg("--casos", len(CASOS)) or len(CASOS))
    casos = CASOS[:max(1, min(n, len(CASOS)))]
    est = estimar(len(casos))
    print("Teste às cegas: %d casos x %d IAs = %d chamadas. Custo estimado: US$ %.2f."
          % (len(casos), len(VARIANTES), len(casos) * len(VARIANTES), est))
    if "--sim" not in sys.argv:
        try:
            resp = input("Continuar? (s/n) ").strip().lower()
        except EOFError:
            resp = ""
        if not resp.startswith("s"):
            print("Nada foi enviado.")
            return 0
    quando = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    pasta = os.path.join(AQUI, "logs_teste", "teste_cego_" + datetime.datetime.now().strftime("%Y%m%d-%H%M"))
    os.makedirs(pasta, exist_ok=True)
    sorte = random.Random()
    resultados = []
    for i, (ditado, instrucao) in enumerate(casos, 1):
        folha, origem = folha_do_ditado(ditado)
        saidas = [{} for _ in VARIANTES]
        ths = [threading.Thread(target=rodar_variante, args=(folha, instrucao, v, s))
               for v, s in zip(VARIANTES, saidas)]
        for t in ths:
            t.start()
        for t in ths:
            t.join()
        ordem = list(range(len(VARIANTES)))
        sorte.shuffle(ordem)
        por_letra = {}
        for letra, j in zip(LETRAS, ordem):
            s = dict(saidas[j])
            s.update(chave=VARIANTES[j][0], nome=VARIANTES[j][1])
            por_letra[letra] = s
        resultados.append({"ditado": ditado, "instrucao": instrucao, "folha": folha, "origem_folha": origem,
                           "por_letra": por_letra})
        print("  caso %2d: %s" % (i, "  ".join("%s %.0fs" % (VARIANTES[j][0], saidas[j].get("s", 0))
                                               for j in range(len(VARIANTES)))), flush=True)
    resumo = {}
    for k, nome, _m, _r in VARIANTES:
        vs = [r["por_letra"][l] for r in resultados for l in LETRAS if r["por_letra"][l]["chave"] == k]
        tempos = sorted(v["s"] for v in vs)
        resumo[nome] = {"mediana_s": tempos[len(tempos) // 2] if tempos else 0, "max_s": max(tempos or [0]),
                        "usd": sum(float(v["usd"] or 0) for v in vs), "n": len(vs),
                        "ok": sum(1 for v in vs if v["texto"])}
    with open(os.path.join(pasta, "TESTE_CEGO.html"), "w", encoding="utf-8") as f:
        f.write(_html_cego(resultados, quando))
    with open(os.path.join(pasta, "GABARITO.html"), "w", encoding="utf-8") as f:
        f.write(_html_gabarito(resultados, quando, resumo))
    gab = {"quando": quando, "versao": getattr(roteador, "VERSAO", ""), "resumo": resumo,
           "casos": [{"caso": i, "ditado": r["ditado"], "instrucao": r["instrucao"],
                      "letras": {l: {k: r["por_letra"][l][k] for k in ("chave", "nome", "modelo", "s", "usd",
                                                                       "formato", "origem", "tokens_out")}
                                 for l in LETRAS}}
                     for i, r in enumerate(resultados, 1)]}
    with open(os.path.join(pasta, "gabarito.json"), "w", encoding="utf-8") as f:
        json.dump(gab, f, ensure_ascii=False, indent=2)
    print("")
    for nome, d in resumo.items():
        print("  %-26s mediana %.1f s · pior %.1f s · US$ %.3f · respondeu %d de %d"
              % (nome, d["mediana_s"], d["max_s"], d["usd"], d["ok"], d["n"]))
    print("")
    print("Pronto. Abra:  %s" % os.path.join(pasta, "TESTE_CEGO.html"))
    print("O gabarito (GABARITO.html) só depois de escolher.")
    try:
        if os.name == "nt":
            os.startfile(os.path.join(pasta, "TESTE_CEGO.html"))
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())

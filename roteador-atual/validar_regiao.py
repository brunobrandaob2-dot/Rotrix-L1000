# -*- coding: utf-8 -*-
"""Valida uma pasta de região contra o formato e contra o motor real.

    python3 validar_regiao.py dados/mascaras/msk/tc/joelho [outra/pasta ...]

Constrói uma base temporária (não mexe no base.sqlite de ninguém), roteia
cada gatilho e compõe cada bloco sobre a máscara normal da região.
Sai com código 1 se houver ERRO; AVISO não reprova.
"""
import os, re, sys, subprocess, tempfile, glob, importlib

AQUI = os.path.dirname(os.path.abspath(__file__))
CABS = ["TÉCNICA", "INDICAÇÃO CLÍNICA", "ANÁLISE", "COMPARAÇÃO", "CONCLUSÃO"]

def cabecalho(caminho):
    meta, gat, corpo = {}, [], []
    linhas = open(caminho, encoding="utf-8").read().splitlines()
    for i, l in enumerate(linhas):
        s = l.strip()
        if s.startswith("## "):
            corpo = linhas[i:]; break
        if s.startswith("#"):
            m = re.match(r"#\s*([a-z_]+)\s*:(.*)$", s, re.I)
            if m:
                k, v = m.group(1).lower(), m.group(2).strip()
                if k == "gatilhos":
                    gat = [g.strip() for g in v.split("|") if g.strip()]
                else:
                    meta[k] = v
            continue
        corpo = linhas[i:]; break
    return meta, gat, corpo

def main(pastas):
    erros, avisos = [], []
    fd, base = tempfile.mkstemp(suffix=".sqlite"); os.close(fd)
    env = dict(os.environ, LAUDO_BASE=base, LAUDO_CATALOGO=base + ".txt")
    r = subprocess.run([sys.executable, os.path.join(AQUI, "construir_base.py")],
                       cwd=AQUI, env=env, capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stdout, r.stderr); sys.exit(1)
    minhas = [os.path.relpath(os.path.abspath(p), os.path.join(AQUI, "dados", "mascaras"))
              .replace("\\", "/") for p in pastas]
    for l in r.stdout.splitlines():
        if "em " in l and any(m in l for m in minhas):
            erros.append("gatilho repetido: " + l.strip())

    os.environ["LAUDO_BASE"] = base
    sys.path.insert(0, AQUI)
    import roteador as R
    R.BANCO.caminho = base
    R.BANCO.carregar()

    for pasta in pastas:
        pasta = os.path.abspath(pasta)
        rel = os.path.relpath(pasta, os.path.join(AQUI, "dados", "mascaras")).replace("\\", "/")
        arqs = sorted(glob.glob(os.path.join(pasta, "*.txt")))
        normal = os.path.join(pasta, "normal.txt")
        if not os.path.exists(normal):
            erros.append(f"{rel}: falta normal.txt"); continue
        _, gn, corpo_n = cabecalho(normal)
        rx = rel.split("/")[1] == "rx" if rel.count("/") >= 2 else False
        rotulos_normal = set()
        frases_normal = []
        dentro = False
        for l in corpo_n:
            if "**ANÁLISE:**" in l: dentro = True; continue
            if dentro and l.startswith("**"): break
            if dentro and l.strip():
                frases_normal.append(R.normalizar(l))
            m = re.match(r"^([^\W\d_][^:*]{0,70}):\s", l)
            if dentro and m:
                rotulos_normal.add(R.normalizar(m.group(1)))
        n_cron = n_agu = n_blk = n_fr = 0
        for a in arqs:
            nome = os.path.basename(a)
            meta, gat, corpo = cabecalho(a)
            tag = f"{rel}/{nome}"
            if nome == "frases.txt":
                n = sum(1 for l in corpo if l.strip().startswith("## gatilhos:"))
                n_fr = n
                for l in corpo:
                    m = re.match(r"##\s*gatilhos\s*:(.*)$", l.strip())
                    if m:
                        g0 = m.group(1).split("|")[0].strip()
                        t, txt, sc = R.BANCO.buscar(R.normalizar(g0), "frase")
                        if txt is None or not t.startswith(rel):
                            erros.append(f"{tag}: frase '{g0}' não roteia para esta pasta (foi para {t})")
                continue
            if not gat:
                erros.append(f"{tag}: sem # gatilhos"); continue
            txt = "\n".join(corpo)
            if nome.startswith("blk_"):
                n_blk += 1
                sec = meta.get("secao", "")
                if not sec:
                    erros.append(f"{tag}: bloco sem # secao")
                elif rx:
                    sn = R.normalizar(sec)
                    if not any(f == sn or f.startswith(sn + " ") for f in frases_normal):
                        erros.append(f"{tag}: # secao '{sec}' não é o início de nenhuma frase da ANÁLISE do normal.txt")
                elif R.normalizar(sec) not in rotulos_normal:
                    erros.append(f"{tag}: # secao '{sec}' não existe como '{sec}:' na ANÁLISE do normal.txt")
                if rx and meta.get("conclusao"):
                    erros.append(f"{tag}: radiografia não tem conclusão — tire a linha # conclusao")
                if not rx and not meta.get("conclusao"):
                    avisos.append(f"{tag}: bloco sem # conclusao")
                primeira = next((l for l in corpo if l.strip()), "")
                if rx:
                    if primeira.lstrip().startswith("-") or re.match(r"^[^\W\d_][^:]{0,40}:  \S", primeira):
                        erros.append(f"{tag}: radiografia usa frase direta, sem 'Rótulo:  ' nem hífen")
                elif primeira.lstrip().startswith("-") or not re.match(r"^[^\W\d_][^:]{0,70}:  \S", primeira):
                    erros.append(f"{tag}: a linha do bloco deve ser 'Rótulo:  texto' (sem hífen, dois espaços)")
                # composição real: exame normal + bloco
                dit = f"{gn[0]} com {gat[0]}"
                out, org = R.rotear(dit)
                if "não encontrado no banco" in out or f"{rel}/{nome[:-4]}" not in str(
                        [b[0] for b in R.achar_blocos([gat[0]], R.BANCO.meta.get(f'{rel}/normal'))]):
                    erros.append(f"{tag}: composição '{dit}' não usou este bloco ({org})")
                continue
            # máscara
            if nome.startswith("cronica"): n_cron += 1
            if nome.startswith("aguda"): n_agu += 1
            titulo = next((l for l in corpo if l.strip()), "")
            if not (titulo.startswith("**") and titulo.rstrip().endswith("**")):
                erros.append(f"{tag}: título deve ser **EM CAIXA ALTA E NEGRITO**")
            pos = []
            cabs = ["TÉCNICA", "ANÁLISE"] if rx else CABS
            if rx:
                for proibido in ("INDICAÇÃO CLÍNICA", "COMPARAÇÃO", "CONCLUSÃO"):
                    if f"**{proibido}:**" in txt:
                        erros.append(f"{tag}: radiografia não tem **{proibido}:**")
                analise = txt.split("**ANÁLISE:**")[-1]
                if re.search(r"^[^\W\d_][^:*]{0,40}:  \S", analise, re.M):
                    erros.append(f"{tag}: radiografia usa frases diretas, não 'Rótulo:  texto'")
            for c in cabs:
                i = txt.find(f"**{c}:**")
                if i < 0:
                    erros.append(f"{tag}: falta cabeçalho **{c}:**")
                pos.append(i)
            if all(p >= 0 for p in pos) and pos != sorted(pos):
                erros.append(f"{tag}: cabeçalhos fora da ordem {cabs}")
            if re.search(r"^- ", txt, re.M):
                erros.append(f"{tag}: linha com hífen — a ANÁLISE é 'Rótulo:  texto', sem hífen")
            if not rx and not re.search(r"^[^\W\d_][^:*]{0,70}:  \S", txt, re.M):
                erros.append(f"{tag}: linhas da ANÁLISE devem ser 'Rótulo:  texto' (dois espaços)")
            if not rx and "**INDICAÇÃO CLÍNICA:**  Em anexo." not in txt:
                erros.append(f"{tag}: INDICAÇÃO CLÍNICA deve ser 'Em anexo.'")
            conc = txt.split("**CONCLUSÃO:**")[-1]
            if re.search(r"^\s*\d+[.)]\s", conc, re.M):
                erros.append(f"{tag}: conclusão não se numera — um achado por linha")
            for g in gat[:3]:
                t, _x, sc = R.BANCO.buscar(R.normalizar(g), "mascara")
                if t != f"{rel}/{nome[:-4]}":
                    erros.append(f"{tag}: gatilho '{g}' roteia para {t}")
            if nome == "normal.txt" and not rx:
                concl = txt.split("**CONCLUSÃO:**")[-1]
                if not re.search(r"sem altera\w+ significativ|sem anormalidades", concl, re.I):
                    erros.append(f"{tag}: conclusão normal deve conter 'sem alterações significativas'")
        tc = "/tc/" in "/" + rel + "/" or "/angiotc/" in "/" + rel + "/"
        minimo_c, minimo_a, minimo_b, minimo_f = (2, 2, 4, 15) if tc else (1, 1, 3, 10)
        if n_cron < minimo_c: avisos.append(f"{rel}: só {n_cron} máscara(s) crônica(s) (mínimo {minimo_c})")
        if n_agu < minimo_a: avisos.append(f"{rel}: só {n_agu} máscara(s) aguda(s) (mínimo {minimo_a})")
        if n_blk < minimo_b: avisos.append(f"{rel}: só {n_blk} bloco(s) (mínimo {minimo_b})")
        if n_fr < minimo_f: avisos.append(f"{rel}: só {n_fr} frase(s) (mínimo {minimo_f})")
        print(f"  {rel}: normal + {n_cron} crônica(s) + {n_agu} aguda(s) + {n_blk} bloco(s) + {n_fr} frase(s)")

    for a in avisos: print("  AVISO:", a)
    for e in erros: print("  ERRO:", e)
    print(f"\n  {len(erros)} erro(s), {len(avisos)} aviso(s)")
    try: os.remove(base); os.remove(base + ".txt")
    except Exception: pass
    sys.exit(1 if erros else 0)

if __name__ == "__main__":
    main(sys.argv[1:] or ["."])

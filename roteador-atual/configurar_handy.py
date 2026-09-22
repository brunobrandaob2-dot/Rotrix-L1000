# -*- coding: utf-8 -*-
"""Configura o Handy para usar o Roteador de Laudos.

- Faz backup do settings_store.json antes de qualquer alteracao.
- Altera apenas as chaves necessarias; tudo o mais fica intacto.
- Escolhe o perfil de vocabulario conforme o modelo de STT em uso.
"""
import json, os, shutil, sys, datetime

AQUI = os.path.dirname(os.path.abspath(__file__))
SET = os.path.join(os.environ.get("APPDATA", ""), "com.pais.handy", "settings_store.json")
PORTA = 8123
ATALHO = "ctrl+alt+space"

def erro(msg):
    print("ERRO: " + msg); sys.exit(1)

if not os.path.exists(SET):
    erro("nao encontrei o Handy neste computador.\n"
         "       Esperava o arquivo: " + SET + "\n"
         "       Instale o Handy (handy.computer) e abra ao menos uma vez.")

backup = SET + ".backup-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
shutil.copy2(SET, backup)
print("backup salvo em: " + os.path.basename(backup))

s = json.load(open(SET, encoding="utf-8"))
st = s.setdefault("settings", {})

# --- atalho do roteador ---
b = st.setdefault("bindings", {})
alvo = b.setdefault("transcribe_with_post_process", {
    "id": "transcribe_with_post_process",
    "name": "Transcribe with Post-Processing",
    "description": "Converts your speech into text and applies AI post-processing.",
    "default_binding": "ctrl+shift+space"})
anterior = alvo.get("current_binding")
alvo["current_binding"] = ATALHO

# --- provider apontando para o roteador ---
provs = st.setdefault("post_process_providers", [])
custom = next((p for p in provs if p.get("id") == "custom"), None)
if custom is None:
    custom = {"id": "custom", "label": "Custom", "base_url": "",
              "models_endpoint": "/models", "allow_base_url_edit": True,
              "supports_structured_output": False}
    provs.append(custom)
custom["base_url"] = "http://127.0.0.1:%d/v1" % PORTA

st["post_process_provider_id"] = "custom"
st.setdefault("post_process_models", {})["custom"] = "laudo-router"
st.setdefault("post_process_api_keys", {})["custom"] = ""

prompts = [p for p in st.get("post_process_prompts", []) if p.get("id") != "roteador_local"]
prompts.append({"id": "roteador_local", "name": "Roteador local", "prompt": "${output}"})
st["post_process_prompts"] = prompts
st["post_process_selected_prompt_id"] = "roteador_local"
st["post_process_enabled"] = True

# --- idioma e higiene ---
st["selected_language"] = "pt"
if st.get("log_level") == "debug":
    st["log_level"] = "warn"

# --- vocabulario ---
# Base: o dicionario de radiologia do Bruno (pacote v8, handy/custom_words_radiologia.txt).
# Os termos do roteador que faltarem entram NA FRENTE da lista: com Whisper, o
# Handy usa a lista como prompt inicial e so o FIM dela cabe no prompt, entao
# acrescentar na frente nao muda o que o Whisper ve hoje.
lista_bruno = os.path.join(AQUI, "handy", "custom_words_radiologia.txt")
atuais = st.get("custom_words") or []
if os.path.exists(lista_bruno):
    base = [l.strip() for l in open(lista_bruno, encoding="utf-8") if l.strip()]
    vistos = {w.lower() for w in base}
    extras_atuais = [w for w in atuais if w.lower() not in vistos]
    for w in extras_atuais: vistos.add(w.lower())
    atuais = extras_atuais + base
else:
    vistos = {w.lower() for w in atuais}
voc = json.load(open(os.path.join(AQUI, "vocabularios.json"), encoding="utf-8"))
modelo = (st.get("selected_model") or "").lower()
perfil = "perfil_whisper" if "whisper" in modelo else "perfil_parakeet_cohere"
frente = [w for w in voc[perfil] if w.lower() not in vistos]
lista = frente + atuais
# Com WHISPER so o FIM da lista chega ao modelo: os termos que ele mais erra
# (handy/whisper_prioridade.txt) vao para o fim, na ordem do arquivo.
prio_p = os.path.join(AQUI, "handy", "whisper_prioridade.txt")
if os.path.exists(prio_p):
    prio = [l.strip() for l in open(prio_p, encoding="utf-8") if l.strip() and not l.startswith("#")]
    pset = {w.lower() for w in prio}
    lista = [w for w in lista if w.lower() not in pset] + prio
st["custom_words"] = lista
st["word_correction_threshold"] = 0.08

# --- mapa de regras do processador: o do pacote + o que so existe na maquina ---
# (regras aprendidas com APRENDER.ps1 ou acrescentadas a mao nao se perdem)
mapa_pkg = os.path.join(AQUI, "handy", "handy_radiology_map.tsv")
mapa_dst = os.path.join(os.environ.get("APPDATA", ""), "com.pais.handy", "handy_radiology_map.tsv")
if os.path.exists(mapa_pkg):
    pkg = open(mapa_pkg, encoding="utf-8").read().splitlines()
    chaves = {tuple(x.lower() for x in l.split("\t")[:2]) for l in pkg if l.count("\t") == 2}
    locais = []
    if os.path.exists(mapa_dst):
        for l in open(mapa_dst, encoding="utf-8").read().splitlines():
            if l.count("\t") == 2 and not l.startswith("#"):
                if tuple(x.lower() for x in l.split("\t")[:2]) not in chaves:
                    locais.append(l)
        shutil.copy2(mapa_dst, mapa_dst + ".backup-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S"))
    with open(mapa_dst, "w", encoding="utf-8") as f:
        f.write("\n".join(pkg) + "\n")
        if locais:
            f.write("\n# regras locais preservadas na atualizacao\n" + "\n".join(locais) + "\n")
    print("mapa de regras: %d do pacote + %d locais preservadas" % (len(chaves), len(locais)))

# --- processador de colagem: recompila quando o pacote traz versao nova ---
# (v10: o ditado sai com maiuscula no inicio e ponto final). So se ele ja
# esta instalado; se nao compilar, fica o anterior.
def _compilar_colador():
    if os.name != "nt":
        return False
    hd = os.path.join(os.environ.get("APPDATA", ""), "com.pais.handy")
    exe_c = os.path.join(hd, "handy_radiology_paste.exe")
    cs_pkg = os.path.join(AQUI, "handy", "handy_radiology_paste.cs")
    cs_dst = os.path.join(hd, "handy_radiology_paste.cs")
    if not (os.path.exists(exe_c) and os.path.exists(cs_pkg)):
        return False
    try:
        if os.path.exists(cs_dst) and open(cs_dst, "rb").read() == open(cs_pkg, "rb").read():
            return False                       # esta versao ja foi compilada
    except OSError:
        pass
    import subprocess
    novo = os.path.join(hd, "handy_radiology_paste.novo.exe")
    ps = ("$ErrorActionPreference='Stop'; "
          "if (Test-Path '{novo}') {{ Remove-Item '{novo}' -Force }}; "
          "Add-Type -Path '{cs}' -ReferencedAssemblies @('System.dll','System.Core.dll','System.Windows.Forms.dll') "
          "-OutputAssembly '{novo}' -OutputType WindowsApplication").format(novo=novo, cs=cs_pkg)
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps],
                           capture_output=True, text=True, timeout=180)
        if r.returncode != 0 or not os.path.exists(novo):
            print("  processador de colagem mantido (nao compilou): " + (r.stderr or r.stdout).strip()[:200])
            return False
        shutil.copy2(exe_c, os.path.join(hd, "handy_radiology_paste.anterior.exe"))
        os.replace(novo, exe_c)
        shutil.copy2(cs_pkg, cs_dst)
        print("  processador de colagem atualizado: maiuscula no inicio e ponto final")
        return True
    except Exception as e:
        print("  processador de colagem mantido: %s" % e)
        return False


_compilar_colador()       # nao muda se a colagem usa ou nao o processador

# --- colagem pelo processador de radiologia (v9), se o instalador compilou ---
exe = os.path.join(os.environ.get("APPDATA", ""), "com.pais.handy", "handy_radiology_paste.exe")
if os.environ.get("ROTEADOR_COLADOR_OK") == "1" and os.path.exists(exe):
    st["paste_method"] = "external_script"
    st["external_script_path"] = exe
    st["clipboard_handling"] = "dont_modify"
    colador = True
else:
    colador = st.get("paste_method") == "external_script" and os.path.exists(exe)

# o roteador so emite **negrito** quando o colador v9 esta ativo
cfg_p = os.path.join(AQUI, "config.json")
try:
    cfg = json.load(open(cfg_p, encoding="utf-8"))
except Exception:
    cfg = {}
cfg["formato_titulos"] = "rico" if colador and os.environ.get("ROTEADOR_COLADOR_OK") == "1" else cfg.get("formato_titulos", "texto")
cfg["processador_colagem"] = bool(colador)
json.dump(cfg, open(cfg_p, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

json.dump(s, open(SET, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

print("")
print("  modelo de STT detectado : " + (st.get("selected_model") or "(nenhum)"))
print("  vocabulario             : %d termos" % len(st["custom_words"]))
print("  colagem                 : " + ("processador de radiologia v9 (com negrito)" if colador else st.get("paste_method", "ctrl_v")))
if "whisper" in modelo:
    print("  ATENCAO: com Whisper o Handy usa o vocabulario como prompt e so os")
    print("           ultimos ~80 termos cabem. Veja o LEIA-ME, secao VOCABULARIO.")
print("  atalho do roteador      : %s  (antes: %s)" % (ATALHO, anterior))
print("  endereco do roteador    : http://127.0.0.1:%d/v1" % PORTA)
print("  idioma                  : pt")

# -*- coding: utf-8 -*-
"""Leitura do CABEÇALHO de arquivos DICOM, no próprio computador.

Por que existe: sem o Radius, quem baixa o exame é o navegador — e o arquivo
não vem com ficha nenhuma. Lendo o cabeçalho, a fila mostra "CT · TOMOGRAFIA
DE TORAX · 14:05" em vez de "pasta baixada por fora".

Regras (as mesmas da seção 17 da especificação, com a permissão que o Bruno deu
em 23/09/2026 para ler o cabeçalho):
- Só o cabeçalho, e só estas etiquetas: modalidade, descrição do estudo, data,
  hora, identificador do estudo e o nome — e o nome é convertido em INICIAIS
  na hora; o nome inteiro nunca é guardado nem devolvido.
- A imagem (PixelData) nunca é lida: a leitura para antes.
- Nada daqui vai para a IA, para log ou para qualquer lugar fora do computador.
"""
import os
import re
import struct
import zipfile

# etiquetas que interessam (grupo, elemento)
T_MODALIDADE = (0x0008, 0x0060)
T_DESCRICAO = (0x0008, 0x1030)
T_SERIE = (0x0008, 0x103E)
T_DATA = (0x0008, 0x0020)
T_HORA = (0x0008, 0x0030)
T_NOME = (0x0010, 0x0010)
T_UID = (0x0020, 0x000D)
T_TRANSFER = (0x0002, 0x0010)
DESEJADAS = {T_MODALIDADE, T_DESCRICAO, T_SERIE, T_DATA, T_HORA, T_NOME, T_UID}

# depois deste grupo já passou de tudo que interessa (a imagem é 7FE0)
_GRUPO_LIMITE = 0x0021
_VR_COM_TAMANHO_LONGO = {b"OB", b"OW", b"OF", b"SQ", b"UT", b"UN"}
_CABECALHO_MAX = 512 * 1024      # nunca lê mais que isso de um arquivo
_ARQUIVOS_POR_PASTA = 400        # onde parar de procurar um .dcm na pasta
_DENTRO_DO_ZIP = 8 * 1024 * 1024  # um .dcm maior que isso não é lido do zip

_EH_DCM = re.compile(r"\.(?:dcm|dicom|ima)$|^dicomdir$", re.I)


def _texto(bruto):
    try:
        s = bruto.decode("latin-1")
    except Exception:
        return ""
    return s.replace("\x00", "").strip()


def _ler_elementos(dados, explicito, inicio=0):
    """Percorre os elementos e devolve {(grupo, elemento): bytes}."""
    achados = {}
    i = inicio
    n = len(dados)
    while i + 8 <= n:
        grupo, elem = struct.unpack_from("<HH", dados, i)
        if grupo == 0 or grupo > _GRUPO_LIMITE:
            break
        i += 4
        if explicito:
            vr = dados[i:i + 2]
            i += 2
            if vr in _VR_COM_TAMANHO_LONGO:
                i += 2
                if i + 4 > n:
                    break
                (tam,) = struct.unpack_from("<I", dados, i)
                i += 4
            else:
                if i + 2 > n:
                    break
                (tam,) = struct.unpack_from("<H", dados, i)
                i += 2
        else:
            if i + 4 > n:
                break
            (tam,) = struct.unpack_from("<I", dados, i)
            i += 4
        if tam == 0xFFFFFFFF:        # tamanho indefinido (sequência): para aqui
            break
        if tam < 0 or i + tam > n:
            break
        if (grupo, elem) in DESEJADAS:
            achados[(grupo, elem)] = dados[i:i + tam]
        i += tam
    return achados


def _do_bloco(dados):
    """Cabeçalho a partir dos primeiros bytes de um arquivo DICOM."""
    if len(dados) < 140:
        return {}
    if dados[128:132] == b"DICM":
        meta = _ler_elementos(dados, True, 132)
        sintaxe = _texto(meta.get(T_TRANSFER, b""))
        explicito = not sintaxe.startswith("1.2.840.10008.1.2\x00") and sintaxe != "1.2.840.10008.1.2"
        # o grupo 0002 é sempre explícito; o resto segue a sintaxe declarada
        corpo = _ler_elementos(dados, explicito, _fim_do_meta(dados))
        achados = dict(meta)
        achados.update(corpo)
        return achados
    for explicito in (True, False):  # arquivo sem preâmbulo
        achados = _ler_elementos(dados, explicito, 0)
        if achados:
            return achados
    return {}


def _fim_do_meta(dados):
    """Começo do conjunto de dados: 132 + tamanho declarado em (0002,0000)."""
    try:
        meta = _ler_elementos(dados[:4096], True, 132)
        bruto = meta.get((0x0002, 0x0000))
        if bruto and len(bruto) >= 4:
            (tam,) = struct.unpack_from("<I", bruto, 0)
            # 132 + (tag+VR+len do 0002,0000 = 12) + tamanho do restante do meta
            return min(len(dados), 132 + 12 + tam)
    except Exception:
        pass
    return 132


def _iniciais(nome):
    from radius import iniciais  # o mesmo critério da fila
    return iniciais(nome)


def _nome(nome):
    from radius import nome_paciente  # o mesmo critério da fila
    return nome_paciente(nome)


def _arrumar(achados):
    if not achados:
        return {}
    data = _texto(achados.get(T_DATA, b""))
    hora = _texto(achados.get(T_HORA, b""))
    quando = ""
    if re.match(r"^\d{8}$", data):
        h = re.match(r"^(\d{2})(\d{2})(\d{2})", hora)
        quando = "%s-%s-%sT%s" % (data[:4], data[4:6], data[6:8],
                                  "%s:%s:%s" % h.groups() if h else "00:00:00")
    return {
        "modalidade": _texto(achados.get(T_MODALIDADE, b""))[:8].upper(),
        "descricao": (_texto(achados.get(T_DESCRICAO, b""))
                      or _texto(achados.get(T_SERIE, b"")))[:80],
        "entrou": quando,
        "iniciais": _iniciais(_texto(achados.get(T_NOME, b""))),
        # nome inteiro, só para a tela dele — mesma regra da fila (ver
        # radius.nome_paciente). PixelData continua sem ser lido.
        "nome": _nome(_texto(achados.get(T_NOME, b""))),
        "uid": _texto(achados.get(T_UID, b""))[:64],
    }


def do_arquivo(caminho):
    """Cabeçalho de um .dcm no disco (lê no máximo 512 KB do começo)."""
    try:
        with open(caminho, "rb") as f:
            return _arrumar(_do_bloco(f.read(_CABECALHO_MAX)))
    except OSError:
        return {}


def do_zip(caminho):
    """Primeiro .dcm de dentro de um .zip, sem gravar nada em disco."""
    try:
        with zipfile.ZipFile(caminho) as z:
            nomes = [n for n in z.namelist()
                     if not n.endswith("/") and _EH_DCM.search(os.path.basename(n))]
            if not nomes:
                # alguns portais gravam o DICOM sem extensão nenhuma
                nomes = [n for n in z.namelist()
                         if not n.endswith("/") and z.getinfo(n).file_size >= 140][:5]
            for n in nomes[:5]:
                if z.getinfo(n).file_size > _DENTRO_DO_ZIP:
                    continue
                with z.open(n) as f:
                    d = _arrumar(_do_bloco(f.read(_CABECALHO_MAX)))
                if d.get("modalidade") or d.get("uid"):
                    return d
    except (zipfile.BadZipFile, OSError, KeyError, RuntimeError):
        return {}
    return {}


def da_pasta(pasta):
    """Procura o primeiro DICOM da pasta (ou de uma subpasta) e lê o cabeçalho."""
    vistos = 0
    for raiz, dirs, arquivos in os.walk(pasta):
        dirs[:] = sorted(dirs)[:20]
        for a in sorted(arquivos):
            vistos += 1
            if vistos > _ARQUIVOS_POR_PASTA:
                return {}
            if _EH_DCM.search(a):
                d = do_arquivo(os.path.join(raiz, a))
                if d.get("modalidade") or d.get("uid"):
                    return d
            elif a.lower().endswith(".zip"):
                d = do_zip(os.path.join(raiz, a))
                if d.get("modalidade") or d.get("uid"):
                    return d
    return {}


def de(caminho):
    """Cabeçalho de um exame, seja ele pasta, .dcm ou .zip."""
    if os.path.isdir(caminho):
        return da_pasta(caminho)
    if caminho.lower().endswith(".zip"):
        return do_zip(caminho)
    return do_arquivo(caminho)

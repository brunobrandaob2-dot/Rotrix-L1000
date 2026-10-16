#!/usr/bin/env bash
# Roda EXATAMENTE o que o GitHub roda em "Validar máscaras".
#
# Existe porque validar só as regiões que eu mexi não basta: o CI valida as 66,
# e uma máscara escrita semanas atrás pode estar errada sem ninguém ter olhado.
# Foi assim que a conclusão da angioTC de coronárias passou batida até o CI.
set -e
cd "$(dirname "$0")"
export LAUDO_BASE=/tmp/val_base.sqlite LAUDO_CATALOGO=/tmp/val_catalogo.txt
# o mesmo filtro do build do instalador ("nada pessoal no instalador"): texto com cara
# de chave de API derruba o .exe. 16/10: uma chave FALSA num teste derrubou o build.
echo "conferindo chave escrita em arquivo (mesmo filtro do build do .exe)..."
achou=$(grep -rnoE --include=*.py --include=*.json --include=*.txt --include=*.md --include=*.tsv --include=*.ps1 \
        'sk-[A-Za-z0-9_\-]{20,}|AIza[0-9A-Za-z_\-]{30,}' . | grep -vE 'SEGREDO|EXEMPLO|TESTE|FAKE|XXXX' || true)
if [ -n "$achou" ]; then echo "PAROU: o build do .exe vai recusar:"; echo "$achou"; exit 1; fi
echo "  nenhuma"
# o Python 3.13 do PC dele avisa escape inválido em string (SyntaxWarning)
for f in *.py; do python3 -W error::SyntaxWarning -c "import ast,sys; ast.parse(open(sys.argv[1],encoding='utf-8').read())" "$f" >/dev/null 2>&1 \
  || echo "  AVISO: escape inválido em $f"; done
python3 construir_base.py
regioes=$(find dados/mascaras -name normal.txt -printf '%h\n' | sort)
echo "validando $(echo "$regioes" | wc -l) regiões..."
python3 validar_regiao.py $regioes | tee /tmp/validacao.txt | grep -E "ERRO|erro\(s\)" || true
echo "conferindo o prompt de sistema (REDATOR_ROTRIX.md)..."
python3 prompts.py
echo "auditando frase quebrada no banco..."
python3 auditar_frases.py | head -4
echo "auditando gatilhos..."
python3 auditar_gatilhos.py | tail -3
for t in testar_nuvem.py testar_sinonimos.py testar_perf_roteador.py testar_tecnica_rx.py testar_importar.py testar_rx_literal.py testar_radius.py \
         testar_tc_literal.py testar_estacao.py testar_v2.py testar_conferir_usuario.py testar_lado_bilateral.py testar_ia_modelos.py testar_tempo_nuvem.py testar_versao.py testar_lista_rapida.py testar_juntar_rotulos.py testar_local_ditado.py testar_imagem_ia.py testar_lyon.py testar_raciocinio.py testar_coluna_hernias.py testar_gatilhos_trancas.py testar_bloqueio.py testar_mesclar_tsv.py testar_ler_print.py testar_mascaras_editar.py testar_fase1.py; do
  printf "%-24s " "$t"
  python3 "$t" 2>&1 | tail -1
done

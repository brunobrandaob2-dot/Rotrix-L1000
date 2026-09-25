#!/usr/bin/env bash
# Roda EXATAMENTE o que o GitHub roda em "Validar máscaras".
#
# Existe porque validar só as regiões que eu mexi não basta: o CI valida as 66,
# e uma máscara escrita semanas atrás pode estar errada sem ninguém ter olhado.
# Foi assim que a conclusão da angioTC de coronárias passou batida até o CI.
set -e
cd "$(dirname "$0")"
export LAUDO_BASE=/tmp/val_base.sqlite LAUDO_CATALOGO=/tmp/val_catalogo.txt
python3 construir_base.py
regioes=$(find dados/mascaras -name normal.txt -printf '%h\n' | sort)
echo "validando $(echo "$regioes" | wc -l) regiões..."
python3 validar_regiao.py $regioes | tee /tmp/validacao.txt | grep -E "ERRO|erro\(s\)" || true
echo "conferindo o prompt de sistema (REDATOR_ROTRIX.md)..."
python3 prompts.py
echo "auditando gatilhos..."
python3 auditar_gatilhos.py | tail -3
for t in testar_nuvem.py testar_sinonimos.py testar_perf_roteador.py testar_tecnica_rx.py testar_importar.py testar_rx_literal.py testar_radius.py \
         testar_tc_literal.py testar_estacao.py testar_v2.py; do
  printf "%-24s " "$t"
  python3 "$t" 2>&1 | tail -1
done

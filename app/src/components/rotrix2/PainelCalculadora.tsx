/* eslint-disable i18next/no-literal-string */
// Rotrix L-1000 — painel das calculadoras novas (adrenal, esteatose, VDT, Evans,
// NASCET), aberto pelo botão Cálculos. A conta é a de calculadoras.ts: local, ao
// vivo, sem IA. "Pôr na folha" usa o mesmo aoInserir dos outros painéis.
import React, { useMemo, useState } from "react";
import { X } from "lucide-react";
import { Button } from "../ui/Button";
import type { Calculadora, Tom, Valores } from "./calculadoras";

const COR: Record<Tom, string> = {
  verde: "border-emerald-500/50 bg-emerald-500/10 text-emerald-300",
  amarelo: "border-amber-400/50 bg-amber-100/10 text-amber-300",
  vermelho: "border-red-500/50 bg-red-500/10 text-red-300",
  cinza: "border-mid-gray/30 bg-mid-gray/10 text-mid-gray",
};

const iniciais = (calc: Calculadora, v?: Valores): Valores => {
  const out: Valores = {};
  for (const c of calc.campos)
    if (c.tipo === "opcoes" && c.opcoes?.length) out[c.id] = c.opcoes[0];
  return { ...out, ...(v || {}) };
};

export const PainelCalculadora: React.FC<{
  calc: Calculadora;
  inicial?: Valores;
  aoInserir: (t: string) => void;
  aoFechar: () => void;
}> = ({ calc, inicial, aoInserir, aoFechar }) => {
  const [valores, setValores] = useState<Valores>(() =>
    iniciais(calc, inicial),
  );
  const preenchido = calc.campos.some(
    (c) => c.tipo !== "opcoes" && (valores[c.id] || "").trim() !== "",
  );
  const r = useMemo(
    () => (preenchido ? calc.calcular(valores) : null),
    [calc, valores, preenchido],
  );
  const trocar = (k: string, v: string) =>
    setValores((x) => ({ ...x, [k]: v }));

  return (
    <div className="flex flex-col h-full min-h-0">
      <div className="flex items-center gap-2 px-3 py-2 border-b border-mid-gray/20">
        <span className="text-[12.5px] font-semibold">{calc.nome}</span>
        <span className="text-[10px] text-mid-gray truncate">
          {calc.resumo}
        </span>
        <button
          type="button"
          onClick={aoFechar}
          className="ms-auto p-1 rounded hover:bg-mid-gray/20 cursor-pointer"
          title="fechar"
        >
          <X size={14} />
        </button>
      </div>

      <div className="flex-1 min-h-0 overflow-y-auto p-3 space-y-3">
        {inicial && Object.keys(inicial).length > 0 && (
          <div className="text-[10.5px] rounded-lg border border-logo-primary/40 bg-logo-primary/10 px-2.5 py-1.5">
            preenchida com os números da folha · confira antes de pôr
          </div>
        )}
        <div className="grid grid-cols-2 gap-2">
          {calc.campos.map((c) =>
            c.tipo === "opcoes" ? (
              <div key={c.id} className="col-span-2">
                <div className="text-[10px] text-mid-gray mb-0.5">
                  {c.rotulo}
                </div>
                <div className="flex gap-1.5">
                  {(c.opcoes || []).map((o) => (
                    <button
                      key={o}
                      type="button"
                      onClick={() => trocar(c.id, o)}
                      className={`text-[10.5px] px-2.5 py-1 rounded-md border cursor-pointer ${
                        valores[c.id] === o
                          ? "border-logo-primary/60 bg-logo-primary/25 font-bold"
                          : "border-mid-gray/25 hover:bg-mid-gray/15"
                      }`}
                    >
                      {o}
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              <label key={c.id} className="flex flex-col gap-0.5 min-w-0">
                <span
                  className="text-[10px] text-mid-gray truncate"
                  title={c.rotulo}
                >
                  {c.rotulo}
                  {c.unidade ? ` (${c.unidade})` : ""}
                </span>
                <input
                  type={c.tipo === "data" ? "date" : "text"}
                  value={valores[c.id] || ""}
                  onChange={(e) => trocar(c.id, e.target.value)}
                  inputMode={c.tipo === "data" ? undefined : "decimal"}
                  className="h-7 min-w-0 rounded-lg border border-mid-gray/25 bg-background px-2 text-[12px]"
                />
              </label>
            ),
          )}
        </div>

        {r?.erro && (
          <div className="text-[11px] rounded-lg border border-amber-400/40 bg-amber-100/10 text-amber-300 px-2.5 py-2">
            {r.erro}
          </div>
        )}

        {r && !r.erro && (
          <>
            <div className="border-t border-mid-gray/20 pt-2 space-y-1.5">
              <div className="text-[13px] font-bold">{r.principal}</div>
              {r.categoria && (
                <div
                  className={`text-[11px] rounded-md border px-2 py-1 inline-block ${COR[r.categoria.tom]}`}
                >
                  {r.categoria.texto}
                </div>
              )}
              {r.conta && (
                <div className="text-[10px] text-mid-gray">{r.conta}</div>
              )}
            </div>
            {r.frase && (
              <div className="rounded-lg papel p-3 text-[11.5px] leading-[1.55]">
                {r.frase}
              </div>
            )}
          </>
        )}

        <div className="text-[10px] text-mid-gray leading-snug">
          {calc.referencia}
        </div>
      </div>

      <div className="flex gap-2 px-3 py-2 border-t border-mid-gray/20">
        <Button
          variant="primary"
          size="sm"
          disabled={!r?.frase}
          onClick={() => {
            if (r?.frase) {
              aoInserir(r.frase);
              aoFechar();
            }
          }}
        >
          Pôr na folha
        </Button>
        <Button
          variant="secondary"
          size="sm"
          onClick={() => setValores(iniciais(calc, calc.exemplo))}
        >
          Exemplo
        </Button>
        <Button
          variant="secondary"
          size="sm"
          onClick={() => setValores(iniciais(calc))}
        >
          Limpar
        </Button>
      </div>
    </div>
  );
};

export default PainelCalculadora;

/* eslint-disable i18next/no-literal-string */
// Rotrix L-1000: primeiros passos. O que falta para o Rotrix ficar pronto
// nesta máquina. Some sozinho quando está tudo certo.
import React, { useCallback, useEffect, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { SettingsGroup } from "../../ui/SettingsGroup";
import { Button } from "../../ui/Button";
import { dica, useAtalho } from "../../../lib/utils/atalhos";

interface Passos {
  roteador: boolean;
  modelo: boolean;
  radius: boolean;
  chave_ia: boolean;
  mascaras: number;
}

const LINHAS: { chave: keyof Passos; texto: string; ajuda: string; obrigatorio: boolean }[] = [
  {
    chave: "roteador",
    texto: "Roteador de laudos no ar",
    ajuda: "Sobe junto com o app. Se ficar vermelho, feche e abra o Rotrix.",
    obrigatorio: true,
  },
  {
    chave: "modelo",
    texto: "Modelo de voz escolhido",
    ajuda: "Escolha em Ditado, aqui embaixo.",
    obrigatorio: true,
  },
  {
    chave: "radius",
    texto: "Pasta do Radius encontrada",
    ajuda: "Só para a fila e o exame da vez. Sem ela, o resto funciona igual.",
    obrigatorio: false,
  },
  {
    chave: "chave_ia",
    texto: "Chave de IA guardada",
    ajuda: "Opcional: só para revisar, analisar e formar laudo com IA.",
    obrigatorio: false,
  },
];

export const RotrixPrimeirosPassos: React.FC = () => {
  const [p, setP] = useState<Passos | null>(null);
  const [mostrar, setMostrar] = useState(false);

  const ler = useCallback(async () => {
    try {
      const r = await invoke<Passos>("rotrix_primeiros_passos");
      setP(r);
    } catch {
      setP(null);
    }
  }, []);

  useEffect(() => {
    void ler();
  }, [ler]);

  useAtalho("p", () => {
    setMostrar((x) => !x);
    void ler();
  });

  if (!p) return null;
  const faltando = LINHAS.filter((l) => l.obrigatorio && !p[l.chave]).length;
  if (faltando === 0 && !mostrar) return null;

  return (
    <SettingsGroup
      title="Primeiros passos"
      description={
        faltando === 0
          ? "Está tudo pronto nesta máquina."
          : "Falta pouco para o Rotrix ficar pronto nesta máquina."
      }
    >
      <div className="px-4 py-3">
        <ul className="flex flex-col gap-2 text-sm">
          {LINHAS.map((l) => {
            const ok = Boolean(p[l.chave]);
            return (
              <li key={l.chave} className="flex items-start gap-3">
                <span className="w-4 shrink-0 text-center" aria-label={ok ? "pronto" : "falta"}>
                  {ok ? "✓" : l.obrigatorio ? "•" : "○"}
                </span>
                <span className="flex-1 min-w-0">
                  {l.texto}
                  {!l.obrigatorio && <span className="text-xs text-mid-gray"> · opcional</span>}
                  <span className="block text-xs text-mid-gray">{l.ajuda}</span>
                </span>
              </li>
            );
          })}
          <li className="flex items-start gap-3">
            <span className="w-4 shrink-0 text-center">{p.mascaras > 0 ? "✓" : "•"}</span>
            <span className="flex-1 min-w-0">
              Banco de máscaras
              <span className="block text-xs text-mid-gray">
                {p.mascaras > 0 ? `${p.mascaras} gatilhos prontos.` : "ainda gerando…"}
              </span>
            </span>
          </li>
        </ul>
        <div className="mt-3 flex gap-2">
          <Button variant="secondary" size="sm" title={dica("Conferir de novo", "p")} onClick={() => void ler()}>
            Conferir de novo
          </Button>
        </div>
      </div>
    </SettingsGroup>
  );
};

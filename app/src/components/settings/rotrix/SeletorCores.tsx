/* eslint-disable i18next/no-literal-string */
// Rotrix L-1000: escolha da cor do app, a qualquer hora (paletas prontas ou
// uma cor livre). Usado no botão "Cores" da barra lateral e na página Rotrix.
import React, { useEffect, useState } from "react";
import { emit } from "@tauri-apps/api/event";
import {
  EVENTO_PALETA,
  ID_LIVRE,
  PALETAS,
  aplicarPaleta,
  getPaletaSalva,
  paletaDe,
  salvarPaleta,
  type EscolhaPaleta,
} from "../../../lib/utils/paleta";

const EVENTO_LOCAL = "rotrix-paleta";

/** Aplica, guarda e avisa as outras janelas (barra de gravação) e seletores. */
export const escolherPaleta = (e: EscolhaPaleta): void => {
  aplicarPaleta(e);
  salvarPaleta(e);
  window.dispatchEvent(new Event(EVENTO_LOCAL));
  emit(EVENTO_PALETA, e).catch(() => {
    // outra janela aberta depois lê a escolha guardada
  });
};

interface SeletorCoresProps {
  mostrarNome?: boolean;
}

export const SeletorCores: React.FC<SeletorCoresProps> = ({ mostrarNome = true }) => {
  const [atual, setAtual] = useState<EscolhaPaleta>(getPaletaSalva());
  const [livre, setLivre] = useState<string>(
    atual.id === ID_LIVRE && atual.cor ? atual.cor : "#82aee6",
  );

  useEffect(() => {
    const sincronizar = () => setAtual(getPaletaSalva());
    window.addEventListener(EVENTO_LOCAL, sincronizar);
    return () => window.removeEventListener(EVENTO_LOCAL, sincronizar);
  }, []);

  const escolher = (e: EscolhaPaleta) => {
    escolherPaleta(e);
    setAtual(e);
  };

  const livreAtiva = atual.id === ID_LIVRE;

  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex flex-wrap items-center gap-2" role="radiogroup" aria-label="Cor do app">
        {PALETAS.map((p) => {
          const sel = atual.id === p.id;
          return (
            <button
              key={p.id}
              type="button"
              role="radio"
              aria-checked={sel}
              aria-label={p.nome}
              title={`${p.nome}: ${p.descricao}`}
              onClick={() => escolher({ id: p.id })}
              className={`w-7 h-7 rounded-full border-2 cursor-pointer transition-transform hover:scale-110 ${
                sel ? "border-text" : "border-mid-gray/30"
              }`}
              style={{
                background: `linear-gradient(135deg, ${p.escuro.bg} 0 50%, ${p.escuro.ac} 50% 100%)`,
              }}
            />
          );
        })}
        <label
          title="Cor livre: escolha qualquer cor"
          className={`relative w-7 h-7 rounded-full border-2 cursor-pointer overflow-hidden transition-transform hover:scale-110 ${
            livreAtiva ? "border-text" : "border-mid-gray/30"
          }`}
          style={{
            background: livreAtiva
              ? livre
              : "conic-gradient(#e35d5d, #e3c35d, #62d392, #5cc8ba, #82aee6, #b58be6, #e35d5d)",
          }}
        >
          <input
            type="color"
            aria-label="Cor livre"
            value={livre}
            onChange={(ev) => {
              setLivre(ev.target.value);
              escolher({ id: ID_LIVRE, cor: ev.target.value });
            }}
            className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
          />
        </label>
      </div>
      {mostrarNome && (
        <span className="text-xs text-mid-gray">
          {paletaDe(atual).nome}
          {livreAtiva ? ` · ${livre}` : ""}
        </span>
      )}
    </div>
  );
};

/* eslint-disable i18next/no-literal-string */
// Rotrix L-1000 v2 — mostrar texto de laudo do jeito que ele é.
//
// As máscaras são guardadas com as marcas que o colador usa: **TÉCNICA:** vira
// negrito na hora de colar, e {lado} é lacuna que o ditado preenche. Mostrar o
// arquivo cru na tela enche tudo de asterisco. Aqui as marcas viram negrito e
// as lacunas ficam destacadas.
import React from "react";

const PEDACO = /(\{[^{}\n]{0,60}\})/g;

/** Uma linha: **negrito** vira negrito, {lacuna} fica marcada. */
const linha = (texto: string, chave: React.Key): React.ReactNode => {
  if (!texto) return <br key={chave} />;
  const partes = texto.split("**");
  return (
    <div key={chave}>
      {partes.map((parte, i) => {
        const conteudo = parte.split(PEDACO).map((p, j) =>
          PEDACO.test(p) ? (
            <span
              key={j}
              className="rounded bg-amber-400/25 text-amber-900 px-0.5"
              title="lacuna: o ditado preenche"
            >
              {p}
            </span>
          ) : (
            <React.Fragment key={j}>{p}</React.Fragment>
          ),
        );
        return i % 2 === 1 ? (
          <b key={i}>{conteudo}</b>
        ) : (
          <React.Fragment key={i}>{conteudo}</React.Fragment>
        );
      })}
    </div>
  );
};

export const TextoDeLaudo: React.FC<{
  texto: string;
  className?: string;
}> = ({ texto, className = "" }) => (
  <div className={`whitespace-pre-wrap break-words ${className}`}>
    {(texto || "").replace(/\r\n?/g, "\n").split("\n").map((l, i) => linha(l, i))}
  </div>
);

export default TextoDeLaudo;

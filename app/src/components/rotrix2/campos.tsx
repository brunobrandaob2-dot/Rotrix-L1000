// Rotrix v2, fase 6: os campos de formulário do Painel e do Aparelho, sobre o
// Astryx. O rótulo visível fica na linha (Linha/label da tela); aqui o rótulo
// vai só para o leitor de tela (isLabelHidden).
import React from "react";
import { TextInput } from "@astryxdesign/core/TextInput";
import { TextArea } from "@astryxdesign/core/TextArea";
import { Selector } from "@astryxdesign/core/Selector";
import { Switch } from "@astryxdesign/core/Switch";
import { Slider } from "@astryxdesign/core/Slider";
import { NumberInput } from "@astryxdesign/core/NumberInput";

// o Selector trata "" como "nada escolhido"; a opção vazia ganha um valor seu
const VAZIO = "__vazio__";
const ida = (v: string): string => (v === "" ? VAZIO : v);
const volta = (v: string): string => (v === VAZIO ? "" : v);

export type Opcao = { value: string; label: string; description?: string; disabled?: boolean };
export type Secao = { type: "section"; title: string; options: Opcao[] };

export const CampoTexto: React.FC<{
  rotulo: string;
  valor: string;
  aoMudar: (v: string) => void;
  max?: number;
  dica?: string;
}> = ({ rotulo, valor, aoMudar, max, dica }) => (
  <TextInput
    label={rotulo}
    isLabelHidden
    size="sm"
    width="100%"
    value={valor}
    placeholder={dica}
    onChange={(v) => aoMudar(max ? v.slice(0, max) : v)}
  />
);

export const CampoArea: React.FC<{
  rotulo: string;
  valor: string;
  aoMudar: (v: string) => void;
  linhas?: number;
}> = ({ rotulo, valor, aoMudar, linhas = 3 }) => (
  <TextArea label={rotulo} isLabelHidden size="sm" width="100%" rows={linhas} value={valor} onChange={(v) => aoMudar(v)} />
);

export const CampoLista: React.FC<{
  rotulo: string;
  valor: string;
  aoMudar: (v: string) => void;
  opcoes: (Opcao | Secao)[];
}> = ({ rotulo, valor, aoMudar, opcoes }) => (
  <Selector
    label={rotulo}
    isLabelHidden
    size="sm"
    width="100%"
    value={ida(valor)}
    onChange={(v) => v != null && aoMudar(volta(v))}
    options={opcoes.map((o) =>
      "type" in o
        ? { ...o, options: o.options.map((x) => ({ ...x, value: ida(x.value) })) }
        : { ...o, value: ida(o.value) },
    )}
  />
);

export const CampoLiga: React.FC<{ rotulo: string; valor: boolean; aoMudar: (v: boolean) => void }> = ({
  rotulo,
  valor,
  aoMudar,
}) => <Switch label={rotulo} isLabelHidden size="sm" value={valor} onChange={(v) => aoMudar(v)} />;

export const CampoBarra: React.FC<{
  rotulo: string;
  valor: number;
  aoMudar: (v: number) => void;
  min: number;
  max: number;
  passo?: number;
}> = ({ rotulo, valor, aoMudar, min, max, passo = 1 }) => (
  <div className="flex-1 min-w-[140px]">
    <Slider
      label={rotulo}
      isLabelHidden
      width="100%"
      value={valor}
      min={min}
      max={max}
      step={passo}
      onChange={(v: number) => aoMudar(v)}
    />
  </div>
);

export const CampoNumero: React.FC<{
  rotulo: string;
  valor: number;
  aoMudar: (v: number) => void;
  min: number;
  max: number;
  passo?: number;
  largura?: number;
}> = ({ rotulo, valor, aoMudar, min, max, passo = 1, largura = 110 }) => (
  <NumberInput
    label={rotulo}
    isLabelHidden
    size="sm"
    width={largura}
    value={valor}
    min={min}
    max={max}
    step={passo}
    onChange={(v) => aoMudar(Math.max(min, Math.min(max, Number(v) || 0)))}
  />
);

/** [id, nome] -> opções do Selector */
export const deParas = (pares: [string, string][]): Opcao[] => pares.map(([value, label]) => ({ value, label }));

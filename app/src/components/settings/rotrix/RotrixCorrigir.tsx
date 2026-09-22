/* eslint-disable i18next/no-literal-string */
// Rotrix L-1000: a caixa de correção. O que você escreveria para o suporte,
// escreve aqui e vale no próximo ditado: grafia que o reconhecimento erra,
// frase que não deve sair, frase que deve sair sempre. Cada regra tem desfazer.
import React, { useCallback, useEffect, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { SettingsGroup } from "../../ui/SettingsGroup";
import { SettingContainer } from "../../ui/SettingContainer";
import { Button } from "../../ui/Button";
import { Textarea } from "../../ui/Textarea";
import { ToggleSwitch } from "../../ui/ToggleSwitch";
import { dica, useAtalho } from "../../../lib/utils/atalhos";

interface Regra {
  id: string;
  tipo: string;
  quando?: string;
  pedido?: string;
  errado?: string;
  certo?: string;
  frase?: string;
  escopo?: string;
  texto?: string;
  por_ia?: boolean;
}

const COMO: Record<string, (r: Regra) => string> = {
  ouvido: (r) => `escrever “${r.certo}” no lugar de “${r.errado}”`,
  tirar: (r) => `não escrever “${r.frase}”${r.escopo ? ` (só em ${r.escopo})` : ""}`,
  acrescentar: (r) => `escrever sempre “${r.frase}”${r.escopo ? ` (só em ${r.escopo})` : ""}`,
  nota: (r) => `anotado para depois: “${(r.texto ?? r.pedido ?? "").slice(0, 120)}”`,
};

const descrever = (r: Regra): string => (COMO[r.tipo] ?? ((x: Regra) => x.tipo))(r);

const EXEMPLOS = [
  "risartrose, o certo é rizartrose",
  "não escrever Partes moles sem alterações no raio x de punho",
  "sempre escrever Sem sinais de pneumotórax no raio x de tórax",
];

export const RotrixCorrigir: React.FC = () => {
  const [texto, setTexto] = useState("");
  const [usarIa, setUsarIa] = useState(false);
  const [regras, setRegras] = useState<Regra[]>([]);
  const [mensagem, setMensagem] = useState("");
  const [ocupado, setOcupado] = useState(false);

  const listar = useCallback(async () => {
    try {
      const txt = await invoke<string>("rotrix_correcao_listar");
      const r = JSON.parse(txt) as { ok: boolean; regras?: Regra[] };
      setRegras(r.regras ?? []);
    } catch {
      setRegras([]);
    }
  }, []);

  useEffect(() => {
    void listar();
  }, [listar]);

  const aplicar = useCallback(async () => {
    if (texto.trim().length < 4 || ocupado) return;
    setOcupado(true);
    setMensagem("Aplicando…");
    try {
      const txt = await invoke<string>("rotrix_correcao_aplicar", {
        texto,
        laudo: "",
        usarIa,
      });
      const r = JSON.parse(txt) as { ok: boolean; acoes?: Regra[]; motivo?: string };
      if (!r.ok) {
        setMensagem("Não consegui: " + (r.motivo ?? ""));
      } else {
        const feitas = r.acoes ?? [];
        setMensagem(
          feitas.length === 0
            ? "Nada mudou."
            : "Pronto: " + feitas.map(descrever).join("; ") + ". Vale já no próximo ditado.",
        );
        setTexto("");
      }
      await listar();
    } catch (e) {
      setMensagem("Não consegui: " + String(e));
    } finally {
      setOcupado(false);
    }
  }, [texto, usarIa, ocupado, listar]);

  const desfazer = async (id: string) => {
    try {
      await invoke("rotrix_correcao_desfazer", { id });
      setMensagem("Regra desfeita.");
      await listar();
    } catch (e) {
      setMensagem("Não consegui desfazer: " + String(e));
    }
  };

  useAtalho("c", () => void aplicar());

  return (
    <SettingsGroup
      title="Corrigir"
      description="Escreva do jeito que você me contaria. A correção entra no roteador na hora, sem passar por ninguém."
    >
      <div className="px-4 pt-3 pb-1">
        <Textarea
          className="w-full"
          value={texto}
          rows={3}
          maxLength={600}
          placeholder={EXEMPLOS.join("\n")}
          onChange={(e) => setTexto(e.target.value)}
        />
      </div>
      <SettingContainer
        title="Aplicar"
        description="Grafia, frase que sai e frase que entra são aplicadas sozinhas. O resto fica anotado."
        grouped={true}
      >
        <Button
          variant="primary"
          size="sm"
          disabled={ocupado || texto.trim().length < 4}
          title={dica("Aplicar a correção", "c")}
          onClick={() => void aplicar()}
        >
          Aplicar
        </Button>
      </SettingContainer>
      <ToggleSwitch
        label="Pedir ajuda da IA quando eu não for claro"
        description="Só o seu texto de correção sai do computador; laudo e nome de paciente nunca."
        descriptionMode="inline"
        grouped={true}
        checked={usarIa}
        onChange={setUsarIa}
      />
      {mensagem !== "" && <div className="px-4 pb-2 text-xs text-mid-gray">{mensagem}</div>}

      <div className="px-4 pb-4">
        {regras.length === 0 ? (
          <p className="text-sm text-mid-gray">Nenhuma correção sua até agora.</p>
        ) : (
          <ul className="divide-y divide-mid-gray/20 text-sm">
            {regras.map((r) => (
              <li key={r.id} className="flex items-center gap-3 py-1.5">
                <span className="flex-1 min-w-0 truncate" title={r.pedido}>
                  {descrever(r)}
                  {r.por_ia ? <span className="text-xs text-mid-gray"> · pela IA</span> : null}
                </span>
                <span className="shrink-0 text-xs text-mid-gray">{r.quando ?? ""}</span>
                <button
                  type="button"
                  className="shrink-0 text-xs text-mid-gray underline cursor-pointer bg-transparent border-0 p-0"
                  title={dica("Desfazer esta correção")}
                  onClick={() => void desfazer(r.id)}
                >
                  desfazer
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </SettingsGroup>
  );
};

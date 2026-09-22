/* eslint-disable i18next/no-literal-string */
// Rotrix L-1000: pagina propria (roteador, gasto com IA e prompt do perfil).
import React, { useCallback, useEffect, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { SettingsGroup } from "../../ui/SettingsGroup";
import { SettingContainer } from "../../ui/SettingContainer";
import { Button } from "../../ui/Button";
import { Textarea } from "../../ui/Textarea";
import { RotrixIA } from "./RotrixIA";
import { RotrixMascaras } from "./RotrixMascaras";
import { RotrixFila } from "./RotrixFila";
import { ThemeSelector } from "../ThemeSelector";

interface RotrixStatus {
  ativo: boolean;
  versao: string | null;
  gatilhos: number | null;
  gasto: string | null;
  pasta: string | null;
}

const LIMITE = 2000;

const EXEMPLO =
  "Estruturar o laudo com subtópicos e, após os dois-pontos, seguir com a descrição na mesma linha (ex.: Rim: ..., Fígado: ...).\n" +
  "Um parágrafo por linha; nunca um bloco único de texto.\n" +
  "Achados alterados ou patológicos nas primeiras linhas da análise; achados normais abaixo.\n" +
  "Não mencionar a vesícula biliar nos laudos de abdome, somente se ela tiver alterações.";

export const RotrixSettings: React.FC = () => {
  const [status, setStatus] = useState<RotrixStatus | null>(null);
  const [prompt, setPrompt] = useState<string>("");
  const [salvo, setSalvo] = useState<string>("");
  const [mensagem, setMensagem] = useState<string>("");

  const atualizar = useCallback(async () => {
    try {
      const s = await invoke<RotrixStatus>("rotrix_status");
      setStatus(s);
    } catch (e) {
      console.error("rotrix_status:", e);
    }
  }, []);

  useEffect(() => {
    void atualizar();
    invoke<string>("rotrix_get_prompt")
      .then((p) => {
        setPrompt(p);
        setSalvo(p);
      })
      .catch((e) => console.error("rotrix_get_prompt:", e));
  }, [atualizar]);

  const salvar = async () => {
    try {
      await invoke("rotrix_set_prompt", { texto: prompt });
      setSalvo(prompt);
      setMensagem("Salvo. Vale a partir do próximo envio à IA.");
    } catch (e) {
      setMensagem("Não consegui salvar: " + String(e));
    }
  };

  const abrirPasta = async () => {
    try {
      await invoke("rotrix_abrir_pasta");
    } catch (e) {
      console.error("rotrix_abrir_pasta:", e);
    }
  };

  let situacao = "verificando…";
  if (status !== null) {
    situacao = status.ativo
      ? "ativo" + (status.versao ? " · versão " + status.versao : "")
      : "parado";
  }

  return (
    <div className="max-w-3xl w-full mx-auto space-y-6">
      <SettingsGroup title="Roteador de Laudos">
        <SettingContainer
          title="Situação"
          description="O roteador local monta o laudo com as máscaras, sem internet."
          grouped={true}
        >
          <span className="text-sm">{situacao}</span>
        </SettingContainer>
        <SettingContainer
          title="Gasto com IA"
          description="O que já foi enviado à IA com a sua chave, hoje e no mês."
          grouped={true}
        >
          <span className="text-sm">{status?.gasto ?? "—"}</span>
        </SettingContainer>
        <SettingContainer
          title="Pasta do roteador"
          description="Máscaras, dicionário de ouvido, configuração e chave de IA."
          grouped={true}
        >
          <div className="flex gap-2">
            <Button variant="secondary" size="sm" onClick={abrirPasta}>
              Abrir pasta
            </Button>
            <Button variant="secondary" size="sm" onClick={atualizar}>
              Atualizar
            </Button>
          </div>
        </SettingContainer>
        <ThemeSelector descriptionMode="tooltip" grouped={true} />
      </SettingsGroup>

      <RotrixFila />

      <SettingsGroup
        title="Prompt adicionado no processamento de todos os laudos"
        description="Não inclua comandos de formatação (centralizar título, fonte, tamanho, cores etc.). Este campo é para orientações sobre o conteúdo e o estilo narrativo dos laudos."
      >
        <div className="p-4 space-y-2">
          <Textarea
            className="w-full"
            rows={8}
            maxLength={LIMITE}
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            placeholder="Ex.: não mencionar a vesícula biliar nos laudos de abdome, somente se ela tiver alterações."
          />
          <div className="flex items-center justify-between text-xs text-mid-gray">
            <button
              type="button"
              className="underline cursor-pointer"
              onClick={() => setPrompt(EXEMPLO)}
            >
              Carregar exemplo
            </button>
            <span>
              {prompt.length} / {LIMITE}
            </span>
          </div>
          <div className="flex items-center gap-3">
            <Button
              variant="primary"
              size="sm"
              onClick={salvar}
              disabled={prompt === salvo}
            >
              Salvar
            </Button>
            {mensagem !== "" && (
              <span className="text-xs text-mid-gray">{mensagem}</span>
            )}
          </div>
        </div>
      </SettingsGroup>

      <RotrixIA />

      <RotrixMascaras />
    </div>
  );
};

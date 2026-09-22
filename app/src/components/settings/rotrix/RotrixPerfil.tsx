/* eslint-disable i18next/no-literal-string */
// Rotrix L-1000: perfil do radiologista. Leva para outro computador as suas
// máscaras, as suas correções de ouvido e os seus ajustes. A chave de IA nunca
// entra no arquivo; os seus laudos de estilo só se você marcar.
import React, { useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { ask, open, save } from "@tauri-apps/plugin-dialog";
import { SettingsGroup } from "../../ui/SettingsGroup";
import { SettingContainer } from "../../ui/SettingContainer";
import { Button } from "../../ui/Button";
import { ToggleSwitch } from "../../ui/ToggleSwitch";
import { dica, useAtalho } from "../../../lib/utils/atalhos";

interface Exportado {
  ok: boolean;
  arquivo?: string;
  mascaras?: number;
  laudos_de_estilo?: number;
  motivo?: string;
}

interface Importado {
  ok: boolean;
  mascaras?: number;
  laudos_de_estilo?: number;
  ouvido?: number;
  config?: boolean;
  base?: boolean;
  motivo?: string;
}

const MOTIVO: Record<string, string> = {
  arquivo_nao_encontrado: "não achei o arquivo",
  nao_e_um_perfil_rotrix: "esse arquivo não é um perfil do Rotrix",
  falha_ao_gerar_a_base: "as máscaras entraram, mas a base não foi gerada",
  perfil_indisponivel: "o roteador desta pasta não tem o perfil (atualize o roteador)",
};

const porque = (m?: string): string => (m ? (MOTIVO[m] ?? m) : "");

export const RotrixPerfil: React.FC = () => {
  const [ocupado, setOcupado] = useState(false);
  const [estilo, setEstilo] = useState(false);
  const [mensagem, setMensagem] = useState("");

  const exportar = async () => {
    const destino = await save({
      title: "Salvar o perfil",
      defaultPath: "perfil-rotrix.rotrix.zip",
      filters: [{ name: "Perfil do Rotrix", extensions: ["zip"] }],
    });
    if (!destino) return;
    setOcupado(true);
    setMensagem("Salvando…");
    try {
      const txt = await invoke<string>("rotrix_perfil_exportar", {
        destino,
        incluirEstilo: estilo,
      });
      const r = JSON.parse(txt) as Exportado;
      setMensagem(
        r.ok
          ? `Perfil salvo: ${r.mascaras ?? 0} máscara(s)` +
              (r.laudos_de_estilo ? `, ${r.laudos_de_estilo} laudo(s) de estilo` : "") +
              `, ajustes e correções de ouvido. Arquivo: ${r.arquivo ?? destino}`
          : "Não deu para salvar: " + porque(r.motivo),
      );
    } catch (e) {
      setMensagem("Não deu para salvar: " + String(e));
    } finally {
      setOcupado(false);
    }
  };

  const importar = async () => {
    const arq = await open({
      multiple: false,
      directory: false,
      filters: [{ name: "Perfil do Rotrix", extensions: ["zip"] }],
    });
    if (arq === null || Array.isArray(arq)) return;
    const substituir = await ask(
      "Trocar as máscaras que você já tem por estas, ou somar as duas coisas?",
      { title: "Rotrix", kind: "info", okLabel: "Trocar", cancelLabel: "Somar" },
    );
    setOcupado(true);
    setMensagem("Lendo o perfil… (a base de máscaras é gerada no fim)");
    try {
      const txt = await invoke<string>("rotrix_perfil_importar", {
        arquivo: arq,
        modo: substituir ? "substituir" : "juntar",
      });
      const r = JSON.parse(txt) as Importado;
      setMensagem(
        r.ok
          ? `Pronto: ${r.mascaras ?? 0} máscara(s), ${r.ouvido ?? 0} correção(ões) de ouvido` +
              (r.laudos_de_estilo ? `, ${r.laudos_de_estilo} laudo(s) de estilo` : "") +
              (r.config ? ", ajustes aplicados" : "") +
              (r.base === false ? " — a base não foi gerada" : "")
          : "Não deu para ler: " + porque(r.motivo),
      );
    } catch (e) {
      setMensagem("Não deu para ler: " + String(e));
    } finally {
      setOcupado(false);
    }
  };

  useAtalho("e", () => {
    if (!ocupado) void exportar();
  });
  useAtalho("i", () => {
    if (!ocupado) void importar();
  });

  return (
    <SettingsGroup
      title="Perfil"
      description="Um arquivo só com o que é seu: máscaras, correções de ouvido e ajustes. Serve para levar a outro computador ou guardar como cópia."
    >
      <ToggleSwitch
        label="Incluir os meus laudos de estilo"
        description="Os laudos que você incluiu para a IA copiar o seu jeito. Ficam só no arquivo, no seu computador."
        descriptionMode="inline"
        grouped={true}
        checked={estilo}
        onChange={setEstilo}
      />
      <SettingContainer
        title="Levar para outro computador"
        description="A chave de IA nunca entra no arquivo."
        grouped={true}
      >
        <div className="flex gap-2">
          <Button
            variant="primary"
            size="sm"
            disabled={ocupado}
            title={dica("Gravar um .rotrix.zip com o que é seu", "e")}
            onClick={() => void exportar()}
          >
            Exportar perfil
          </Button>
          <Button
            variant="secondary"
            size="sm"
            disabled={ocupado}
            title={dica("Ler um .rotrix.zip de outro computador", "i")}
            onClick={() => void importar()}
          >
            Importar perfil
          </Button>
        </div>
      </SettingContainer>
      {mensagem !== "" && <div className="px-4 pb-3 text-xs text-mid-gray">{mensagem}</div>}
    </SettingsGroup>
  );
};

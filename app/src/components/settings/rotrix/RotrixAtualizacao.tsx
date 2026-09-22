/* eslint-disable i18next/no-literal-string */
// Rotrix L-1000: atualização do app. O Rotrix procura a versão publicada no
// GitHub e abre o instalador para você. Nada é instalado sem você mandar.
import React, { useCallback, useEffect, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { openUrl } from "@tauri-apps/plugin-opener";
import { SettingsGroup } from "../../ui/SettingsGroup";
import { SettingContainer } from "../../ui/SettingContainer";
import { Button } from "../../ui/Button";
import { dica, useAtalho } from "../../../lib/utils/atalhos";

interface Versao {
  instalada: string;
  publicada: string;
  nome: string;
  quando: string;
  link: string;
  tem_nova: boolean;
}

const dia = (iso: string): string => {
  const m = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/.exec(iso || "");
  return m ? `${m[3]}/${m[2]} ${m[4]}:${m[5]}` : "";
};

export const RotrixAtualizacao: React.FC = () => {
  const [v, setV] = useState<Versao | null>(null);
  const [mensagem, setMensagem] = useState("");
  const [ocupado, setOcupado] = useState(false);

  const procurar = useCallback(async () => {
    setOcupado(true);
    setMensagem("Procurando…");
    try {
      const r = await invoke<Versao>("rotrix_versao_publicada");
      setV(r);
      setMensagem(
        r.tem_nova
          ? "Tem versão nova."
          : r.instalada === ""
            ? "Esta cópia foi compilada fora do GitHub; comparo só pela data."
            : "Você já está na versão publicada.",
      );
    } catch (e) {
      setMensagem(String(e));
    } finally {
      setOcupado(false);
    }
  }, []);

  useEffect(() => {
    void procurar();
  }, [procurar]);

  const baixar = async () => {
    if (!v?.link) return;
    try {
      await openUrl(v.link);
      setMensagem("Baixando pelo navegador. Feche o Rotrix antes de rodar o instalador.");
    } catch (e) {
      setMensagem("Não consegui abrir o link: " + String(e));
    }
  };

  useAtalho("u", () => void procurar());

  return (
    <SettingsGroup
      title="Atualização"
      description="A versão publicada fica no GitHub, sem login. O Rotrix confere e baixa; instalar é você quem manda."
    >
      <SettingContainer
        title="Versão publicada"
        description={v?.quando ? `Publicada em ${dia(v.quando)}.` : "Procura ao abrir a página."}
        grouped={true}
      >
        <div className="flex items-center gap-3">
          <span className="text-sm">{v?.nome || "—"}</span>
          <Button
            variant="secondary"
            size="sm"
            disabled={ocupado}
            title={dica("Procurar versão nova", "u")}
            onClick={() => void procurar()}
          >
            Procurar
          </Button>
          {v?.tem_nova && v.link !== "" && (
            <Button variant="primary" size="sm" title={dica("Baixar o instalador")} onClick={() => void baixar()}>
              Baixar
            </Button>
          )}
        </div>
      </SettingContainer>
      {mensagem !== "" && <div className="px-4 pb-3 text-xs text-mid-gray">{mensagem}</div>}
    </SettingsGroup>
  );
};

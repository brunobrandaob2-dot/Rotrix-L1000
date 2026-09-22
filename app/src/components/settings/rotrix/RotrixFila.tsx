/* eslint-disable i18next/no-literal-string */
// Rotrix L-1000: fila do Radius. O roteador lê os arquivos de estado do Radius
// no próprio computador e só devolve modalidade, descrição, status e laudado.
// Nome e número de acesso nunca chegam à tela ("Paciente ••••").
import React, { useCallback, useEffect, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { SettingsGroup } from "../../ui/SettingsGroup";
import { SettingContainer } from "../../ui/SettingContainer";
import { Button } from "../../ui/Button";
import { Input } from "../../ui/Input";
import { ToggleSwitch } from "../../ui/ToggleSwitch";

interface Estudo {
  id: string;
  modalidade: string;
  descricao: string;
  status: string;
  laudado: boolean | null;
  entrou: string;
  cabecalho: string;
  mascara: string | null;
}

interface Fila {
  disponivel: boolean;
  pasta_existe?: boolean;
  itens: Estudo[];
  atual: string | null;
  perfil_automatico: boolean;
}

const MAX_LINHAS = 40;

// "msk/rx/joelho/normal" -> "rx · joelho"
const nomeMascara = (m: string | null): string => {
  if (!m) return "sem máscara";
  const p = m.split("/");
  return p.length >= 3 ? `${p[1]} · ${p[2].replace(/_/g, " ")}` : m;
};

// status do Radius em português (o resto aparece como veio)
const STATUS_PT: Record<string, string> = {
  ready: "pronto",
  downloaded: "baixado",
  downloading: "baixando",
  queued: "na fila",
  pending: "na fila",
  opened: "aberto",
  open: "aberto",
  error: "erro",
  failed: "erro",
  completed: "concluído",
  reported: "laudado",
};

const statusPt = (s: string): string => STATUS_PT[(s || "").trim().toLowerCase()] ?? s;

const hora = (t: string): string => {
  const m = /T?(\d{2}):(\d{2})/.exec(t || "");
  return m ? `${m[1]}:${m[2]}` : "";
};

export const RotrixFila: React.FC = () => {
  const [fila, setFila] = useState<Fila | null>(null);
  const [erro, setErro] = useState<string>("");
  const [pasta, setPasta] = useState<string>("");
  const [mensagem, setMensagem] = useState<string>("");
  const [salvando, setSalvando] = useState<boolean>(false);

  const ler = useCallback(async () => {
    try {
      const txt = await invoke<string>("rotrix_fila");
      setFila(JSON.parse(txt) as Fila);
      setErro("");
    } catch (e) {
      setErro(String(e));
    }
  }, []);

  useEffect(() => {
    void ler();
    const t = window.setInterval(() => void ler(), 10000);
    return () => window.clearInterval(t);
  }, [ler]);

  const salvar = async (perfil: boolean, novaPasta: string | null) => {
    setSalvando(true);
    try {
      await invoke("rotrix_fila_salvar", {
        perfilAutomatico: perfil,
        pasta: novaPasta,
      });
      setMensagem(novaPasta !== null ? "Pasta salva." : "");
      await ler();
    } catch (e) {
      setMensagem("Não consegui salvar: " + String(e));
    } finally {
      setSalvando(false);
    }
  };

  let situacao = "lendo…";
  if (erro !== "") situacao = "roteador parado";
  else if (fila && !fila.disponivel) situacao = "leitura do Radius indisponível";
  else if (fila && fila.pasta_existe === false) situacao = "pasta do Radius não encontrada";
  else if (fila) {
    const pendentes = fila.itens.filter((x) => !x.laudado).length;
    situacao = `${fila.itens.length} estudo(s), ${pendentes} sem laudo`;
  }

  const itens = (fila?.itens ?? []).slice(0, MAX_LINHAS);

  return (
    <SettingsGroup
      title="Fila do Radius"
      description="Lida no seu computador. Só modalidade, exame e situação aparecem aqui; o nome do paciente nunca sai do Radius."
    >
      <SettingContainer title="Situação" description="Atualiza a cada 10 segundos." grouped={true}>
        <div className="flex items-center gap-3">
          <span className="text-sm">{situacao}</span>
          <Button variant="secondary" size="sm" onClick={() => void ler()}>
            Atualizar
          </Button>
        </div>
      </SettingContainer>

      <ToggleSwitch
        label="Perfil automático (radiografia)"
        description="Ditado de RX sem o nome do exame usa o exame aberto no Radius: “opacidade na base direita” vira radiografia do tórax com esse achado."
        descriptionMode="inline"
        grouped={true}
        checked={fila?.perfil_automatico ?? false}
        disabled={fila === null || erro !== ""}
        isUpdating={salvando}
        onChange={(v) => void salvar(v, null)}
      />

      <SettingContainer
        title="Pasta do Radius"
        description="Deixe em branco para usar Downloads\Radius Downloads."
        grouped={true}
      >
        <div className="flex gap-2">
          <Input
            className="w-72"
            value={pasta}
            placeholder="C:\Users\...\Downloads\Radius Downloads"
            onChange={(e) => setPasta(e.target.value)}
          />
          <Button
            variant="secondary"
            size="sm"
            onClick={() => void salvar(fila?.perfil_automatico ?? false, pasta)}
          >
            Salvar
          </Button>
        </div>
      </SettingContainer>
      {mensagem !== "" && <div className="px-4 pb-2 text-xs text-mid-gray">{mensagem}</div>}

      <div className="px-4 pb-4">
        {itens.length === 0 ? (
          <p className="text-sm text-mid-gray">Nenhum estudo na fila.</p>
        ) : (
          <ul className="divide-y divide-mid-gray/20 text-sm">
            {itens.map((x) => {
              const aberto = fila?.atual === x.id;
              const marca = x.laudado ? "✓" : aberto ? "●" : "○";
              return (
                <li
                  key={x.id}
                  className={`flex items-center gap-3 py-1.5 ${x.laudado ? "opacity-60" : ""}`}
                  title={x.cabecalho}
                >
                  <span
                    className="w-4 shrink-0 text-center"
                    aria-label={x.laudado ? "laudado" : aberto ? "estudo da vez" : "na fila"}
                    title={x.laudado ? "laudado" : aberto ? "estudo da vez" : "na fila"}
                  >
                    {marca}
                  </span>
                  <span className="w-10 shrink-0 text-xs font-semibold">{x.modalidade}</span>
                  <span className="flex-1 min-w-0 truncate">{x.descricao || "—"}</span>
                  <span className="shrink-0 whitespace-nowrap text-xs text-mid-gray">Paciente ••••</span>
                  <span className="w-28 shrink-0 truncate text-xs text-mid-gray">{nomeMascara(x.mascara)}</span>
                  <span className="w-20 shrink-0 truncate text-right text-xs text-mid-gray">{statusPt(x.status)}</span>
                  <span className="w-12 shrink-0 text-right text-xs text-mid-gray">{hora(x.entrou)}</span>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </SettingsGroup>
  );
};

/* eslint-disable i18next/no-literal-string */
// Rotrix L-1000: fila do Radius e modo estação. O roteador lê os arquivos de
// estado do Radius no próprio computador e só devolve modalidade, descrição,
// situação e laudado. Nome e número de acesso nunca chegam à tela.
// O "exame da vez" (●) decide a máscara do próximo ditado quando o perfil
// automático está ligado; Ctrl+Alt+N passa para o próximo.
import React, { useCallback, useEffect, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
import { SettingsGroup } from "../../ui/SettingsGroup";
import { SettingContainer } from "../../ui/SettingContainer";
import { Button } from "../../ui/Button";
import { Input } from "../../ui/Input";
import { ToggleSwitch } from "../../ui/ToggleSwitch";
import { ShortcutInput } from "../ShortcutInput";
import { dica, useAtalho } from "../../../lib/utils/atalhos";

interface Estudo {
  id: string;
  modalidade: string;
  descricao: string;
  status: string;
  laudado: boolean | null;
  entrou: string;
  cabecalho: string;
  mascara: string | null;
  feito?: boolean;
}

interface Fila {
  disponivel: boolean;
  pasta_existe?: boolean;
  itens: Estudo[];
  atual: string | null;
  vez?: string | null;
  escolhido?: string | null;
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

  // Ctrl+Alt+N (ou o atalho que você escolher) avisa aqui
  useEffect(() => {
    const p = listen("rotrix-proximo-exame", () => void ler());
    return () => {
      void p.then((un) => un());
    };
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

  const proximo = async () => {
    setSalvando(true);
    try {
      const txt = await invoke<string>("rotrix_fila_proximo");
      const r = JSON.parse(txt) as { ok: boolean; item: Estudo | null; restam?: number };
      setMensagem(
        r.item
          ? `Agora: ${r.item.descricao || r.item.modalidade}${
              typeof r.restam === "number" ? ` · faltam ${r.restam}` : ""
            }`
          : "Não há mais exame pendente na fila.",
      );
      await ler();
    } catch (e) {
      setMensagem("Não consegui passar de exame: " + String(e));
    } finally {
      setSalvando(false);
    }
  };

  const escolher = async (id: string) => {
    try {
      await invoke("rotrix_fila_escolher", { id });
      setMensagem("");
      await ler();
    } catch (e) {
      setMensagem("Não consegui escolher: " + String(e));
    }
  };

  const marcar = async (id: string, feito: boolean) => {
    try {
      await invoke("rotrix_fila_feito", { id, feito });
      await ler();
    } catch (e) {
      setMensagem("Não consegui marcar: " + String(e));
    }
  };

  let situacao = "lendo…";
  if (erro !== "") situacao = "roteador parado";
  else if (fila && !fila.disponivel) situacao = "leitura do Radius indisponível";
  else if (fila && fila.pasta_existe === false) situacao = "pasta do Radius não encontrada";
  else if (fila) {
    const pendentes = fila.itens.filter((x) => !x.laudado && !x.feito).length;
    situacao = `${fila.itens.length} exame(s) na fila · ${pendentes} para laudar`;
  }

  const itens = (fila?.itens ?? []).slice(0, MAX_LINHAS);
  const vez = itens.find((x) => x.id === fila?.vez) ?? null;

  // teclas da tela (sem Ctrl/Alt), enquanto você não está num campo de texto
  useAtalho("a", () => void ler());
  useAtalho("n", () => {
    if (!salvando && fila !== null && erro === "") void proximo();
  });
  useAtalho("l", () => {
    if (vez) void marcar(vez.id, true);
  });

  return (
    <SettingsGroup
      title="Fila do Radius"
      description="Lida no seu computador. Só modalidade, exame e situação aparecem aqui; o nome do paciente nunca sai do Radius."
    >
      <SettingContainer title="Na fila agora" description="Atualiza a cada 10 segundos." grouped={true}>
        <div className="flex items-center gap-3">
          <span className="text-sm">{situacao}</span>
          <Button
            variant="secondary"
            size="sm"
            title={dica("Reler a fila do Radius", "a")}
            onClick={() => void ler()}
          >
            Atualizar
          </Button>
        </div>
      </SettingContainer>

      <SettingContainer
        title="Exame da vez"
        description="É ele que o ditado usa quando o perfil automático está ligado."
        grouped={true}
      >
        <div className="flex items-center gap-3">
          <span className="text-sm">
            {vez ? `${vez.modalidade} · ${vez.descricao || "sem descrição"}` : "nenhum"}
          </span>
          <Button
            variant="primary"
            size="sm"
            disabled={salvando || fila === null || erro !== ""}
            title={dica("Marca o exame da vez como laudado e passa ao próximo", "n")}
            onClick={() => void proximo()}
          >
            Próximo exame
          </Button>
        </div>
      </SettingContainer>
      {vez && (
        <div className="px-4 pb-2 text-xs text-mid-gray">
          Abertura do ditado: {vez.cabecalho || "—"} · máscara: {nomeMascara(vez.mascara)}
        </div>
      )}

      <ShortcutInput shortcutId="proximo_exame" grouped={true} />

      <ToggleSwitch
        label="Perfil automático (radiografia)"
        description="Ditado de RX sem o nome do exame usa o exame da vez: “opacidade na base direita” vira radiografia do tórax com esse achado."
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
            title={dica("Salvar a pasta do Radius")}
            onClick={() => void salvar(fila?.perfil_automatico ?? false, pasta)}
          >
            Salvar
          </Button>
        </div>
      </SettingContainer>
      {mensagem !== "" && <div className="px-4 pb-2 text-xs text-mid-gray">{mensagem}</div>}

      <div className="px-4 pb-4">
        {itens.length === 0 ? (
          <p className="text-sm text-mid-gray">Nenhum exame na fila.</p>
        ) : (
          <ul className="divide-y divide-mid-gray/20 text-sm">
            {itens.map((x) => {
              const daVez = fila?.vez === x.id;
              const pronto = Boolean(x.laudado || x.feito);
              const marca = pronto ? "✓" : daVez ? "●" : "○";
              const titulo = pronto ? "laudado" : daVez ? "exame da vez" : "na fila";
              return (
                <li
                  key={x.id}
                  className={`flex items-center gap-3 py-1.5 ${pronto ? "opacity-60" : ""} ${
                    daVez ? "font-semibold" : ""
                  }`}
                  title={x.cabecalho}
                >
                  <button
                    type="button"
                    className="w-4 shrink-0 text-center cursor-pointer bg-transparent border-0 p-0 leading-none"
                    aria-label={titulo}
                    title={pronto ? "marcar como não laudado" : "tornar este o exame da vez"}
                    onClick={() => void (pronto ? marcar(x.id, false) : escolher(x.id))}
                  >
                    {marca}
                  </button>
                  <span className="w-10 shrink-0 text-xs font-semibold">{x.modalidade}</span>
                  <span className="flex-1 min-w-0 truncate">{x.descricao || "—"}</span>
                  <span className="shrink-0 whitespace-nowrap text-xs text-mid-gray">Paciente ••••</span>
                  <span className="w-28 shrink-0 truncate text-xs text-mid-gray">{nomeMascara(x.mascara)}</span>
                  <span className="w-20 shrink-0 truncate text-right text-xs text-mid-gray">
                    {statusPt(x.status)}
                  </span>
                  <span className="w-12 shrink-0 text-right text-xs text-mid-gray">{hora(x.entrou)}</span>
                  {!pronto && (
                    <button
                      type="button"
                      className="shrink-0 text-xs text-mid-gray underline cursor-pointer bg-transparent border-0 p-0"
                      title={dica("Marcar como laudado por você", daVez ? "l" : undefined)}
                      onClick={() => void marcar(x.id, true)}
                    >
                      laudei
                    </button>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </SettingsGroup>
  );
};

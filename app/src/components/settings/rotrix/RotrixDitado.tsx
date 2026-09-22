/* eslint-disable i18next/no-literal-string */
// Rotrix L-1000: como o ditado é acionado e com qual modelo.
// Segurar para falar: enquanto a tecla está pressionada, grava; ao soltar,
// o texto vem. Nada prende o mouse nem o teclado — dá para trocar de tela,
// mexer nas imagens e ditar ao mesmo tempo.
import React, { useCallback, useEffect, useState } from "react";
import { commands } from "@/bindings";
import type { ModelInfo } from "@/bindings";
import { SettingsGroup } from "../../ui/SettingsGroup";
import { SettingContainer } from "../../ui/SettingContainer";
import { Button } from "../../ui/Button";
import { ShortcutInput } from "../ShortcutInput";
import { ShortcutActivationSetting } from "../ShortcutActivation";
import { dica, useAtalho } from "../../../lib/utils/atalhos";

const PT = "pt";

const falaPortugues = (m: ModelInfo): boolean =>
  m.supported_languages.length === 0 || m.supported_languages.includes(PT);

// nota do catálogo: precisão pesa mais que velocidade, mas um modelo lento
// atrapalha o plantão
const nota = (m: ModelInfo): number => m.accuracy_score * 2 + m.speed_score;

export const RotrixDitado: React.FC = () => {
  const [atual, setAtual] = useState<ModelInfo | null>(null);
  const [opcoes, setOpcoes] = useState<ModelInfo[]>([]);
  const [mensagem, setMensagem] = useState("");
  const [ocupado, setOcupado] = useState(false);

  const ler = useCallback(async () => {
    const id = await commands.getCurrentModel();
    const lista = await commands.getAvailableModels();
    if (lista.status !== "ok") return;
    const modelos = lista.data.filter(falaPortugues);
    const idAtual = id.status === "ok" ? id.data : "";
    setAtual(modelos.find((m) => m.id === idAtual) ?? null);
    setOpcoes([...modelos].sort((a, b) => nota(b) - nota(a)).slice(0, 4));
  }, []);

  useEffect(() => {
    void ler();
  }, [ler]);

  const usar = useCallback(
    async (m: ModelInfo) => {
      setOcupado(true);
      try {
        if (!m.is_downloaded) {
          setMensagem(`Baixando ${m.name} (${m.size_mb} MB)… pode deixar rodando.`);
          const r = await commands.downloadModel(m.id);
          if (r.status !== "ok") {
            setMensagem("Não consegui baixar: " + String(r.error));
            return;
          }
        }
        const s = await commands.setActiveModel(m.id);
        setMensagem(
          s.status === "ok"
            ? `${m.name} em uso. Rode o ATUALIZAR_AGORA.bat depois, para o vocabulário combinar com ele.`
            : "Não consegui trocar o modelo: " + String(s.error),
        );
        await ler();
      } finally {
        setOcupado(false);
      }
    },
    [ler],
  );

  const melhor = opcoes[0] ?? null;
  useAtalho("m", () => {
    if (melhor && !ocupado && melhor.id !== atual?.id) void usar(melhor);
  });

  return (
    <SettingsGroup
      title="Ditado"
      description="Segure a tecla e fale; ao soltar, o texto entra. Enquanto grava, você continua mexendo o mouse e trocando de tela — a barra fica flutuando e não prende nada."
    >
      <ShortcutInput shortcutId="transcribe_with_post_process" grouped={true} />
      <ShortcutActivationSetting descriptionMode="inline" grouped={true} />

      <SettingContainer
        title="Modelo de reconhecimento"
        description="Quem transforma a sua voz em texto, antes do roteador montar o laudo."
        grouped={true}
      >
        <div className="flex items-center gap-3">
          <span className="text-sm">{atual ? atual.name : "lendo…"}</span>
          {melhor && atual && melhor.id !== atual.id && (
            <Button
              variant="secondary"
              size="sm"
              disabled={ocupado}
              title={dica(`Usar ${melhor.name}`, "m")}
              onClick={() => void usar(melhor)}
            >
              Usar o recomendado
            </Button>
          )}
        </div>
      </SettingContainer>

      <div className="px-4 pb-4">
        <p className="text-sm text-mid-gray mb-2">
          Modelos que falam português, do melhor equilíbrio para o mais devagar:
        </p>
        <ul className="flex flex-col gap-2">
          {opcoes.map((m, i) => (
            <li key={m.id} className="flex items-center gap-3 text-sm">
              <span className="flex-1 min-w-0 truncate">
                {m.name}
                <span className="text-xs text-mid-gray">
                  {" · "}precisão {m.accuracy_score} · velocidade {m.speed_score} · {m.size_mb} MB
                  {m.is_downloaded ? " · baixado" : ""}
                  {i === 0 ? " · recomendado" : ""}
                  {m.supports_streaming ? " · mostra o texto enquanto fala" : ""}
                </span>
              </span>
              {m.id === atual?.id ? (
                <span className="text-xs text-mid-gray shrink-0">em uso</span>
              ) : (
                <Button
                  variant="secondary"
                  size="sm"
                  disabled={ocupado}
                  title={dica(m.is_downloaded ? `Usar ${m.name}` : `Baixar e usar ${m.name}`, i === 0 ? "m" : undefined)}
                  onClick={() => void usar(m)}
                >
                  {m.is_downloaded ? "Usar este" : "Baixar e usar"}
                </Button>
              )}
            </li>
          ))}
        </ul>
        {mensagem !== "" && <p className="text-xs text-mid-gray mt-2">{mensagem}</p>}
      </div>
    </SettingsGroup>
  );
};

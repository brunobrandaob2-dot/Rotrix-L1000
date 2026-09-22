/* eslint-disable i18next/no-literal-string */
// Rotrix L-1000: texto ao vivo. A barra de gravação mostra o que você está
// falando enquanto fala — só com modelo que reconhece em tempo real. O Whisper
// não faz isso: ele só devolve o texto no fim.
import React, { useCallback, useEffect, useState } from "react";
import { commands } from "@/bindings";
import type { ModelInfo } from "@/bindings";
import { SettingsGroup } from "../../ui/SettingsGroup";
import { SettingContainer } from "../../ui/SettingContainer";
import { Button } from "../../ui/Button";

const PT = "pt";

const fala = (m: ModelInfo): boolean =>
  m.supported_languages.length === 0 || m.supported_languages.includes(PT);

export const RotrixAoVivo: React.FC = () => {
  const [atual, setAtual] = useState<ModelInfo | null>(null);
  const [opcoes, setOpcoes] = useState<ModelInfo[]>([]);
  const [mensagem, setMensagem] = useState("");
  const [ocupado, setOcupado] = useState(false);

  const ler = useCallback(async () => {
    const id = await commands.getCurrentModel();
    const lista = await commands.getAvailableModels();
    if (lista.status !== "ok") return;
    const modelos = lista.data;
    setOpcoes(modelos.filter((m) => m.supports_streaming && fala(m)));
    const idAtual = id.status === "ok" ? id.data : "";
    setAtual(modelos.find((m) => m.id === idAtual) ?? null);
  }, []);

  useEffect(() => {
    void ler();
  }, [ler]);

  const usar = async (m: ModelInfo) => {
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
          ? `Pronto: ${m.name} em uso. Rode o ATUALIZAR_AGORA.bat depois, para o vocabulário combinar com este modelo.`
          : "Não consegui trocar o modelo: " + String(s.error),
      );
      await ler();
    } finally {
      setOcupado(false);
    }
  };

  const ligado = Boolean(atual?.supports_streaming);

  return (
    <SettingsGroup
      title="Texto ao vivo"
      description="A barra de gravação mostra o texto enquanto você dita. O roteador continua montando o laudo no fim, do mesmo jeito."
    >
      <SettingContainer
        title="Situação"
        description={
          ligado
            ? "O modelo em uso reconhece em tempo real."
            : "O modelo em uso só devolve o texto no fim do ditado."
        }
        grouped={true}
      >
        <span className="text-sm">
          {atual ? `${atual.name}${ligado ? " · ao vivo" : " · sem texto ao vivo"}` : "lendo…"}
        </span>
      </SettingContainer>

      {!ligado && (
        <div className="px-4 pb-3">
          <p className="text-sm text-mid-gray mb-2">
            Modelos que reconhecem em tempo real e falam português:
          </p>
          {opcoes.length === 0 ? (
            <p className="text-sm text-mid-gray">Nenhum disponível nesta versão.</p>
          ) : (
            <ul className="flex flex-col gap-2">
              {opcoes.map((m) => (
                <li key={m.id} className="flex items-center gap-3 text-sm">
                  <span className="flex-1 min-w-0 truncate">
                    {m.name}
                    <span className="text-xs text-mid-gray">
                      {" · "}
                      {m.size_mb} MB{m.is_downloaded ? " · já baixado" : ""}
                    </span>
                  </span>
                  <Button
                    variant="secondary"
                    size="sm"
                    disabled={ocupado}
                    onClick={() => void usar(m)}
                  >
                    {m.is_downloaded ? "Usar este" : "Baixar e usar"}
                  </Button>
                </li>
              ))}
            </ul>
          )}
          <p className="text-xs text-mid-gray mt-2">
            Trocar de modelo muda o reconhecimento. O Whisper médio acerta mais termo raro; os de
            tempo real são mais rápidos e mostram o texto enquanto você fala. Dá para voltar quando
            quiser, na tela de modelos.
          </p>
        </div>
      )}
      {mensagem !== "" && <div className="px-4 pb-3 text-xs text-mid-gray">{mensagem}</div>}
    </SettingsGroup>
  );
};

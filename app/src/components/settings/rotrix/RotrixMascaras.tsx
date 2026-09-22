/* eslint-disable i18next/no-literal-string */
// Rotrix L-1000: "Minhas máscaras e laudos" — importar o arquivo de máscaras do
// próprio radiologista, os laudos que servem de estilo para a IA, e escolher se
// valem as máscaras do Rotrix, as suas ou as duas (importar_usuario.py).
import React, { useCallback, useEffect, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { ask, open } from "@tauri-apps/plugin-dialog";
import { SettingsGroup } from "../../ui/SettingsGroup";
import { SettingContainer } from "../../ui/SettingContainer";
import { Button } from "../../ui/Button";

interface MascaraImportada {
  titulo: string;
  comandos?: string[];
  comando?: string;
  avisos?: string[];
  arquivo?: string;
}

interface Resposta {
  ok?: boolean;
  erro?: string;
  acao?: string;
  fonte?: string;
  base?: string;
  importadas?: MascaraImportada[];
  recusadas?: { titulo: string; motivo: string }[];
  importados?: number;
  recusados?: { titulo: string; motivo: string }[];
  avisos?: string[];
  mascaras?: MascaraImportada[];
  laudos?: number;
  removidas?: number;
  removidos?: number;
}

const FONTES: { valor: string; nome: string; texto: string }[] = [
  {
    valor: "rotrix",
    nome: "Só as do Rotrix",
    texto: "O banco que vem com o app.",
  },
  {
    valor: "minhas",
    nome: "Só as minhas",
    texto: "Apenas as máscaras que você incluiu.",
  },
  {
    valor: "ambas",
    nome: "As duas",
    texto: "Quando o comando é o mesmo, vale a sua.",
  },
];

const EXTENSOES = ["txt", "md", "docx", "rtf"];

export const RotrixMascaras: React.FC = () => {
  const [lista, setLista] = useState<Resposta | null>(null);
  const [resultado, setResultado] = useState<Resposta | null>(null);
  const [ocupado, setOcupado] = useState<boolean>(false);
  const [mensagem, setMensagem] = useState<string>("");

  const chamar = async (
    acao: string,
    arg: string | null,
    substituir = false,
  ): Promise<Resposta | null> => {
    try {
      const txt = await invoke<string>("rotrix_mascaras", {
        acao,
        arg,
        substituir,
      });
      return JSON.parse(txt) as Resposta;
    } catch (err) {
      setMensagem(String(err));
      return null;
    }
  };

  const listar = useCallback(async () => {
    const r = await chamar("listar", null);
    if (r !== null) setLista(r);
  }, []);

  useEffect(() => {
    void listar();
  }, [listar]);

  const escolherFonte = async (f: string) => {
    setOcupado(true);
    setMensagem("Refazendo o banco…");
    const r = await chamar("fonte", f);
    setOcupado(false);
    if (r?.ok) {
      setMensagem("Pronto. " + (r.base ?? ""));
      await listar();
    }
  };

  const importar = async (tipo: "mascaras" | "laudos") => {
    const arq = await open({
      multiple: false,
      directory: false,
      filters: [{ name: "Máscaras ou laudos", extensions: EXTENSOES }],
    });
    if (arq === null || Array.isArray(arq)) return;
    let substituir = false;
    const temAlgo =
      tipo === "mascaras"
        ? (lista?.mascaras?.length ?? 0) > 0
        : (lista?.laudos ?? 0) > 0;
    if (temAlgo) {
      substituir = await ask(
        tipo === "mascaras"
          ? "Trocar as máscaras que você já incluiu pelas deste arquivo, ou somar?"
          : "Trocar os laudos de estilo que você já incluiu pelos deste arquivo, ou somar?",
        { title: "Rotrix", kind: "info", okLabel: "Trocar", cancelLabel: "Somar" },
      );
    }
    setOcupado(true);
    setMensagem(tipo === "mascaras" ? "Lendo as máscaras…" : "Lendo os laudos…");
    const r = await chamar(tipo, arq, substituir);
    setOcupado(false);
    if (r !== null) {
      setResultado(r);
      setMensagem(r.ok ? "" : "Falhou: " + (r.erro ?? ""));
      await listar();
    }
  };

  const remover = async (o: "mascaras" | "laudos") => {
    const sim = await ask(
      o === "mascaras"
        ? "Remover todas as máscaras que você incluiu? As do Rotrix continuam."
        : "Remover todos os laudos de estilo que você incluiu?",
      { title: "Rotrix", kind: "warning", okLabel: "Remover", cancelLabel: "Cancelar" },
    );
    if (!sim) return;
    setOcupado(true);
    const r = await chamar("remover", o);
    setOcupado(false);
    if (r?.ok) {
      setResultado(null);
      setMensagem("Removido.");
      await listar();
    }
  };

  const fonte = lista?.fonte ?? "rotrix";
  const minhas = lista?.mascaras ?? [];

  return (
    <div className="space-y-6">
      <SettingsGroup
        title="Minhas máscaras"
        description="Inclua o arquivo com as suas máscaras (.txt, .docx, .rtf ou .md). Separe uma da outra com uma linha “---” ou comece cada uma com o título em CAIXA ALTA. Os comandos de voz saem do título (“tc de tórax”); para escolher outros, escreva na primeira linha: gatilhos: minha tc de torax | tc torax."
      >
        <SettingContainer
          title="Quais máscaras valem"
          description="Mudar aqui refaz o banco (alguns segundos)."
          grouped={true}
          layout="stacked"
        >
          <div className="flex flex-col gap-2">
            {FONTES.map((f) => (
              <label
                key={f.valor}
                className="flex items-start gap-2 cursor-pointer text-sm"
              >
                <input
                  type="radio"
                  name="fonte_mascaras"
                  className="mt-1"
                  checked={fonte === f.valor}
                  disabled={ocupado}
                  onChange={() => void escolherFonte(f.valor)}
                />
                <span>
                  <b>{f.nome}</b>{" "}
                  <span className="text-mid-gray">— {f.texto}</span>
                </span>
              </label>
            ))}
          </div>
        </SettingContainer>
        <SettingContainer
          title="Incluir arquivo de máscaras"
          description="O lado escrito no título vira lacuna que o ditado preenche. Máscara com dado de paciente não entra."
          grouped={true}
        >
          <Button
            variant="primary"
            size="sm"
            disabled={ocupado}
            onClick={() => void importar("mascaras")}
          >
            Escolher arquivo…
          </Button>
        </SettingContainer>
        <div className="px-4 py-2 space-y-1">
          <div className="text-xs text-mid-gray">
            {minhas.length === 0
              ? "Nenhuma máscara sua ainda."
              : minhas.length + " máscara(s) sua(s):"}
          </div>
          {minhas.slice(0, 60).map((m) => (
            <div key={m.arquivo ?? m.titulo} className="text-xs">
              <b>{m.titulo}</b>
              {m.comando ? (
                <span className="text-mid-gray"> — diga “{m.comando}”</span>
              ) : null}
            </div>
          ))}
          {minhas.length > 0 && (
            <div className="pt-1">
              <Button
                variant="danger-ghost"
                size="sm"
                disabled={ocupado}
                onClick={() => void remover("mascaras")}
              >
                Remover minhas máscaras
              </Button>
            </div>
          )}
        </div>
      </SettingsGroup>

      <SettingsGroup
        title="Meus laudos (estilo para a IA)"
        description="Laudos seus, sem dados de paciente, que a IA usa como exemplo de vocabulário e ritmo. As linhas de cabeçalho com dados do paciente são retiradas; se sobrar CPF, data completa, prontuário ou e-mail, o laudo não entra. Nome no meio do texto não é detectável: retire antes."
      >
        <SettingContainer
          title="Incluir arquivo de laudos"
          description={
            (lista?.laudos ?? 0) + " laudo(s) de estilo incluído(s) por você."
          }
          grouped={true}
        >
          <div className="flex gap-2">
            <Button
              variant="primary"
              size="sm"
              disabled={ocupado}
              onClick={() => void importar("laudos")}
            >
              Escolher arquivo…
            </Button>
            {(lista?.laudos ?? 0) > 0 && (
              <Button
                variant="danger-ghost"
                size="sm"
                disabled={ocupado}
                onClick={() => void remover("laudos")}
              >
                Remover
              </Button>
            )}
          </div>
        </SettingContainer>
      </SettingsGroup>

      {(mensagem !== "" || resultado !== null) && (
        <div className="px-4 space-y-1 text-xs">
          {mensagem !== "" && <div className="text-mid-gray">{mensagem}</div>}
          {resultado?.importadas && (
            <div>
              {resultado.importadas.length} máscara(s) incluída(s)
              {resultado.base ? " · " + resultado.base : ""}
            </div>
          )}
          {resultado?.importadas?.map((m) => (
            <div key={"i-" + (m.arquivo ?? m.titulo)}>
              <b>{m.titulo}</b>
              {m.comandos && m.comandos.length > 0
                ? " — diga “" + m.comandos[0] + "”"
                : ""}
              {m.avisos && m.avisos.length > 0 ? (
                <span className="text-mid-gray"> ({m.avisos.join("; ")})</span>
              ) : null}
            </div>
          ))}
          {resultado?.importados !== undefined && (
            <div>{resultado.importados} laudo(s) de estilo incluído(s).</div>
          )}
          {[...(resultado?.recusadas ?? []), ...(resultado?.recusados ?? [])].map(
            (x, i) => (
              <div key={"r-" + i} className="text-red-400">
                Não entrou: {x.titulo} — {x.motivo}
              </div>
            ),
          )}
          {resultado?.avisos?.map((a, i) => (
            <div key={"a-" + i} className="text-mid-gray">
              {a}
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

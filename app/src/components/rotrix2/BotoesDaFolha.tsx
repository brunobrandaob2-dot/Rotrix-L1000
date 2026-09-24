/* eslint-disable i18next/no-literal-string */
// Rotrix L-1000 — os quatro botões do fim da fileira de formatação da folha.
//
// Escanometria (com três divisões) · Idade óssea · Prescrição · Cálculos.
//
// Cada um abre um painel. Nos exames de medida e na idade óssea o painel é um
// FORMULÁRIO: os números entram, o laudo sai pronto. A conta acontece no
// roteador, na máquina — a IA, quando entra, só lê o print e devolve valores.
// Isso não é detalhe de implementação: é o que faz o mesmo print dar sempre o
// mesmo laudo, e o que mantém a redação sendo a do médico, não a do modelo.
import React, { useCallback, useEffect, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import {
  Ruler,
  Bone,
  FileText,
  Calculator,
  ChevronDown,
  ImagePlus,
  X,
} from "lucide-react";
import { Button } from "../ui/Button";

// ---------------------------------------------------------------------------

type Exame = "escanometria" | "panoramica_mmii" | "panoramica_coluna";

interface CampoLeitura {
  0: string;
  1: string;
}

interface ConfExame {
  titulo: string;
  mascara: string;
  leitura: [string, string][];
  escolha: [string, string, string[]][];
  blocos: [string, string][];
  calculado: string[];
}

interface Props {
  /** põe o texto na folha, no ponto do cursor */
  aoInserir: (texto: string) => void;
  /** avisos curtos para o rodapé da folha */
  aoAvisar?: (texto: string) => void;
}

const DIVISOES: { id: Exame; nome: string; resumo: string }[] = [
  {
    id: "escanometria",
    nome: "Escanometria",
    resumo:
      "régua graduada, quadris / joelhos / tornozelos — fêmur, tíbia, membro inferior e a dismetria",
  },
  {
    id: "panoramica_mmii",
    nome: "Panorâmica de membros inferiores",
    resumo: "ortostase — eixo mecânico, ângulo femorotibial, comprimentos",
  },
  {
    id: "panoramica_coluna",
    nome: "Panorâmica da coluna total",
    resumo: "AP e perfil — Cobb, Risser, báscula, balanço sagital, Ferguson",
  },
];

const IDADE_OSSEA = [
  { id: "greulich", nome: "Greulich & Pyle", resumo: "atlas de mão e punho, com a variabilidade do Brush Foundation" },
];

// ---------------------------------------------------------------------------

const Menu: React.FC<{
  aberto: boolean;
  aoFechar: () => void;
  children: React.ReactNode;
}> = ({ aberto, aoFechar, children }) => {
  useEffect(() => {
    if (!aberto) return;
    const sair = (e: KeyboardEvent) => {
      if (e.key === "Escape") aoFechar();
    };
    window.addEventListener("keydown", sair);
    return () => window.removeEventListener("keydown", sair);
  }, [aberto, aoFechar]);
  if (!aberto) return null;
  return (
    <>
      <div className="fixed inset-0 z-40" onClick={aoFechar} />
      <div className="absolute z-50 top-full mt-1 start-0 w-[330px] rounded-xl border border-mid-gray/30 bg-background shadow-2xl p-1.5">
        {children}
      </div>
    </>
  );
};

const ItemMenu: React.FC<{
  nome: string;
  resumo?: string;
  onClick: () => void;
}> = ({ nome, resumo, onClick }) => (
  <button
    type="button"
    onClick={onClick}
    className="w-full text-start px-2.5 py-2 rounded-lg hover:bg-logo-primary/20 cursor-pointer"
  >
    <div className="text-[12.5px] font-semibold">{nome}</div>
    {resumo && <div className="text-[10.5px] text-mid-gray leading-tight">{resumo}</div>}
  </button>
);

const Fer: React.FC<{
  titulo: string;
  onClick: () => void;
  aberto?: boolean;
  children: React.ReactNode;
}> = ({ titulo, onClick, aberto, children }) => (
  <button
    type="button"
    title={titulo}
    onClick={onClick}
    className={`h-7 px-2 rounded-lg border flex items-center gap-1.5 text-[11.5px] cursor-pointer transition-colors ${
      aberto
        ? "border-logo-primary/60 bg-logo-primary/30 font-semibold"
        : "border-logo-primary/45 bg-logo-primary/12 hover:bg-logo-primary/22"
    }`}
  >
    {children}
  </button>
);

// ---------------------------------------------------------------------------
// Painel dos exames de medida
// ---------------------------------------------------------------------------

const PainelMedidas: React.FC<{
  exame: Exame;
  conf?: ConfExame;
  aoInserir: (t: string) => void;
  aoFechar: () => void;
}> = ({ exame, conf, aoInserir, aoFechar }) => {
  const [valores, setValores] = useState<Record<string, string>>({});
  const [saida, setSaida] = useState<{ texto: string; avisos: string[] } | null>(null);
  const [erro, setErro] = useState("");
  const [ocupado, setOcupado] = useState(false);

  const trocar = (k: string, v: string) => {
    setValores((x) => ({ ...x, [k]: v }));
    setSaida(null);
  };

  const gerar = useCallback(async () => {
    setOcupado(true);
    setErro("");
    try {
      const bruto = await invoke<string>("rotrix_medidas", {
        exame,
        valores: JSON.stringify(valores),
      });
      const r = JSON.parse(bruto || "{}") as {
        ok?: boolean;
        texto?: string;
        avisos?: string[];
        motivo?: string;
        faltando?: string[];
      };
      if (!r.ok) {
        setErro(
          r.motivo === "nivel_ausente"
            ? `falta a leitura de: ${(r.faltando || []).join(", ")}`
            : r.motivo || "não deu para montar",
        );
        return;
      }
      setSaida({ texto: r.texto || "", avisos: r.avisos || [] });
    } catch (e) {
      setErro(String(e));
    } finally {
      setOcupado(false);
    }
  }, [exame, valores]);

  if (!conf) {
    return (
      <div className="p-4 text-[12px] text-mid-gray">
        o roteador ainda não respondeu com os campos deste exame
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full min-h-0">
      <div className="flex items-center gap-2 px-3 py-2 border-b border-mid-gray/20">
        <span className="text-[12.5px] font-semibold">{conf.titulo}</span>
        <button
          type="button"
          onClick={aoFechar}
          className="ms-auto p-1 rounded hover:bg-mid-gray/20 cursor-pointer"
          title="fechar"
        >
          <X size={14} />
        </button>
      </div>

      <div className="flex-1 min-h-0 overflow-y-auto p-3 space-y-3">
        <div>
          <div className="text-[9.5px] font-bold tracking-wider text-mid-gray mb-1.5">
            {exame === "escanometria" ? "LEITURAS NA RÉGUA (cm)" : "MEDIDAS"}
          </div>
          <div className="grid grid-cols-2 gap-2">
            {conf.leitura.map(([k, rot]) => (
              <label key={k} className="flex flex-col gap-0.5">
                <span className="text-[10px] text-mid-gray">{rot}</span>
                <input
                  value={valores[k] ?? ""}
                  onChange={(e) => trocar(k, e.target.value)}
                  inputMode="decimal"
                  className="h-7 rounded-lg border border-mid-gray/25 bg-background px-2 text-[12px]"
                />
              </label>
            ))}
          </div>
        </div>

        {conf.escolha.map(([k, rot, opcoes]) => (
          <div key={k}>
            <div className="text-[9.5px] font-bold tracking-wider text-mid-gray mb-1">
              {rot.toUpperCase()}
            </div>
            <div className="flex flex-wrap gap-1.5">
              {opcoes.map((o) => (
                <button
                  key={o}
                  type="button"
                  onClick={() => trocar(k, o)}
                  className={`text-[10.5px] px-2 py-1 rounded-md border cursor-pointer ${
                    valores[k] === o
                      ? "border-logo-primary/60 bg-logo-primary/25 font-bold"
                      : "border-mid-gray/25 hover:bg-mid-gray/15"
                  }`}
                >
                  {o}
                </button>
              ))}
            </div>
          </div>
        ))}

        <button
          type="button"
          onClick={() =>
            setErro(
              "colar o print entra junto com o botão de imagem da folha: a imagem passa pelo recorte e pela limpeza de metadados antes de sair",
            )
          }
          className="w-full h-9 rounded-lg border border-logo-primary/45 bg-logo-primary/12 flex items-center justify-center gap-2 text-[11.5px] font-semibold cursor-pointer hover:bg-logo-primary/22"
        >
          <ImagePlus size={15} /> Colar print com as medidas
        </button>

        {erro && (
          <div className="text-[11px] rounded-lg border border-amber-400/40 bg-amber-100/10 text-amber-300 px-2.5 py-2">
            {erro}
          </div>
        )}

        {saida && (
          <div className="rounded-lg bg-white text-black p-3">
            <pre className="whitespace-pre-wrap font-mono text-[11px] leading-[1.5]">
              {saida.texto.replace(/\*\*/g, "")}
            </pre>
          </div>
        )}
        {saida?.avisos.map((a) => (
          <div
            key={a}
            className="text-[11px] rounded-lg border border-amber-400/35 bg-amber-100/10 text-amber-300 px-2.5 py-2"
          >
            {a}
          </div>
        ))}
      </div>

      <div className="flex gap-2 px-3 py-2 border-t border-mid-gray/20">
        <Button variant="primary" size="sm" onClick={() => void gerar()} disabled={ocupado}>
          {ocupado ? "calculando…" : "Calcular"}
        </Button>
        <Button
          variant="secondary"
          size="sm"
          disabled={!saida}
          onClick={() => {
            if (saida) {
              aoInserir(saida.texto);
              aoFechar();
            }
          }}
        >
          Pôr na folha
        </Button>
        <Button variant="secondary" size="sm" onClick={() => { setValores({}); setSaida(null); setErro(""); }}>
          Limpar
        </Button>
      </div>
    </div>
  );
};

// ---------------------------------------------------------------------------
// Painel da idade óssea
// ---------------------------------------------------------------------------

const hoje = () => new Date().toISOString().slice(0, 10);

const PainelIdadeOssea: React.FC<{
  aoInserir: (t: string) => void;
  aoFechar: () => void;
}> = ({ aoInserir, aoFechar }) => {
  const [nascimento, setNascimento] = useState("");
  const [exame, setExame] = useState(hoje());
  const [sexo, setSexo] = useState("masculino");
  const [anos, setAnos] = useState("");
  const [meses, setMeses] = useState("");
  const [r, setR] = useState<Record<string, unknown> | null>(null);
  const [erro, setErro] = useState("");

  const calcular = useCallback(async () => {
    setErro("");
    try {
      const bruto = await invoke<string>("rotrix_idade_ossea", {
        nascimento,
        exame,
        sexo,
        anos: Number(anos) || 0,
        meses: Number(meses) || 0,
      });
      const d = JSON.parse(bruto || "{}") as Record<string, unknown>;
      if (!d.ok) {
        setErro(String(d.motivo || "não deu para calcular"));
        return;
      }
      setR(d);
    } catch (e) {
      setErro(String(e));
    }
  }, [nascimento, exame, sexo, anos, meses]);

  return (
    <div className="flex flex-col h-full min-h-0">
      <div className="flex items-center gap-2 px-3 py-2 border-b border-mid-gray/20">
        <span className="text-[12.5px] font-semibold">Idade óssea</span>
        <button
          type="button"
          onClick={aoFechar}
          className="ms-auto p-1 rounded hover:bg-mid-gray/20 cursor-pointer"
          title="fechar"
        >
          <X size={14} />
        </button>
      </div>

      <div className="flex-1 min-h-0 overflow-y-auto p-3 space-y-3">
        <label className="flex flex-col gap-0.5">
          <span className="text-[10px] text-mid-gray">Data de nascimento</span>
          <input
            type="date"
            value={nascimento}
            onChange={(e) => { setNascimento(e.target.value); setR(null); }}
            className="h-7 rounded-lg border border-mid-gray/25 bg-background px-2 text-[12px]"
          />
        </label>
        <label className="flex flex-col gap-0.5">
          <span className="text-[10px] text-mid-gray">Data do exame</span>
          <input
            type="date"
            value={exame}
            onChange={(e) => { setExame(e.target.value); setR(null); }}
            className="h-7 rounded-lg border border-mid-gray/25 bg-background px-2 text-[12px]"
          />
        </label>
        <div>
          <div className="text-[9.5px] font-bold tracking-wider text-mid-gray mb-1">SEXO</div>
          <div className="flex gap-1.5">
            {["masculino", "feminino"].map((s) => (
              <button
                key={s}
                type="button"
                onClick={() => { setSexo(s); setR(null); }}
                className={`text-[10.5px] px-2.5 py-1 rounded-md border cursor-pointer ${
                  sexo === s
                    ? "border-logo-primary/60 bg-logo-primary/25 font-bold"
                    : "border-mid-gray/25 hover:bg-mid-gray/15"
                }`}
              >
                {s}
              </button>
            ))}
          </div>
        </div>
        <div>
          <div className="text-[9.5px] font-bold tracking-wider text-mid-gray mb-1">
            IDADE ÓSSEA LIDA NO ATLAS
          </div>
          <div className="grid grid-cols-2 gap-2">
            <label className="flex flex-col gap-0.5">
              <span className="text-[10px] text-mid-gray">anos</span>
              <input
                value={anos}
                onChange={(e) => { setAnos(e.target.value); setR(null); }}
                inputMode="numeric"
                className="h-7 rounded-lg border border-mid-gray/25 bg-background px-2 text-[12px]"
              />
            </label>
            <label className="flex flex-col gap-0.5">
              <span className="text-[10px] text-mid-gray">meses</span>
              <input
                value={meses}
                onChange={(e) => { setMeses(e.target.value); setR(null); }}
                inputMode="numeric"
                className="h-7 rounded-lg border border-mid-gray/25 bg-background px-2 text-[12px]"
              />
            </label>
          </div>
        </div>

        {erro && (
          <div className="text-[11px] rounded-lg border border-amber-400/40 bg-amber-100/10 text-amber-300 px-2.5 py-2">
            {erro}
          </div>
        )}

        {r && (
          <>
            <div className="text-[10.5px] text-mid-gray border-t border-mid-gray/20 pt-2">
              idade cronológica <b className="text-text">{String(r.cronologica_meses)} meses</b> · DP{" "}
              <b className="text-text">{String(r.dp_meses)}</b> · Z{" "}
              <b className="text-text">{String(r.z)}</b> · percentil{" "}
              <b className="text-text">{String(r.percentil)}%</b>
            </div>
            <div className="rounded-lg bg-white text-black p-3">
              <pre className="whitespace-pre-wrap text-[11px] leading-[1.5]">
                {String(r.texto || "").replace(/\*\*/g, "")}
              </pre>
            </div>
          </>
        )}
      </div>

      <div className="flex gap-2 px-3 py-2 border-t border-mid-gray/20">
        <Button variant="primary" size="sm" onClick={() => void calcular()}>
          Calcular
        </Button>
        <Button
          variant="secondary"
          size="sm"
          disabled={!r}
          onClick={() => {
            if (r) {
              aoInserir(String(r.texto || ""));
              aoFechar();
            }
          }}
        >
          Pôr na folha
        </Button>
      </div>
    </div>
  );
};

// ---------------------------------------------------------------------------
// Painel das prescrições
// ---------------------------------------------------------------------------

const PainelPrescricoes: React.FC<{
  aoInserir: (t: string) => void;
  aoFechar: () => void;
}> = ({ aoInserir, aoFechar }) => {
  const [lista, setLista] = useState<{ titulo: string; gatilhos?: string[] }[]>([]);
  const [texto, setTexto] = useState("");
  const [escolhida, setEscolhida] = useState("");

  useEffect(() => {
    invoke<string>("rotrix_mascaras_banco", { busca: "prescricao", titulo: "", limite: 60 })
      .then((b) => {
        const d = JSON.parse(b || "{}") as { mascaras?: { titulo: string }[] };
        setLista((d.mascaras || []).filter((m) => m.titulo.startsWith("prescricao/")));
      })
      .catch(() => setLista([]));
  }, []);

  const abrir = (titulo: string) => {
    setEscolhida(titulo);
    invoke<string>("rotrix_mascaras_banco", { busca: "", titulo, limite: 1 })
      .then((b) => {
        const d = JSON.parse(b || "{}") as { texto?: string };
        setTexto(d.texto || "");
      })
      .catch(() => setTexto(""));
  };

  return (
    <div className="flex flex-col h-full min-h-0">
      <div className="flex items-center gap-2 px-3 py-2 border-b border-mid-gray/20">
        <span className="text-[12.5px] font-semibold">Prescrições</span>
        <button
          type="button"
          onClick={aoFechar}
          className="ms-auto p-1 rounded hover:bg-mid-gray/20 cursor-pointer"
          title="fechar"
        >
          <X size={14} />
        </button>
      </div>
      <div className="flex-1 min-h-0 flex">
        <div className="w-[190px] shrink-0 border-e border-mid-gray/20 overflow-y-auto p-1.5">
          {lista.map((m) => (
            <button
              key={m.titulo}
              type="button"
              onClick={() => abrir(m.titulo)}
              className={`w-full text-start px-2 py-1.5 rounded-md text-[11px] cursor-pointer ${
                escolhida === m.titulo ? "bg-logo-primary/25 font-semibold" : "hover:bg-mid-gray/15"
              }`}
            >
              {m.titulo.replace("prescricao/", "")}
            </button>
          ))}
          {lista.length === 0 && (
            <div className="text-[11px] text-mid-gray p-2">nenhuma prescrição no banco</div>
          )}
        </div>
        <div className="flex-1 min-w-0 overflow-y-auto p-3">
          {texto ? (
            <div className="rounded-lg bg-white text-black p-3">
              <pre className="whitespace-pre-wrap text-[11px] leading-[1.55]">
                {texto.replace(/\*\*/g, "")}
              </pre>
            </div>
          ) : (
            <div className="text-[11.5px] text-mid-gray">escolha uma prescrição à esquerda</div>
          )}
        </div>
      </div>
      <div className="flex gap-2 px-3 py-2 border-t border-mid-gray/20">
        <Button
          variant="primary"
          size="sm"
          disabled={!texto}
          onClick={() => {
            aoInserir(texto);
            aoFechar();
          }}
        >
          Pôr na folha
        </Button>
        <span className="text-[10.5px] text-mid-gray self-center">
          dose e volume saem em branco, de propósito
        </span>
      </div>
    </div>
  );
};

// ---------------------------------------------------------------------------

export const BotoesDaFolha: React.FC<Props> = ({ aoInserir, aoAvisar }) => {
  const [menu, setMenu] = useState<"" | "escanometria" | "idade" | "prescricao" | "calculos">("");
  const [painel, setPainel] = useState<
    { tipo: "medidas"; exame: Exame } | { tipo: "idade" } | { tipo: "prescricao" } | null
  >(null);
  const [campos, setCampos] = useState<Record<string, ConfExame>>({});

  useEffect(() => {
    invoke<string>("rotrix_medidas_campos")
      .then((b) => {
        const d = JSON.parse(b || "{}") as { ok?: boolean; exames?: Record<string, ConfExame> };
        if (d.ok && d.exames) setCampos(d.exames);
      })
      .catch(() => undefined);
  }, []);

  const fechar = () => setPainel(null);

  return (
    <>
      <div className="w-px h-[18px] bg-mid-gray/30 mx-1" />

      <div className="relative">
        <Fer
          titulo="Escanometria e panorâmicas"
          aberto={menu === "escanometria"}
          onClick={() => setMenu((m) => (m === "escanometria" ? "" : "escanometria"))}
        >
          <Ruler size={14} /> Escanometria <ChevronDown size={11} />
        </Fer>
        <Menu aberto={menu === "escanometria"} aoFechar={() => setMenu("")}>
          <div className="text-[9.5px] font-bold tracking-wider text-mid-gray px-2 pt-1 pb-1">
            O QUE MONTAR
          </div>
          {DIVISOES.map((d) => (
            <ItemMenu
              key={d.id}
              nome={d.nome}
              resumo={d.resumo}
              onClick={() => {
                setMenu("");
                setPainel({ tipo: "medidas", exame: d.id });
              }}
            />
          ))}
        </Menu>
      </div>

      <div className="relative">
        <Fer
          titulo="Cálculo de idade óssea"
          aberto={menu === "idade"}
          onClick={() => setMenu((m) => (m === "idade" ? "" : "idade"))}
        >
          <Bone size={14} /> Idade óssea <ChevronDown size={11} />
        </Fer>
        <Menu aberto={menu === "idade"} aoFechar={() => setMenu("")}>
          <div className="text-[9.5px] font-bold tracking-wider text-mid-gray px-2 pt-1 pb-1">
            MÉTODO
          </div>
          {IDADE_OSSEA.map((m) => (
            <ItemMenu
              key={m.id}
              nome={m.nome}
              resumo={m.resumo}
              onClick={() => {
                setMenu("");
                setPainel({ tipo: "idade" });
              }}
            />
          ))}
          <div className="px-2.5 py-1.5 text-[10.5px] text-mid-gray">
            Tanner-Whitehouse pede a pontuação osso a osso — entra depois.
          </div>
        </Menu>
      </div>

      <Fer titulo="Prescrições do banco" onClick={() => setPainel({ tipo: "prescricao" })}>
        <FileText size={14} /> Prescrição
      </Fer>

      <Fer
        titulo="Cálculos (ainda sem conteúdo definido)"
        onClick={() =>
          aoAvisar?.("o quarto botão ainda não tem nome: diga qual é e ele entra aqui")
        }
      >
        <Calculator size={14} /> Cálculos
      </Fer>

      {painel && (
        <div className="fixed inset-y-0 end-0 z-50 w-[430px] bg-background border-s border-mid-gray/30 shadow-2xl flex flex-col">
          {painel.tipo === "medidas" && (
            <PainelMedidas
              exame={painel.exame}
              conf={campos[painel.exame]}
              aoInserir={aoInserir}
              aoFechar={fechar}
            />
          )}
          {painel.tipo === "idade" && <PainelIdadeOssea aoInserir={aoInserir} aoFechar={fechar} />}
          {painel.tipo === "prescricao" && (
            <PainelPrescricoes aoInserir={aoInserir} aoFechar={fechar} />
          )}
        </div>
      )}
    </>
  );
};

export default BotoesDaFolha;

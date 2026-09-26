/* eslint-disable i18next/no-literal-string */
// Rotrix L-1000 v2 — aba Estruturados (coluna por níveis).
//
// Uma linha por nível discal, botões por achado. Marca e a frase sai montada.
// A montagem é por REGRA, no roteador: a mesma combinação dá sempre o mesmo
// texto. É isso que permite assinar sem reler.
//
// Quatro coisas que o desenho respeita, porque ele corrigiu cada uma:
//  · achado difuso (desidratação, osteofitose) é dito UMA VEZ, na faixa de
//    cima. Redução de altura não: essa é de cada disco.
//  · a cervical tem três zonas, não cinco — o espaço lateral lá é da artéria
//    vertebral.
//  · anterolistese e Modic não entram na linha do nível: são de alinhamento e
//    de corpo vertebral, cada um na sua seção — e cada seção tem o seu painel
//    aqui embaixo, inclusive musculatura.
//  · a prévia mostra o LAUDO INTEIRO, não só as alterações: quem monta o texto
//    completo é o roteador, a partir da máscara normal da região.
import React, { useCallback, useEffect, useMemo, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { LayoutGrid, CornerDownLeft, Copy, Trash2 } from "lucide-react";
import { Button } from "../ui/Button";
import { htmlDeTexto, semMarcas, copiarRico } from "./formatar";

type Segmento = "cervical" | "toracica" | "lombar";
type Modalidade = "tc" | "rm";

interface Botao {
  id: string;
  rotulo: string;
  exclui: string[];
}

interface CampoExtra {
  id: string;
  tipo: "botao" | "opcao" | "niveis" | "vertebra" | "vertebras";
  rotulo: string;
  opcoes?: string[];
  depende?: string;
}

interface SecaoExtra {
  id: string;
  secao: string;
  rotulo: string;
  campos: CampoExtra[];
}

interface Campos {
  niveis: string[];
  vertebras: string[];
  zonas: string[];
  lados: string[];
  difusos: { id: string; rotulo: string }[];
  botoes: Botao[];
  forame: Record<string, string[]>;
  extras: SecaoExtra[];
}

type ValorExtra = string | boolean | string[];

interface Nivel {
  marcados: string[];
  zona?: string;
  lado?: string;
  medida?: string;
  migracao?: string;
  contato?: string;
  plato?: string;
}

const SEGMENTOS: [Segmento, string][] = [
  ["cervical", "Cervical"],
  ["toracica", "Torácica"],
  ["lombar", "Lombar"],
];

const CONTATOS = [
  "em contato com a raiz descendente",
  "em contato com o saco dural",
  "sem contato radicular",
];

const MIGRACOES = ["caudal", "cranial"];
const PLATOS = ["superior", "inferior"];

// ---------------------------------------------------------------------------
// mapa do disco — corte axial, clicável. Clicar põe zona e lado de uma vez.
// ---------------------------------------------------------------------------

const MapaDoDisco: React.FC<{
  zonas: string[];
  zona?: string;
  lado?: string;
  aoEscolher: (zona: string, lado: string) => void;
}> = ({ zonas, zona, lado, aoEscolher }) => {
  // as zonas de um lado, da linha média para fora
  const fora = zonas.filter((z) => z !== "central");
  const passo = 150 / (fora.length + 0.5);

  const alvo = (z: string, l: string) => zona === z && (z === "central" || lado === l);

  return (
    <svg viewBox="0 0 360 150" className="w-full max-w-[360px]">
      {/* corpo vertebral (anterior) */}
      <path
        d="M60 26 Q180 6 300 26 L300 74 Q180 96 60 74 Z"
        fill="#ded9d4"
        stroke="#9a9a98"
        strokeWidth="1.2"
      />
      {/* canal (posterior) */}
      <path
        d="M120 96 Q180 74 240 96 Q252 116 180 126 Q108 116 120 96 Z"
        fill="#2c2b29"
        stroke="#9a9a98"
        strokeWidth="1.2"
      />
      <text x="180" y="18" textAnchor="middle" fontSize="9" fill="#9a9a98">
        anterior
      </text>
      <text x="180" y="146" textAnchor="middle" fontSize="9" fill="#9a9a98">
        posterior
      </text>
      <text x="14" y="84" fontSize="9" fill="#9a9a98">
        D
      </text>
      <text x="338" y="84" fontSize="9" fill="#9a9a98">
        E
      </text>

      {/* central, na linha média */}
      <g onClick={() => aoEscolher("central", "")} style={{ cursor: "pointer" }}>
        <circle
          cx="180"
          cy="88"
          r="13"
          fill={alvo("central", "") ? "#da5893" : "#4a4845"}
          stroke="#9a9a98"
          strokeWidth="1"
        />
        <title>central</title>
      </g>

      {/* as demais, espelhadas: direita do paciente à esquerda da imagem */}
      {fora.map((z, i) => {
        const dx = 26 + i * passo;
        return (
          <g key={z}>
            <g onClick={() => aoEscolher(z, "à direita")} style={{ cursor: "pointer" }}>
              <circle
                cx={180 - dx}
                cy={92 + i * 3}
                r="11"
                fill={alvo(z, "à direita") ? "#da5893" : "#4a4845"}
                stroke="#9a9a98"
                strokeWidth="1"
              />
              <title>{`${z} à direita`}</title>
            </g>
            <g onClick={() => aoEscolher(z, "à esquerda")} style={{ cursor: "pointer" }}>
              <circle
                cx={180 + dx}
                cy={92 + i * 3}
                r="11"
                fill={alvo(z, "à esquerda") ? "#da5893" : "#4a4845"}
                stroke="#9a9a98"
                strokeWidth="1"
              />
              <title>{`${z} à esquerda`}</title>
            </g>
          </g>
        );
      })}
    </svg>
  );
};

// ---------------------------------------------------------------------------

const Chip: React.FC<{
  on?: boolean;
  onClick: () => void;
  children: React.ReactNode;
  cor?: "pri" | "al";
}> = ({ on, onClick, children, cor = "pri" }) => (
  <button
    type="button"
    onClick={onClick}
    className={`text-[10.5px] px-2 py-1 rounded-md border cursor-pointer whitespace-nowrap ${
      on
        ? cor === "al"
          ? "border-amber-400/50 bg-amber-300/20 text-amber-200 font-bold"
          : "border-logo-primary/60 bg-logo-primary/25 font-bold"
        : "border-mid-gray/25 hover:bg-mid-gray/15 text-mid-gray"
    }`}
  >
    {children}
  </button>
);

export const EstruturadosPage: React.FC = () => {
  const [segmento, setSegmento] = useState<Segmento>("lombar");
  const [modalidade, setModalidade] = useState<Modalidade>("rm");
  const [campos, setCampos] = useState<Campos | null>(null);
  const [difusos, setDifusos] = useState<string[]>([]);
  const [niveis, setNiveis] = useState<Record<string, Nivel>>({});
  const [forame, setForame] = useState<Record<string, unknown>>({ niveis: [] });
  const [extras, setExtras] = useState<Record<string, Record<string, ValorExtra>>>({});
  const [listarTodos, setListarTodos] = useState(true);
  const [saida, setSaida] = useState<{ texto: string; conclusao: string } | null>(null);
  const [aviso, setAviso] = useState("");

  useEffect(() => {
    invoke<string>("rotrix_estruturados_campos", { segmento, modalidade })
      .then((b) => {
        const d = JSON.parse(b || "{}") as Campos & { ok?: boolean };
        if (d.ok !== false) setCampos(d);
      })
      .catch(() => setCampos(null));
    setDifusos([]);
    setNiveis({});
    setForame({ niveis: [] });
    setExtras({});
    setSaida(null);
  }, [segmento, modalidade]);

  // um só ajuste para todos os painéis de seção: o backend manda a lista de
  // campos, a tela só desenha. Campo novo no Python aparece aqui sem mexer no
  // TypeScript — foi o que faltou da última vez.
  const mexerExtra = useCallback((secao: string, campo: string, valor: ValorExtra) => {
    setSaida(null);
    setExtras((tudo) => ({ ...tudo, [secao]: { ...(tudo[secao] || {}), [campo]: valor } }));
  }, []);

  const marcar = useCallback(
    (nivel: string, id: string) => {
      setSaida(null);
      setNiveis((tudo) => {
        const n: Nivel = tudo[nivel] ? { ...tudo[nivel] } : { marcados: [] };
        const tem = n.marcados.includes(id);
        const botao = campos?.botoes.find((b) => b.id === id);
        let lista = tem ? n.marcados.filter((x) => x !== id) : [...n.marcados, id];
        if (!tem && botao) lista = lista.filter((x) => x === id || !botao.exclui.includes(x));
        // quem é excluído por "normal" também exclui "normal"
        if (!tem && id !== "normal") lista = lista.filter((x) => x !== "normal");
        n.marcados = lista;
        return { ...tudo, [nivel]: n };
      });
    },
    [campos],
  );

  const ajustar = (nivel: string, campo: keyof Nivel, valor: string) => {
    setSaida(null);
    setNiveis((tudo) => ({
      ...tudo,
      [nivel]: { ...(tudo[nivel] || { marcados: [] }), [campo]: valor },
    }));
  };

  const montar = useCallback(async () => {
    try {
      const b = await invoke<string>("rotrix_estruturados", {
        pedido: JSON.stringify({
          segmento,
          modalidade,
          difusos,
          niveis,
          forame,
          extras,
          listar_todos: listarTodos,
        }),
      });
      const d = JSON.parse(b || "{}") as {
        ok?: boolean;
        texto?: string;
        conclusao?: string;
        completo?: boolean;
        aviso?: string;
        motivo?: string;
      };
      if (!d.ok) {
        setAviso(d.motivo || "não deu para montar");
        return;
      }
      setSaida({ texto: d.texto || "", conclusao: d.conclusao || "" });
      // sem máscara no banco o texto sai só com os achados: melhor avisar do
      // que entregar meio laudo calado
      setAviso(d.completo === false ? "sem a máscara da região: saiu só os achados" : "");
    } catch (e) {
      setAviso(String(e));
    }
  }, [segmento, modalidade, difusos, niveis, forame, extras, listarTodos]);

  // O roteador já devolve o laudo inteiro, com CONCLUSÃO dentro. Nada de
  // grudar conclusão aqui: era isso que fazia sair laudo pela metade.
  const textoTodo = useMemo(() => saida?.texto || "", [saida]);

  const colar = async () => {
    if (!textoTodo) return;
    try {
      await invoke("rotrix_colar", { texto: textoTodo.replace(/\*\*/g, "") });
      setAviso("colado na janela que estava na frente");
    } catch (e) {
      setAviso(String(e));
    }
  };

  const nivelForame = (n: string) => {
    setSaida(null);
    setForame((f) => {
      const lista = (f.niveis as string[]) || [];
      return {
        ...f,
        niveis: lista.includes(n) ? lista.filter((x) => x !== n) : [...lista, n],
      };
    });
  };

  if (!campos) {
    return (
      <div className="p-6 text-[12.5px] text-mid-gray">
        o roteador ainda não respondeu com a grade deste segmento
      </div>
    );
  }

  return (
    <div className="h-full flex min-h-0">
      {/* grade */}
      <div className="flex-1 min-w-0 flex flex-col">
        <div className="flex items-center gap-2 px-3 py-2 border-b border-mid-gray/20 flex-wrap">
          <LayoutGrid size={15} />
          <span className="text-[13px] font-semibold">Estruturados</span>
          <div className="flex gap-1 ms-2">
            {SEGMENTOS.map(([id, nome]) => (
              <Chip key={id} on={segmento === id} onClick={() => setSegmento(id)}>
                {nome}
              </Chip>
            ))}
          </div>
          <div className="flex gap-1">
            {(["rm", "tc"] as Modalidade[]).map((m) => (
              <Chip key={m} on={modalidade === m} onClick={() => setModalidade(m)}>
                {m.toUpperCase()}
              </Chip>
            ))}
          </div>
          <Chip on={listarTodos} onClick={() => { setSaida(null); setListarTodos((x) => !x); }}>
            listar todos os níveis
          </Chip>
          <span className="ms-auto text-[11px] text-mid-gray">{aviso}</span>
        </div>

        <div className="flex-1 min-h-0 overflow-y-auto p-3 space-y-3">
          {/* faixa do difuso */}
          <div className="rounded-lg border border-amber-400/25 bg-amber-100/5 p-2.5">
            <div className="text-[9.5px] font-bold tracking-wider text-mid-gray mb-1.5">
              DIFUSO — DITO UMA VEZ, ANTES DOS NÍVEIS
            </div>
            <div className="flex flex-wrap gap-1.5">
              {campos.difusos.map((d) => (
                <Chip
                  key={d.id}
                  cor="al"
                  on={difusos.includes(d.id)}
                  onClick={() => {
                    setSaida(null);
                    setDifusos((x) =>
                      x.includes(d.id) ? x.filter((y) => y !== d.id) : [...x, d.id],
                    );
                  }}
                >
                  {d.rotulo}
                </Chip>
              ))}
            </div>
          </div>

          {/* uma linha por nível */}
          {campos.niveis.map((nivel) => {
            const n = niveis[nivel] || { marcados: [] };
            const temHernia =
              n.marcados.includes("protrusao") || n.marcados.includes("extrusao");
            return (
              <div
                key={nivel}
                className={`rounded-lg border p-2.5 ${
                  n.marcados.length
                    ? "border-logo-primary/35 bg-logo-primary/5"
                    : "border-mid-gray/20"
                }`}
              >
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-[12px] font-bold w-[58px] shrink-0">{nivel}</span>
                  {campos.botoes.map((b) => (
                    <Chip
                      key={b.id}
                      on={n.marcados.includes(b.id)}
                      onClick={() => marcar(nivel, b.id)}
                    >
                      {b.rotulo}
                    </Chip>
                  ))}
                </div>

                {temHernia && (
                  <div className="mt-2 ps-[58px] flex gap-3 flex-wrap items-start">
                    <div className="w-[300px]">
                      <MapaDoDisco
                        zonas={campos.zonas}
                        zona={n.zona}
                        lado={n.lado}
                        aoEscolher={(z, l) => {
                          ajustar(nivel, "zona", z);
                          ajustar(nivel, "lado", l);
                        }}
                      />
                    </div>
                    <div className="flex-1 min-w-[220px] space-y-1.5">
                      <div className="flex gap-1.5 items-center">
                        <span className="text-[10px] text-mid-gray w-[52px]">medida</span>
                        <input
                          value={n.medida || ""}
                          onChange={(e) => ajustar(nivel, "medida", e.target.value)}
                          inputMode="decimal"
                          placeholder="mm"
                          className="h-6 w-20 rounded-md border border-mid-gray/25 bg-background px-2 text-[11.5px]"
                        />
                      </div>
                      {n.marcados.includes("extrusao") && (
                        <div className="flex gap-1.5 items-center flex-wrap">
                          <span className="text-[10px] text-mid-gray w-[52px]">migração</span>
                          {MIGRACOES.map((m) => (
                            <Chip
                              key={m}
                              on={n.migracao === m}
                              onClick={() =>
                                ajustar(nivel, "migracao", n.migracao === m ? "" : m)
                              }
                            >
                              {m}
                            </Chip>
                          ))}
                        </div>
                      )}
                      <div className="flex gap-1.5 items-start flex-wrap">
                        <span className="text-[10px] text-mid-gray w-[52px] pt-1">contato</span>
                        <div className="flex flex-wrap gap-1.5 flex-1">
                          {CONTATOS.map((c) => (
                            <Chip
                              key={c}
                              on={n.contato === c}
                              onClick={() => ajustar(nivel, "contato", n.contato === c ? "" : c)}
                            >
                              {c.replace("em contato com ", "").replace("sem contato radicular", "sem contato")}
                            </Chip>
                          ))}
                        </div>
                      </div>
                    </div>
                  </div>
                )}

                {n.marcados.includes("schmorl") && (
                  <div className="mt-2 ps-[58px] flex gap-1.5 items-center">
                    <span className="text-[10px] text-mid-gray">platô</span>
                    {PLATOS.map((p) => (
                      <Chip key={p} on={(n.plato || "superior") === p} onClick={() => ajustar(nivel, "plato", p)}>
                        {p}
                      </Chip>
                    ))}
                  </div>
                )}
              </div>
            );
          })}

          {/* forames */}
          <div className="rounded-lg border border-mid-gray/20 p-2.5 space-y-2">
            <div className="text-[9.5px] font-bold tracking-wider text-mid-gray">
              ESTREITAMENTO FORAMINAL — SEM DIZER QUAL RAIZ
            </div>
            {(["simetria", "grau", "repercussao"] as const).map((k) => (
              <div key={k} className="flex gap-1.5 items-start flex-wrap">
                <span className="text-[10px] text-mid-gray w-[78px] pt-1">{k}</span>
                <div className="flex flex-wrap gap-1.5 flex-1">
                  {(campos.forame[k] || []).map((o) => (
                    <Chip
                      key={o}
                      on={forame[k] === o}
                      onClick={() => {
                        setSaida(null);
                        setForame((f) => ({ ...f, [k]: f[k] === o ? "" : o }));
                      }}
                    >
                      {o}
                    </Chip>
                  ))}
                </div>
              </div>
            ))}
            {forame.simetria === "assimétrico" && (
              <div className="flex gap-1.5 items-center flex-wrap">
                <span className="text-[10px] text-mid-gray w-[78px]">lado</span>
                {(campos.forame.lado || []).map((o) => (
                  <Chip
                    key={o}
                    on={forame.lado === o}
                    onClick={() => {
                      setSaida(null);
                      setForame((f) => ({ ...f, lado: f.lado === o ? "" : o }));
                    }}
                  >
                    {o}
                  </Chip>
                ))}
              </div>
            )}
            <div className="flex gap-1.5 items-center flex-wrap">
              <span className="text-[10px] text-mid-gray w-[78px]">níveis</span>
              {campos.niveis.map((n) => (
                <Chip
                  key={n}
                  on={((forame.niveis as string[]) || []).includes(n)}
                  onClick={() => nivelForame(n)}
                >
                  {n}
                </Chip>
              ))}
            </div>
          </div>

          {/* as demais seções do laudo — alinhamento, corpos, canal, facetas,
              medula, sacroilíacas, musculatura */}
          {(campos.extras || []).map((sec) => {
            const val = extras[sec.id] || {};
            const ligado = sec.campos.some(
              (c) => c.tipo === "botao" && val[c.id] === true,
            );
            return (
              <div
                key={sec.id}
                className={`rounded-lg border p-2.5 space-y-2 ${
                  ligado ? "border-logo-primary/35 bg-logo-primary/5" : "border-mid-gray/20"
                }`}
              >
                <div className="text-[9.5px] font-bold tracking-wider text-mid-gray">
                  {sec.rotulo.toUpperCase()}
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {sec.campos
                    .filter((c) => c.tipo === "botao" && !c.depende)
                    .map((c) => (
                      <Chip
                        key={c.id}
                        on={val[c.id] === true}
                        onClick={() => mexerExtra(sec.id, c.id, val[c.id] !== true)}
                      >
                        {c.rotulo}
                      </Chip>
                    ))}
                </div>
                {sec.campos
                  .filter((c) => c.depende && val[c.depende] === true)
                  .map((c) => {
                    const lista =
                      c.tipo === "niveis" || c.tipo === "vertebras"
                        ? c.tipo === "niveis"
                          ? campos.niveis
                          : campos.vertebras
                        : c.tipo === "vertebra"
                          ? campos.vertebras
                          : c.opcoes || [];
                    const multiplo = c.tipo === "niveis" || c.tipo === "vertebras";
                    const atual = val[c.id];
                    return (
                      <div key={c.id} className="flex gap-1.5 items-start flex-wrap">
                        <span className="text-[10px] text-mid-gray w-[78px] pt-1">
                          {c.rotulo}
                        </span>
                        <div className="flex flex-wrap gap-1.5 flex-1">
                          {c.tipo === "botao" ? (
                            <Chip
                              on={atual === true}
                              onClick={() => mexerExtra(sec.id, c.id, atual !== true)}
                            >
                              {c.rotulo}
                            </Chip>
                          ) : (
                            lista.map((o) => {
                              const on = multiplo
                                ? ((atual as string[]) || []).includes(o)
                                : atual === o;
                              return (
                                <Chip
                                  key={o}
                                  on={on}
                                  onClick={() => {
                                    if (multiplo) {
                                      const l = (atual as string[]) || [];
                                      mexerExtra(
                                        sec.id,
                                        c.id,
                                        l.includes(o) ? l.filter((x) => x !== o) : [...l, o],
                                      );
                                    } else {
                                      mexerExtra(sec.id, c.id, on ? "" : o);
                                    }
                                  }}
                                >
                                  {o.length > 46 ? `${o.slice(0, 44)}…` : o}
                                </Chip>
                              );
                            })
                          )}
                        </div>
                      </div>
                    );
                  })}
              </div>
            );
          })}
        </div>
      </div>

      {/* prévia */}
      <div className="w-[420px] shrink-0 border-s border-mid-gray/20 flex flex-col">
        <div className="px-3 py-2 border-b border-mid-gray/20 text-[11px] text-mid-gray">
          o que vai para a folha
        </div>
        <div className="flex-1 min-h-0 overflow-y-auto bg-white">
          <pre className="px-6 py-5 text-black text-[11.5px] leading-[1.65] whitespace-pre-wrap font-sans">
            {textoTodo.replace(/\*\*/g, "") || "marque os achados e aperte Montar"}
          </pre>
        </div>
        <div className="flex gap-2 px-3 py-2 border-t border-mid-gray/20 flex-wrap">
          <Button variant="primary" size="sm" onClick={() => void montar()}>
            Montar
          </Button>
          <Button variant="secondary" size="sm" disabled={!textoTodo} onClick={() => void colar()}>
            <span className="flex items-center gap-1.5">
              <CornerDownLeft size={14} /> Colar no RIS
            </span>
          </Button>
          <Button
            variant="secondary"
            size="sm"
            disabled={!textoTodo}
            onClick={() => {
              void copiarRico(htmlDeTexto(textoTodo), semMarcas(textoTodo)).then((rico) =>
                setAviso(
                  rico
                    ? "copiado, com a formatação"
                    : "copiado (sem formatação: o campo não aceita texto rico)",
                ),
              );
            }}
          >
            <span className="flex items-center gap-1.5">
              <Copy size={14} /> Copiar
            </span>
          </Button>
          <Button
            variant="secondary"
            size="sm"
            onClick={() => {
              setDifusos([]);
              setNiveis({});
              setForame({ niveis: [] });
              setExtras({});
              setSaida(null);
            }}
          >
            <span className="flex items-center gap-1.5">
              <Trash2 size={14} /> Limpar
            </span>
          </Button>
        </div>
      </div>
    </div>
  );
};

export default EstruturadosPage;

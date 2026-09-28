/* eslint-disable i18next/no-literal-string */
// Rotrix L-1000 — Estruturados: TC dos joelhos, protocolo de Lyon (27/09).
//
// Ele pediu o Lyon na aba Estruturados COM o passo a passo de cada medida (o
// infográfico) ao lado dos campos. Cada passo é um cartão: o desenho, onde e
// como medir, o valor de corte e, na mesma altura, os campos do lado direito e
// do esquerdo. O laudo sai por REGRA no roteador (lyon.py): os mesmos números
// dão sempre o mesmo texto. Campo vazio não vira lacuna; a linha sai.
//
// O guia (textos) vem do roteador: corrigir um passo é ATUALIZAR, sem .exe.
// Aqui ficam só os desenhos, que são esquemas nossos (joelho direito, lateral à
// esquerda, como no visualizador).
import React, { useEffect, useRef, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { LayoutGrid, CornerDownLeft, Copy, Trash2 } from "lucide-react";
import { Button } from "../ui/Button";
import { htmlDeTexto, semMarcas, copiarRico } from "./formatar";

type Lado = "direito" | "esquerdo" | "ambos";

interface CampoLyon {
  id: string;
  rotulo: string;
  tipo: "opcao" | "numero";
  unidade?: string;
  opcoes?: string[];
}

interface PassoLyon {
  id: string;
  titulo: string;
  onde: string;
  como: string[];
  corte: string;
  campos: CampoLyon[];
}

interface CamposLyon {
  ok?: boolean;
  lados: string[];
  passos: PassoLyon[];
  ossos: string[];
  frase_normal?: string;
}

// padrão quando o campo está vazio (o roteador faz o mesmo)
const PADRAO: Record<string, string> = { troclea: "habitual", posicao: "centrada" };

const LADOS_DE: Record<Lado, ("d" | "e")[]> = { direito: ["d"], esquerdo: ["e"], ambos: ["d", "e"] };
const NOME_LADO = { d: "direito", e: "esquerdo" };

// cores dos desenhos: legíveis no tema claro e no escuro
const MEDE = "#d98e04";
const REF = "#3b82f6";

// ---------------------------------------------------------------------------
// desenhos (esquemas, não imagens de exame)
// ---------------------------------------------------------------------------

const FEMUR =
  "M 120 70 Q 170 80 220 110 Q 270 82 318 76 C 360 90 380 140 372 190 C 368 225 350 250 318 252 C 290 254 270 245 262 225 C 256 200 240 188 222 188 C 204 188 188 200 182 225 C 174 245 150 256 120 254 C 88 252 66 225 64 190 C 60 140 80 85 120 70 Z";

const Osso: React.FC<{ d: string; transform?: string }> = ({ d, transform }) => (
  <path d={d} transform={transform} fill="currentColor" fillOpacity={0.08} stroke="currentColor" strokeWidth={2.5} />
);

const DesenhoTroclea = () => (
  <svg viewBox="0 0 440 300" className="w-full" role="img" aria-label="Axial da tróclea com o ângulo do sulco">
    <Osso d={FEMUR} />
    <line x1="220" y1="110" x2="112" y2="67" stroke={MEDE} strokeWidth={3.5} />
    <line x1="220" y1="110" x2="326" y2="73" stroke={MEDE} strokeWidth={3.5} />
    <path d="M 182.9 95.1 A 40 40 0 0 1 257.8 96.9" fill="none" stroke={MEDE} strokeWidth={2.5} />
    <circle cx="220" cy="110" r="5" fill={MEDE} />
    <text x="220" y="40" textAnchor="middle" fill={MEDE} fontSize="18" fontWeight="600">ângulo do sulco</text>
    <line x1="40" y1="256" x2="400" y2="256" stroke={REF} strokeWidth={2} strokeDasharray="8 5" />
    <text x="30" y="288" fill="currentColor" fontSize="15">lateral</text>
    <text x="410" y="288" textAnchor="end" fill="currentColor" fontSize="15">medial</text>
  </svg>
);

const DesenhoCaton = () => (
  <svg viewBox="0 0 440 300" className="w-full" role="img" aria-label="Sagital com AT e AP do Caton-Deschamps">
    <line x1="250" y1="0" x2="246" y2="100" stroke="currentColor" strokeWidth={2.5} />
    <line x1="345" y1="0" x2="354" y2="110" stroke="currentColor" strokeWidth={2.5} />
    <circle cx="300" cy="142" r="62" fill="currentColor" fillOpacity={0.08} stroke="currentColor" strokeWidth={2.5} />
    <Osso d="M 172 206 L 398 206 L 390 298 L 205 298 L 196 262 Q 158 252 164 232 Q 166 218 172 206 Z" />
    <Osso d="M 148 48 C 118 70 112 120 138 152 C 160 130 172 100 170 72 C 168 60 160 50 148 48 Z" />
    <line x1="138" y1="152" x2="160" y2="244" stroke="currentColor" strokeOpacity={0.6} strokeWidth={2} />
    <line x1="168" y1="66" x2="150" y2="138" stroke={REF} strokeWidth={5} />
    <line x1="150" y1="138" x2="172" y2="206" stroke={MEDE} strokeWidth={5} />
    <text x="182" y="100" fill={REF} fontSize="22" fontWeight="600">AP</text>
    <text x="180" y="170" fill={MEDE} fontSize="22" fontWeight="600">AT</text>
    <text x="300" y="262" textAnchor="middle" fill="currentColor" fontSize="15">tíbia</text>
    <text x="300" y="30" textAnchor="middle" fill="currentColor" fontSize="15">fêmur</text>
  </svg>
);

const DesenhoInclinacao = () => (
  <svg viewBox="0 0 440 300" className="w-full" role="img" aria-label="Axial com o eixo da patela e a tangente condilar">
    <Osso d={FEMUR} transform="translate(0,30)" />
    <line x1="30" y1="284" x2="410" y2="284" stroke={REF} strokeWidth={3} />
    <g transform="rotate(-14 215 55)">
      <Osso d="M 130 55 Q 215 12 300 55 Q 215 86 130 55 Z" />
      <line x1="98" y1="55" x2="332" y2="55" stroke={MEDE} strokeWidth={3.5} />
    </g>
    <line x1="80" y1="55" x2="360" y2="55" stroke={REF} strokeWidth={2} strokeDasharray="8 5" />
    <path d="M 135 55 A 80 80 0 0 0 137.4 74.4" fill="none" stroke={MEDE} strokeWidth={2.5} />
    <text x="40" y="100" fill={MEDE} fontSize="18" fontWeight="600">inclinação</text>
    <text x="220" y="274" textAnchor="middle" fill={REF} fontSize="15">tangente condilar posterior</text>
  </svg>
);

const DesenhoTTTG = () => (
  <svg viewBox="0 0 440 300" className="w-full" role="img" aria-label="Axiais sobrepostos com as perpendiculares do TT e do TG">
    <defs>
      <marker id="lyonSetaTG" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
        <path d="M 0 0 L 10 5 L 0 10 Z" fill={MEDE} />
      </marker>
    </defs>
    <Osso d={FEMUR} transform="translate(0,20)" />
    <path d="M 138 92 Q 160 62 182 92" fill="none" stroke="currentColor" strokeWidth={2} strokeDasharray="4 4" />
    <line x1="24" y1="274" x2="416" y2="274" stroke={REF} strokeWidth={3} />
    <line x1="220" y1="274" x2="220" y2="30" stroke={REF} strokeWidth={2.5} strokeDasharray="8 5" />
    <line x1="160" y1="274" x2="160" y2="30" stroke={MEDE} strokeWidth={2.5} strokeDasharray="8 5" />
    <circle cx="220" cy="130" r="5" fill={REF} />
    <circle cx="160" cy="76" r="5" fill={MEDE} />
    <line x1="166" y1="44" x2="214" y2="44" stroke={MEDE} strokeWidth={3} markerStart="url(#lyonSetaTG)" markerEnd="url(#lyonSetaTG)" />
    <text x="190" y="24" textAnchor="middle" fill={MEDE} fontSize="18" fontWeight="600">TT-TG</text>
    <text x="228" y="150" fill={REF} fontSize="16">TG</text>
    <text x="104" y="118" fill={MEDE} fontSize="16">TT</text>
  </svg>
);

const DesenhoTTPCL = () => (
  <svg viewBox="0 0 440 300" className="w-full" role="img" aria-label="Axial da tíbia com a borda medial do LCP e a TAT">
    <defs>
      <marker id="lyonSetaPCL" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
        <path d="M 0 0 L 10 5 L 0 10 Z" fill={MEDE} />
      </marker>
    </defs>
    <Osso d="M 90 150 C 90 90 150 60 220 62 C 300 60 360 90 362 150 C 364 200 340 238 300 240 C 270 242 250 228 232 226 C 214 226 196 242 160 240 C 118 238 90 205 90 150 Z" />
    <ellipse cx="232" cy="208" rx="16" ry="12" fill="currentColor" fillOpacity={0.2} stroke="currentColor" strokeWidth={2} />
    <path d="M 170 70 Q 190 40 210 70" fill="none" stroke="currentColor" strokeWidth={2} strokeDasharray="4 4" />
    <line x1="24" y1="242" x2="416" y2="242" stroke={REF} strokeWidth={3} />
    <line x1="248" y1="242" x2="248" y2="30" stroke={REF} strokeWidth={2.5} strokeDasharray="8 5" />
    <line x1="190" y1="242" x2="190" y2="30" stroke={MEDE} strokeWidth={2.5} strokeDasharray="8 5" />
    <circle cx="248" cy="208" r="5" fill={REF} />
    <circle cx="190" cy="54" r="5" fill={MEDE} />
    <line x1="196" y1="40" x2="242" y2="40" stroke={MEDE} strokeWidth={3} markerStart="url(#lyonSetaPCL)" markerEnd="url(#lyonSetaPCL)" />
    <text x="219" y="24" textAnchor="middle" fill={MEDE} fontSize="18" fontWeight="600">TT-PCL</text>
    <text x="256" y="200" fill={REF} fontSize="16">LCP</text>
    <text x="134" y="104" fill={MEDE} fontSize="16">TT</text>
    <text x="30" y="288" fill="currentColor" fontSize="15">lateral</text>
    <text x="410" y="288" textAnchor="end" fill="currentColor" fontSize="15">medial</text>
  </svg>
);

const DESENHOS: Record<string, React.FC> = {
  troclea: DesenhoTroclea,
  patela: DesenhoCaton,
  femoropatelar: DesenhoInclinacao,
  tttg: DesenhoTTTG,
  ttpcl: DesenhoTTPCL,
};

// ---------------------------------------------------------------------------

const Chip: React.FC<{ on?: boolean; onClick: () => void; children: React.ReactNode }> = ({ on, onClick, children }) => (
  <button
    type="button"
    onClick={onClick}
    aria-pressed={Boolean(on)}
    className={`text-[10.5px] px-2 py-1 rounded-md border cursor-pointer whitespace-nowrap ${
      on
        ? "border-logo-primary/60 bg-logo-primary/25 font-bold"
        : "border-mid-gray/25 hover:bg-mid-gray/15 text-mid-gray"
    }`}
  >
    {children}
  </button>
);

export const LyonEstruturado: React.FC<{ aoTrocar: () => void }> = ({ aoTrocar }) => {
  const [campos, setCampos] = useState<CamposLyon | null>(null);
  const [lado, setLado] = useState<Lado>("direito");
  const [valores, setValores] = useState<Record<string, string>>({});
  const [ossos, setOssos] = useState("");
  const [guia, setGuia] = useState(true);
  const [texto, setTexto] = useState("");
  const [avisos, setAvisos] = useState<string[]>([]);
  const [aviso, setAviso] = useState("");
  const pedido = useRef(0);

  useEffect(() => {
    invoke<string>("rotrix_estruturados_campos", { segmento: "lyon", modalidade: "tc" })
      .then((b) => {
        const d = JSON.parse(b || "{}") as CamposLyon;
        if (d.ok !== false && Array.isArray(d.passos)) setCampos(d);
        else setAviso("o roteador ainda não tem o Lyon: rode o ATUALIZAR");
      })
      .catch(() => setAviso("o roteador não respondeu"));
  }, []);

  // prévia ao vivo: cada mudança remonta o laudo no roteador (local, sem IA)
  useEffect(() => {
    if (!campos) return;
    const meu = ++pedido.current;
    const t = window.setTimeout(async () => {
      try {
        const b = await invoke<string>("rotrix_estruturados", {
          pedido: JSON.stringify({ tipo: "lyon", lado, valores, ossos }),
        });
        if (meu !== pedido.current) return; // chegou uma resposta velha
        const d = JSON.parse(b || "{}") as { ok?: boolean; texto?: string; avisos?: string[]; motivo?: string };
        if (d.ok) {
          setTexto(d.texto || "");
          setAvisos(d.avisos || []);
          setAviso("");
        } else {
          setAviso(d.motivo || "não deu para montar");
        }
      } catch (e) {
        if (meu === pedido.current) setAviso(String(e));
      }
    }, 200);
    return () => window.clearTimeout(t);
  }, [campos, lado, valores, ossos]);

  const mudar = (chave: string, v: string) => setValores((x) => ({ ...x, [chave]: v }));

  const colar = async () => {
    if (!texto) return;
    try {
      await invoke("rotrix_colar", { texto: texto.replace(/\*\*/g, "") });
      setAviso("colado na janela que estava na frente");
    } catch (e) {
      setAviso(String(e));
    }
  };

  const lados = LADOS_DE[lado];

  return (
    <div className="h-full flex min-h-0">
      <div className="flex-1 min-w-0 flex flex-col">
        <div className="flex items-center gap-2 px-3 py-2 border-b border-mid-gray/20 flex-wrap">
          <LayoutGrid size={15} />
          <span className="text-[13px] font-semibold">Estruturados</span>
          <div className="flex gap-1 ms-2">
            <Chip onClick={aoTrocar}>Coluna</Chip>
            <Chip on onClick={() => undefined}>Joelho · Lyon</Chip>
          </div>
          <div className="flex gap-1 ms-2">
            {(["direito", "esquerdo", "ambos"] as Lado[]).map((l) => (
              <Chip key={l} on={lado === l} onClick={() => setLado(l)}>
                {l === "ambos" ? "os dois joelhos" : `joelho ${l}`}
              </Chip>
            ))}
          </div>
          <Chip on={guia} onClick={() => setGuia((g) => !g)}>
            passo a passo
          </Chip>
          <span className="ms-auto text-[11px] text-mid-gray">{aviso}</span>
        </div>

        <div className="flex-1 min-h-0 overflow-y-auto p-3 space-y-3">
          {!campos && <div className="text-[12.5px] text-mid-gray">{aviso || "carregando o protocolo de Lyon…"}</div>}
          {campos?.passos.map((p, i) => {
            const Desenho = DESENHOS[p.id];
            return (
              <section key={p.id} className="rounded-lg border border-mid-gray/20 p-3 flex gap-4">
                {guia && Desenho && (
                  <div className="w-[190px] shrink-0 text-mid-gray">
                    <Desenho />
                  </div>
                )}
                <div className="flex-1 min-w-0 flex flex-col gap-2">
                  <div className="flex items-center gap-2">
                    <span className="text-[11px] font-bold px-1.5 py-0.5 rounded bg-amber-400/80 text-neutral-900">{i + 1}</span>
                    <h3 className="m-0 text-[13.5px] font-semibold">{p.titulo}</h3>
                  </div>
                  {guia && (
                    <div className="text-[11.5px] leading-[1.5] text-mid-gray flex flex-col gap-1">
                      <div>
                        <b className="text-text">Onde:</b> {p.onde}
                      </div>
                      <ol className="m-0 ps-4 list-decimal flex flex-col gap-0.5">
                        {p.como.map((c) => (
                          <li key={c}>{c}</li>
                        ))}
                      </ol>
                      <div className="text-amber-500 font-semibold">{p.corte}</div>
                    </div>
                  )}
                  <div className="flex flex-col gap-1.5 mt-1">
                    {lados.map((s) => (
                      <div key={s} className="flex items-center gap-2 flex-wrap">
                        <span className="w-[62px] text-[11px] font-semibold">{NOME_LADO[s]}</span>
                        {p.campos.map((c) => {
                          const chave = `${c.id}_${s}`;
                          const v = valores[chave] || "";
                          if (c.tipo === "opcao") {
                            const atual = v || PADRAO[c.id] || "";
                            return (
                              <div key={chave} className="flex gap-1 flex-wrap">
                                {(c.opcoes || []).map((o) => (
                                  <Chip key={o} on={atual === o} onClick={() => mudar(chave, o)}>
                                    {o}
                                  </Chip>
                                ))}
                              </div>
                            );
                          }
                          return (
                            <label key={chave} className="flex items-center gap-1 text-[11px] text-mid-gray">
                              {c.rotulo}
                              <input
                                type="text"
                                inputMode="decimal"
                                value={v}
                                onChange={(e) => mudar(chave, e.target.value)}
                                aria-label={`${c.rotulo}, joelho ${NOME_LADO[s]}`}
                                className="w-[64px] px-1.5 py-1 rounded-md border border-mid-gray/30 bg-background text-text text-[12px]"
                              />
                              {c.unidade}
                            </label>
                          );
                        })}
                      </div>
                    ))}
                  </div>
                </div>
              </section>
            );
          })}
          {campos && (
            <section className="rounded-lg border border-mid-gray/20 p-3 flex flex-col gap-2">
              <h3 className="m-0 text-[13.5px] font-semibold">Estruturas ósseas</h3>
              <div className="flex gap-1 flex-wrap">
                {campos.ossos.map((o) => (
                  <Chip key={o} on={(ossos || campos.ossos[0]) === o} onClick={() => setOssos(o)}>
                    {o}
                  </Chip>
                ))}
              </div>
            </section>
          )}
        </div>
      </div>

      {/* prévia */}
      <div className="w-[420px] shrink-0 border-s border-mid-gray/20 flex flex-col">
        <div className="px-3 py-2 border-b border-mid-gray/20 text-[11px] text-mid-gray">o que vai para a folha</div>
        {avisos.length > 0 && (
          <div className="px-3 py-2 border-b border-amber-400/30 bg-amber-100/10 text-[11px] text-amber-500 flex flex-col gap-1">
            {avisos.map((a) => (
              <div key={a}>conferir: {a}</div>
            ))}
          </div>
        )}
        <div className="flex-1 min-h-0 overflow-y-auto papel">
          <pre className="px-6 py-5 text-[11.5px] leading-[1.65] whitespace-pre-wrap font-sans">
            {texto.replace(/\*\*/g, "") || "preencha as medidas: o laudo aparece aqui"}
          </pre>
        </div>
        <div className="flex gap-2 px-3 py-2 border-t border-mid-gray/20 flex-wrap">
          <Button variant="primary" size="sm" disabled={!texto} onClick={() => void colar()}>
            <span className="flex items-center gap-1.5">
              <CornerDownLeft size={14} /> Colar no RIS
            </span>
          </Button>
          <Button
            variant="secondary"
            size="sm"
            disabled={!texto}
            onClick={() => {
              void copiarRico(htmlDeTexto(texto), semMarcas(texto)).then((rico) =>
                setAviso(rico ? "copiado, com a formatação" : "copiado (sem formatação: o campo não aceita texto rico)"),
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
              setValores({});
              setOssos("");
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

export default LyonEstruturado;

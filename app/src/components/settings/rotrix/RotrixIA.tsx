/* eslint-disable i18next/no-literal-string */
// Rotrix L-1000: IA sob demanda — provedor e modelo, IA por exame, chaves e gasto.
// Grava no config.json do roteador em uso (comandos rotrix_ia_* em rotrix.rs).
import React, { useCallback, useEffect, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { SettingsGroup } from "../../ui/SettingsGroup";
import { SettingContainer } from "../../ui/SettingContainer";
import { Button } from "../../ui/Button";
import { Input } from "../../ui/Input";

interface Rota {
  provedor?: string;
  modelo?: string;
  modo?: string;
  raciocinio?: string;
}

interface GastoModelo {
  usd?: number;
  chamadas?: number;
  tokens_in?: number;
  tokens_out?: number;
}

interface EstadoIA {
  ativa: boolean;
  provedor: string;
  modelo: string;
  modo_ia?: string;
  ia_por_exame: Record<string, Rota | string>;
  chaves: Record<string, boolean>;
  limite_mes_usd: number;
  gasto: {
    mes?: string;
    usd?: number;
    chamadas?: number;
    tokens_in?: number;
    tokens_out?: number;
    por_modelo?: Record<string, GastoModelo>;
  };
  roteador_parado?: boolean;
}

const PROVEDORES: { value: string; label: string }[] = [
  { value: "anthropic", label: "Anthropic (Claude)" },
  { value: "openai", label: "OpenAI (GPT)" },
  { value: "gemini", label: "Google (Gemini)" },
  { value: "openrouter", label: "OpenRouter" },
  { value: "ollama", label: "Ollama (no próprio computador)" },
];

const COM_CHAVE = ["anthropic", "openai", "gemini", "openrouter"];

const MODELOS: Record<string, { value: string; label: string }[]> = {
  anthropic: [
    { value: "claude-haiku-4-5-20251001", label: "Haiku 4.5 (básico: só formatar)" },
    { value: "claude-sonnet-5", label: "Sonnet 5" },
    { value: "claude-opus-5", label: "Opus 5" },
    { value: "claude-fable-5-1", label: "Fable 5.1" },
  ],
  openai: [
    { value: "gpt-5.6-luna", label: "GPT-5.6 Luna (básico: só formatar)" },
    { value: "gpt-5.6-terra", label: "GPT-5.6 Terra" },
    { value: "gpt-5.6-sol", label: "GPT-5.6 Sol" },
  ],
  gemini: [{ value: "gemini-3.8-flash", label: "Gemini 3.8 Flash" }],
  openrouter: [],
  ollama: [],
  compativel: [],
};

const EXAMES: { chave: string; nome: string }[] = [
  { chave: "rx", nome: "Radiografia" },
  { chave: "tc", nome: "Tomografia" },
  { chave: "rm", nome: "Ressonância" },
  { chave: "angio", nome: "Angio" },
  { chave: "us", nome: "Ultrassom" },
  { chave: "mamo", nome: "Mamografia" },
  { chave: "onco", nome: "Oncológico (RECIST)" },
  { chave: "padrao", nome: "Demais exames" },
];

// Como o Bruno descreveu: básicos (Luna, Haiku) só formatam; RM e oncológico no Sonnet.
const SUGESTAO: Record<string, Rota> = {
  rx: { provedor: "openai", modelo: "gpt-5.6-luna", modo: "formatar" },
  rm: { provedor: "anthropic", modelo: "claude-sonnet-5" },
  onco: { provedor: "anthropic", modelo: "claude-sonnet-5" },
};

const OUTRO = "__outro__";

// o config aceita "provedor:modelo" em texto; a tela trabalha com objeto
const normalizarRotas = (v: unknown): Record<string, Rota> => {
  const out: Record<string, Rota> = {};
  if (v === null || typeof v !== "object") return out;
  for (const [k, e] of Object.entries(v as Record<string, unknown>)) {
    if (typeof e === "string") {
      const i = e.indexOf(":");
      out[k] =
        i > 0
          ? { provedor: e.slice(0, i).trim().toLowerCase(), modelo: e.slice(i + 1).trim() }
          : { modelo: e.trim() };
    } else if (e !== null && typeof e === "object") {
      out[k] = e as Rota;
    }
  }
  return out;
};

const classeSelect =
  "px-2 py-1 text-sm bg-mid-gray/10 border border-mid-gray/80 rounded-md hover:border-logo-primary focus:outline-none focus:border-logo-primary";

const usd = (v: number | undefined): string =>
  "US$ " +
  (v ?? 0).toFixed(v !== undefined && v > 0 && v < 0.01 ? 4 : 2).replace(".", ",");

const milhar = (v: number | undefined): string =>
  (v ?? 0).toLocaleString("pt-BR");

// Escolha de modelo: lista pronta do provedor + "outro" (digitado).
const EscolhaModelo: React.FC<{
  provedor: string;
  modelo: string;
  onChange: (m: string) => void;
  vazio?: string;
}> = ({ provedor, modelo, onChange, vazio }) => {
  const lista = MODELOS[provedor] ?? [];
  const conhecido = lista.some((m) => m.value === modelo);
  const [digitando, setDigitando] = useState<boolean>(
    modelo !== "" && !conhecido,
  );
  // quem usa este componente troca a "key" quando o provedor muda ou a
  // configuração é recarregada: o estado inicial acima é recalculado
  return (
    <div className="flex gap-2 items-center">
      <select
        className={classeSelect}
        value={digitando ? OUTRO : modelo}
        onChange={(e) => {
          const v = e.target.value;
          if (v === OUTRO) {
            setDigitando(true);
          } else {
            setDigitando(false);
            onChange(v);
          }
        }}
      >
        <option value="">{vazio ?? "escolha o modelo"}</option>
        {lista.map((m) => (
          <option key={m.value} value={m.value}>
            {m.label}
          </option>
        ))}
        <option value={OUTRO}>outro (digitar o nome)</option>
      </select>
      {digitando && (
        <Input
          variant="compact"
          className="w-48"
          value={modelo}
          placeholder="nome exato do modelo"
          onChange={(e) => onChange(e.target.value.trim())}
        />
      )}
    </div>
  );
};

export const RotrixIA: React.FC = () => {
  const [estado, setEstado] = useState<EstadoIA | null>(null);
  const [ativa, setAtiva] = useState<boolean>(false);
  const [provedor, setProvedor] = useState<string>("anthropic");
  const [modelo, setModelo] = useState<string>("");
  const [limite, setLimite] = useState<string>("25");
  const [rotas, setRotas] = useState<Record<string, Rota>>({});
  const [chaves, setChaves] = useState<Record<string, string>>({});
  const [mensagem, setMensagem] = useState<string>("");
  const [alterado, setAlterado] = useState<boolean>(false);
  const [versao, setVersao] = useState<number>(0);

  const carregar = useCallback(async () => {
    try {
      const txt = await invoke<string>("rotrix_ia_estado");
      const e = JSON.parse(txt) as EstadoIA;
      setEstado(e);
      setAtiva(Boolean(e.ativa));
      setProvedor(e.provedor || "anthropic");
      setModelo(e.modelo || "");
      setLimite(String(e.limite_mes_usd ?? 0));
      setRotas(normalizarRotas(e.ia_por_exame));
      setAlterado(false);
      setVersao((v) => v + 1);
    } catch (err) {
      setMensagem("Não consegui ler a configuração da IA: " + String(err));
    }
  }, []);

  useEffect(() => {
    void carregar();
  }, [carregar]);

  const mudarRota = (exame: string, parte: Partial<Rota>) => {
    setRotas((r) => {
      const atual: Rota = { ...(r[exame] ?? {}), ...parte };
      if (parte.provedor !== undefined) {
        atual.modelo = "";
      }
      return { ...r, [exame]: atual };
    });
    setAlterado(true);
  };

  const salvar = async () => {
    const teto = Number(limite.replace(",", "."));
    if (!Number.isFinite(teto) || teto < 0 || teto > 1000) {
      setMensagem("O teto do mês deve ser um número entre 0 e 1000.");
      return;
    }
    const limpas: Record<string, Rota> = {};
    for (const [k, r] of Object.entries(rotas)) {
      const item: Rota = {};
      if (r.provedor) item.provedor = r.provedor;
      if (r.modelo) item.modelo = r.modelo;
      if (r.modo) item.modo = r.modo;
      if (r.raciocinio) item.raciocinio = r.raciocinio;
      if (item.provedor && !item.modelo && item.provedor !== provedor) {
        const nome = EXAMES.find((x) => x.chave === k)?.nome ?? k;
        setMensagem("Escolha o modelo de " + nome + ".");
        return;
      }
      if (Object.keys(item).length > 0) limpas[k] = item;
    }
    try {
      await invoke("rotrix_ia_salvar", {
        ajustes: JSON.stringify({
          ativa,
          provedor,
          modelo,
          limite_mes_usd: teto,
          ia_por_exame: limpas,
        }),
      });
      setMensagem("Salvo. Vale a partir do próximo pedido à IA.");
      await carregar();
    } catch (err) {
      setMensagem("Não consegui salvar: " + String(err));
    }
  };

  const gravarChave = async (p: string) => {
    const k = (chaves[p] ?? "").trim();
    if (k === "") return;
    try {
      await invoke("rotrix_chave_salvar", { provedor: p, chave: k });
      setChaves((c) => ({ ...c, [p]: "" }));
      setMensagem("Chave gravada neste computador.");
      await carregar();
    } catch (err) {
      setMensagem(String(err));
    }
  };

  const apagarChave = async (p: string) => {
    try {
      await invoke("rotrix_chave_apagar", { provedor: p });
      setMensagem("Chave apagada.");
      await carregar();
    } catch (err) {
      setMensagem(String(err));
    }
  };

  const porModelo = Object.entries(estado?.gasto?.por_modelo ?? {}).sort(
    (a, b) => (b[1].usd ?? 0) - (a[1].usd ?? 0),
  );
  const nomeProvedor = (p: string) =>
    PROVEDORES.find((x) => x.value === p)?.label ?? p;

  return (
    <div className="space-y-6">
      <SettingsGroup
        title="Inteligência artificial (sob demanda)"
        description="O banco de máscaras continua sendo o padrão. A IA só entra quando você pede: Ctrl+Alt+A, “revisar”, “analisar” ou “formar laudo com IA”."
      >
        <SettingContainer
          title="IA ligada"
          description="Desligada, nada sai do computador."
          grouped={true}
        >
          <input
            type="checkbox"
            className="w-4 h-4 cursor-pointer"
            checked={ativa}
            onChange={(e) => {
              setAtiva(e.target.checked);
              setAlterado(true);
            }}
          />
        </SettingContainer>
        <SettingContainer
          title="Provedor padrão"
          description="Usado nos exames sem regra própria na tabela abaixo."
          grouped={true}
        >
          <select
            className={classeSelect}
            value={provedor}
            onChange={(e) => {
              setProvedor(e.target.value);
              setModelo("");
              setAlterado(true);
            }}
          >
            {PROVEDORES.map((p) => (
              <option key={p.value} value={p.value}>
                {p.label}
              </option>
            ))}
          </select>
        </SettingContainer>
        <SettingContainer
          title="Modelo padrão"
          description="Modelos básicos (Haiku, Luna) servem para formatar; os maiores analisam."
          grouped={true}
        >
          <EscolhaModelo
            key={provedor + "-" + versao}
            provedor={provedor}
            modelo={modelo}
            onChange={(m) => {
              setModelo(m);
              setAlterado(true);
            }}
          />
        </SettingContainer>
      </SettingsGroup>

      <SettingsGroup
        title="IA por tipo de exame"
        description="“Só formatar”: a IA só organiza, põe cada achado na linha certa e corrige a transcrição. Não descreve nem raciocina, e uma trava aponta no topo do laudo tudo o que ela acrescentar."
      >
        <div className="p-4 space-y-2">
          <div className="grid grid-cols-[9rem_1fr_1.6fr_6rem] gap-2 text-xs text-mid-gray">
            <span>Exame</span>
            <span>Provedor</span>
            <span>Modelo</span>
            <span>Só formatar</span>
          </div>
          {EXAMES.map((ex) => {
            const r = rotas[ex.chave] ?? {};
            const prov = r.provedor ?? "";
            return (
              <div
                key={ex.chave}
                className="grid grid-cols-[9rem_1fr_1.6fr_6rem] gap-2 items-center"
              >
                <span className="text-sm">{ex.nome}</span>
                <select
                  className={classeSelect}
                  value={prov}
                  onChange={(e) =>
                    mudarRota(ex.chave, { provedor: e.target.value })
                  }
                >
                  <option value="">igual ao padrão</option>
                  {PROVEDORES.map((p) => (
                    <option key={p.value} value={p.value}>
                      {p.label}
                    </option>
                  ))}
                </select>
                <EscolhaModelo
                  key={ex.chave + "-" + (prov || provedor) + "-" + versao}
                  provedor={prov || provedor}
                  modelo={r.modelo ?? ""}
                  vazio={prov === "" ? "modelo padrão" : "escolha o modelo"}
                  onChange={(m) => mudarRota(ex.chave, { modelo: m })}
                />
                <input
                  type="checkbox"
                  className="w-4 h-4 cursor-pointer justify-self-center"
                  checked={r.modo === "formatar"}
                  onChange={(e) =>
                    mudarRota(ex.chave, {
                      modo: e.target.checked ? "formatar" : "",
                    })
                  }
                />
              </div>
            );
          })}
          <div className="flex gap-2 pt-2">
            <Button
              variant="secondary"
              size="sm"
              onClick={() => {
                setRotas((r) => ({ ...r, ...SUGESTAO }));
                setAlterado(true);
                setVersao((v) => v + 1);
              }}
            >
              Usar a sugestão (RX na Luna só formatando; RM e oncológico no
              Sonnet)
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                setRotas({});
                setAlterado(true);
                setVersao((v) => v + 1);
              }}
            >
              Limpar a tabela
            </Button>
          </div>
        </div>
      </SettingsGroup>

      <SettingsGroup
        title="Chaves de API"
        description="A chave fica só neste computador, num arquivo da pasta do roteador. Nunca mande a chave por chat ou e-mail."
      >
        {COM_CHAVE.map((p) => (
          <SettingContainer
            key={p}
            title={nomeProvedor(p)}
            description={
              estado?.chaves?.[p]
                ? "Chave configurada."
                : "Sem chave: os exames que usam este provedor não vão para a IA."
            }
            grouped={true}
          >
            <div className="flex gap-2 items-center">
              <span
                className={`text-xs ${estado?.chaves?.[p] ? "text-green-500" : "text-mid-gray"}`}
              >
                {estado?.chaves?.[p] ? "configurada" : "sem chave"}
              </span>
              <Input
                variant="compact"
                type="password"
                autoComplete="off"
                className="w-40"
                placeholder="colar a chave"
                value={chaves[p] ?? ""}
                onChange={(e) =>
                  setChaves((c) => ({ ...c, [p]: e.target.value }))
                }
              />
              <Button
                variant="secondary"
                size="sm"
                disabled={(chaves[p] ?? "").trim() === ""}
                onClick={() => void gravarChave(p)}
              >
                Gravar
              </Button>
              {estado?.chaves?.[p] && (
                <Button
                  variant="danger-ghost"
                  size="sm"
                  onClick={() => void apagarChave(p)}
                >
                  Apagar
                </Button>
              )}
            </div>
          </SettingContainer>
        ))}
      </SettingsGroup>

      <SettingsGroup
        title="Gasto com IA neste mês"
        description="Contado a partir dos tokens que a própria API cobra em cada pedido."
      >
        <div className="p-4 space-y-3">
          <div className="flex flex-wrap gap-6 text-sm">
            <span>
              Total: <b>{usd(estado?.gasto?.usd)}</b>
            </span>
            <span>Pedidos: {milhar(estado?.gasto?.chamadas)}</span>
            <span>
              Tokens: {milhar(estado?.gasto?.tokens_in)} entrada ·{" "}
              {milhar(estado?.gasto?.tokens_out)} saída
            </span>
          </div>
          {porModelo.length > 0 && (
            <table className="w-full text-xs">
              <thead className="text-mid-gray">
                <tr>
                  <th className="text-start font-normal">Modelo</th>
                  <th className="text-end font-normal">Pedidos</th>
                  <th className="text-end font-normal">Tokens</th>
                  <th className="text-end font-normal">Gasto</th>
                </tr>
              </thead>
              <tbody>
                {porModelo.map(([nome, g]) => (
                  <tr key={nome}>
                    <td>{nome}</td>
                    <td className="text-end">{milhar(g.chamadas)}</td>
                    <td className="text-end">
                      {milhar((g.tokens_in ?? 0) + (g.tokens_out ?? 0))}
                    </td>
                    <td className="text-end">{usd(g.usd)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          <div className="flex items-center gap-2 text-sm">
            <span>Teto do mês (US$):</span>
            <Input
              variant="compact"
              className="w-24"
              value={limite}
              onChange={(e) => {
                setLimite(e.target.value);
                setAlterado(true);
              }}
            />
            <span className="text-xs text-mid-gray">
              Ao chegar no teto, a IA para até o mês seguinte. 0 = sem teto.
            </span>
          </div>
        </div>
      </SettingsGroup>

      <div className="flex items-center gap-3 px-1">
        <Button
          variant="primary"
          size="sm"
          onClick={() => void salvar()}
          disabled={!alterado}
        >
          Salvar a configuração da IA
        </Button>
        <Button variant="secondary" size="sm" onClick={() => void carregar()}>
          Recarregar
        </Button>
        {estado?.roteador_parado && (
          <span className="text-xs text-mid-gray">
            O roteador está parado: as chaves só aparecem quando ele estiver
            rodando.
          </span>
        )}
        {mensagem !== "" && (
          <span className="text-xs text-mid-gray">{mensagem}</span>
        )}
      </div>
    </div>
  );
};

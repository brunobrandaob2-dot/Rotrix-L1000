/* eslint-disable i18next/no-literal-string */
// Rotrix L-1000 — anexar imagem à folha.
//
// Três entradas: colar (Ctrl+V do print do RadiAnt), escolher arquivo, ou
// arrastar para cá. Antes de a imagem entrar no laudo ela passa por UMA etapa
// obrigatória: recorte e limpeza.
//
// O motivo não é estética. Print de visualizador traz o nome do paciente
// GRAVADO NOS PIXELS, nas bordas — e triagem de texto não enxerga pixel. O
// recorte tira a borda e o redesenho num canvas descarta todo metadado do
// arquivo original (EXIF, comentários, data, equipamento). O que entra na folha
// é uma imagem nova, feita aqui, não o arquivo que veio.
import React, { useCallback, useEffect, useRef, useState } from "react";
import { X, ImagePlus, Crop, Check } from "lucide-react";
import { Button } from "../ui/Button";

interface Props {
  aberto: boolean;
  aoFechar: () => void;
  /** entrega o PNG já recortado e sem metadado, como data URL */
  aoConfirmar: (dataUrl: string) => void;
}

interface Corte {
  x: number;
  y: number;
  w: number;
  h: number;
}

// Quanto da borda a proposta automática tira. É onde os visualizadores põem
// cabeçalho e rodapé com nome, data de nascimento e número de acesso.
const MARGEM = 0.07;

export const ImagemNaFolha: React.FC<Props> = ({ aberto, aoFechar, aoConfirmar }) => {
  const [imagem, setImagem] = useState<HTMLImageElement | null>(null);
  const [corte, setCorte] = useState<Corte | null>(null);
  const [arrastando, setArrastando] = useState<{ x: number; y: number } | null>(null);
  const [erro, setErro] = useState("");
  const tela = useRef<HTMLCanvasElement>(null);
  const caixa = useRef<HTMLDivElement>(null);

  const carregar = useCallback((origem: Blob | string) => {
    setErro("");
    const img = new Image();
    img.onload = () => {
      setImagem(img);
      setCorte({
        x: Math.round(img.width * MARGEM),
        y: Math.round(img.height * MARGEM),
        w: Math.round(img.width * (1 - 2 * MARGEM)),
        h: Math.round(img.height * (1 - 2 * MARGEM)),
      });
    };
    img.onerror = () => setErro("não consegui abrir essa imagem");
    img.src = typeof origem === "string" ? origem : URL.createObjectURL(origem);
  }, []);

  // colar
  useEffect(() => {
    if (!aberto) return;
    const colar = (e: ClipboardEvent) => {
      const itens = Array.from(e.clipboardData?.items || []);
      const img = itens.find((i) => i.type.startsWith("image/"));
      if (!img) return;
      const arq = img.getAsFile();
      if (arq) {
        e.preventDefault();
        carregar(arq);
      }
    };
    window.addEventListener("paste", colar);
    return () => window.removeEventListener("paste", colar);
  }, [aberto, carregar]);

  // desenhar a prévia com o retângulo do corte
  useEffect(() => {
    const c = tela.current;
    if (!c || !imagem || !corte) return;
    const largura = Math.min(imagem.width, 560);
    const escala = largura / imagem.width;
    c.width = largura;
    c.height = Math.round(imagem.height * escala);
    const ctx = c.getContext("2d");
    if (!ctx) return;
    ctx.clearRect(0, 0, c.width, c.height);
    ctx.drawImage(imagem, 0, 0, c.width, c.height);
    ctx.fillStyle = "rgba(0,0,0,.55)";
    ctx.fillRect(0, 0, c.width, c.height);
    ctx.save();
    ctx.beginPath();
    ctx.rect(corte.x * escala, corte.y * escala, corte.w * escala, corte.h * escala);
    ctx.clip();
    ctx.clearRect(0, 0, c.width, c.height);
    ctx.drawImage(imagem, 0, 0, c.width, c.height);
    ctx.restore();
    ctx.strokeStyle = "#f28cbb";
    ctx.lineWidth = 2;
    ctx.strokeRect(corte.x * escala, corte.y * escala, corte.w * escala, corte.h * escala);
  }, [imagem, corte]);

  const posicao = (e: React.MouseEvent) => {
    const c = tela.current;
    if (!c || !imagem) return null;
    const r = c.getBoundingClientRect();
    const escala = imagem.width / r.width;
    return {
      x: Math.round((e.clientX - r.left) * escala),
      y: Math.round((e.clientY - r.top) * escala),
    };
  };

  const confirmar = useCallback(() => {
    if (!imagem || !corte) return;
    // O redesenho num canvas novo é o que limpa: sai um PNG feito agora, sem
    // nenhum metadado do arquivo de origem.
    const c = document.createElement("canvas");
    c.width = corte.w;
    c.height = corte.h;
    const ctx = c.getContext("2d");
    if (!ctx) {
      setErro("não consegui preparar a imagem");
      return;
    }
    ctx.drawImage(imagem, corte.x, corte.y, corte.w, corte.h, 0, 0, corte.w, corte.h);
    aoConfirmar(c.toDataURL("image/png"));
    setImagem(null);
    setCorte(null);
    aoFechar();
  }, [imagem, corte, aoConfirmar, aoFechar]);

  if (!aberto) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-6">
      <div className="w-[640px] max-h-full flex flex-col rounded-xl border border-mid-gray/30 bg-background shadow-2xl">
        <div className="flex items-center gap-2 px-3 py-2 border-b border-mid-gray/20">
          <ImagePlus size={15} />
          <span className="text-[12.5px] font-semibold">Anexar imagem à folha</span>
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
          {!imagem && (
            <div
              ref={caixa}
              onDragOver={(e) => e.preventDefault()}
              onDrop={(e) => {
                e.preventDefault();
                const arq = e.dataTransfer.files?.[0];
                if (arq && arq.type.startsWith("image/")) carregar(arq);
              }}
              className="h-44 rounded-xl border-2 border-dashed border-mid-gray/35 flex flex-col items-center justify-center gap-2 text-[12px] text-mid-gray"
            >
              <ImagePlus size={22} />
              <div>
                <b>Ctrl+V</b> para colar o print · ou arraste a imagem para cá
              </div>
              <label className="cursor-pointer text-[11.5px] underline">
                escolher arquivo
                <input
                  type="file"
                  accept="image/*"
                  className="hidden"
                  onChange={(e) => {
                    const arq = e.target.files?.[0];
                    if (arq) carregar(arq);
                  }}
                />
              </label>
            </div>
          )}

          {imagem && corte && (
            <>
              <div className="text-[11px] rounded-lg border border-amber-400/40 bg-amber-100/10 text-amber-300 px-2.5 py-2 flex gap-2">
                <Crop size={14} className="shrink-0 mt-0.5" />
                <span>
                  Print de visualizador tem <b>nome de paciente gravado nos pixels</b>, nas
                  bordas. Arraste sobre a imagem para escolher o que fica. Só o que está claro
                  entra no laudo.
                </span>
              </div>
              <canvas
                ref={tela}
                className="w-full rounded-lg cursor-crosshair"
                onMouseDown={(e) => {
                  const p = posicao(e);
                  if (p) {
                    setArrastando(p);
                    setCorte({ x: p.x, y: p.y, w: 1, h: 1 });
                  }
                }}
                onMouseMove={(e) => {
                  if (!arrastando) return;
                  const p = posicao(e);
                  if (!p) return;
                  setCorte({
                    x: Math.min(arrastando.x, p.x),
                    y: Math.min(arrastando.y, p.y),
                    w: Math.max(4, Math.abs(p.x - arrastando.x)),
                    h: Math.max(4, Math.abs(p.y - arrastando.y)),
                  });
                }}
                onMouseUp={() => setArrastando(null)}
                onMouseLeave={() => setArrastando(null)}
              />
              <div className="text-[10.5px] text-mid-gray">
                recorte: {corte.w} × {corte.h} px · o arquivo que entra é um PNG novo, feito
                aqui, sem nenhum metadado do original
              </div>
            </>
          )}

          {erro && (
            <div className="text-[11px] rounded-lg border border-amber-400/40 bg-amber-100/10 text-amber-300 px-2.5 py-2">
              {erro}
            </div>
          )}
        </div>

        <div className="flex gap-2 px-3 py-2 border-t border-mid-gray/20">
          <Button variant="primary" size="sm" disabled={!imagem} onClick={confirmar}>
            <span className="flex items-center gap-1.5">
              <Check size={14} /> Pôr na folha
            </span>
          </Button>
          <Button
            variant="secondary"
            size="sm"
            disabled={!imagem}
            onClick={() => {
              if (!imagem) return;
              setCorte({
                x: Math.round(imagem.width * MARGEM),
                y: Math.round(imagem.height * MARGEM),
                w: Math.round(imagem.width * (1 - 2 * MARGEM)),
                h: Math.round(imagem.height * (1 - 2 * MARGEM)),
              });
            }}
          >
            Corte sugerido
          </Button>
          <Button
            variant="secondary"
            size="sm"
            onClick={() => {
              setImagem(null);
              setCorte(null);
              setErro("");
            }}
          >
            Outra imagem
          </Button>
        </div>
      </div>
    </div>
  );
};

export default ImagemNaFolha;

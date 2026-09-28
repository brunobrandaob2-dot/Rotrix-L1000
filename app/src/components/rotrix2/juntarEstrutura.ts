// A mesma estrutura numa linha só.
//
// 27/09: ele dita frases prontas uma a uma — "bandas parenquimatosas basais",
// depois outra opacidade, depois "enfisema centrolobular nos lobos superiores" — e
// cada uma entrava na folha como uma linha nova "Parênquima pulmonar: ...". Ele quer
// o parênquima numa linha só, com todas as frases que ditou dele. O roteador já
// juntava quando vinham no MESMO ditado (roteador.py, montar); ditadas uma a uma,
// cada frase chega sozinha, sem a folha. Então quem junta é a folha, na hora em que
// a frase entra — sem IA, sem custo.
//
// A regra é a mesma do roteador: a frase de normalidade da linha que já estava
// ("sem alterações significativas", "Não há consolidações...") sai quando chega um
// achado novo da mesma estrutura — senão o laudo se contradiz.

import { rotuloDeEstrutura } from "./formatar";

/** Frase de normalidade: a mesma lista do roteador (_NEGATIVA em roteador.py). */
const NEGATIVA = /^(?:não há|não se|não são|ausência|sem |demais |restante)/i;

const CABECALHOS = new Set([
  "tecnica", "indicacao clinica", "indicacao", "analise", "relatorio", "achados",
  "comparacao", "conclusao", "impressao", "opiniao", "achado adicional", "observacao",
]);

export const normalizar = (t: string): string =>
  (t || "")
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .replace(/\s+/g, " ")
    .trim()
    .toLowerCase();

/** A linha é de estrutura ("Rótulo:  texto") e não cabeçalho de seção? Devolve a chave. */
export const chaveDaEstrutura = (linha: string): { chave: string; rotulo: string; resto: string } | null => {
  const r = rotuloDeEstrutura(linha);
  if (!r) return null;
  const chave = normalizar(r.rotulo);
  if (CABECALHOS.has(chave)) return null;
  return { chave, rotulo: r.rotulo, resto: r.resto };
};

/** Palavras de normalidade que não nomeiam achado (a mesma lista do roteador). */
const GENERICAS_NEG = [
  "significativ", "evident", "alteraco", "alteraca", "sinais", "achados", "demais", "restant",
  "segment", "pulmona", "parenqu", "suspeit", "adjacen", "habitua", "preserv", "normais",
  "limites", "outras", "outros",
];

/**
 * Tira a frase de normalidade que nega um achado presente na mesma linha
 * ("consolidação no LIE... Não há consolidações" — o laudo se contradizendo).
 * Mesma regra do roteador (_sem_contradicao em roteador.py).
 */
export const semContradicao = (frases: string[]): string[] => {
  const palavras = (f: string) => normalizar(f).replace(/[^a-z0-9 ]/g, " ").split(/\s+/);
  const radicais = new Set(
    frases.filter((f) => !NEGATIVA.test(f)).flatMap(palavras).filter((w) => w.length >= 6).map((w) => w.slice(0, 7)),
  );
  return frases.filter((f) => {
    if (!NEGATIVA.test(f)) return true;
    const nega = palavras(f)
      .filter((w) => w.length >= 6 && !GENERICAS_NEG.some((g) => w.startsWith(g)))
      .map((w) => w.slice(0, 7));
    return !nega.some((r) => radicais.has(r));
  });
};

const frasesDe = (t: string): string[] =>
  (t || "")
    .trim()
    .split(/(?<=[.])\s+/)
    .map((f) => f.trim())
    .filter(Boolean);

/**
 * O texto da estrutura depois de juntar o achado novo.
 * `existente`: o que já está depois do rótulo; `novo`: o que chegou depois do rótulo.
 */
export const juntarConteudo = (existente: string, novo: string): string => {
  const chegou = (novo || "").trim();
  if (!chegou) return (existente || "").trim();
  const ficam = frasesDe(existente).filter((f) => !NEGATIVA.test(f));
  // a mesma frase ditada de novo não duplica
  if (ficam.some((f) => normalizar(f) === normalizar(chegou))) return ficam.join(" ");
  if (!ficam.length) return chegou;
  const ultima = ficam[ficam.length - 1];
  if (!/[.!?]$/.test(ultima)) ficam[ficam.length - 1] = ultima + ".";
  return semContradicao([...ficam, ...frasesDe(chegou.charAt(0).toUpperCase() + chegou.slice(1))]).join(" ");
};

/**
 * Onde cada linha que chegou deve entrar. `linhasDaFolha`: o texto de cada linha da
 * folha, em ordem. Devolve, para cada linha que chegou, o índice da linha da folha que
 * a recebe (mesma estrutura, dentro da ANÁLISE quando há ANÁLISE) ou -1 (entra normal).
 */
export const destinosNaFolha = (linhasDaFolha: string[], chegaram: string[]): number[] => {
  const cab = (l: string) => {
    const m = /^\s*([^:]{2,40}):?\s*$/.exec(l || "");
    const n = normalizar((m ? m[1] : l || "").replace(/:.*/, ""));
    return CABECALHOS.has(n) ? n : null;
  };
  let ini = 0;
  let fim = linhasDaFolha.length;
  const a = linhasDaFolha.findIndex((l) => {
    const c = cab(l);
    return c === "analise" || c === "relatorio" || c === "achados";
  });
  if (a >= 0) {
    ini = a + 1;
    const f = linhasDaFolha.findIndex((l, i) => i > a && cab(l) !== null);
    fim = f >= 0 ? f : linhasDaFolha.length;
  }
  return chegaram.map((linha) => {
    const e = chaveDaEstrutura(linha);
    if (!e || !e.resto) return -1;
    for (let i = ini; i < fim; i++) {
      const d = chaveDaEstrutura(linhasDaFolha[i]);
      if (d && d.chave === e.chave) return i;
    }
    return -1;
  });
};

const escapar = (t: string) =>
  t.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

/**
 * Junta na folha, na hora em que o ditado chega. As linhas de estrutura que já
 * existem na ANÁLISE recebem a frase nova (pelo próprio editor, então o Ctrl+Z
 * desfaz); devolve o texto que SOBROU para entrar do jeito de sempre.
 * Máscara inteira (com cabeçalho de seção) não passa por aqui.
 */
export const juntarNaFolha = (folha: HTMLElement, texto: string): { sobra: string; juntadas: number } => {
  const chegaram = (texto || "").replace(/\r\n?/g, "\n").split("\n").filter((l) => l.trim());
  const temCabecalho = chegaram.some((l) => CABECALHOS.has(normalizar(l.split(":")[0])));
  if (!chegaram.length || temCabecalho) return { sobra: texto, juntadas: 0 };

  const blocos = Array.from(folha.children).filter((e) =>
    /^(DIV|P)$/.test(e.tagName),
  ) as HTMLElement[];
  const linhas = blocos.map((b) => (b.innerText || b.textContent || "").replace(/\n+$/, ""));
  const destinos = destinosNaFolha(linhas, chegaram);
  if (destinos.every((d) => d < 0)) return { sobra: texto, juntadas: 0 };

  const sel = window.getSelection();
  const antes = sel && sel.rangeCount ? sel.getRangeAt(0).cloneRange() : null;
  const sobra: string[] = [];
  let juntadas = 0;
  chegaram.forEach((linha, k) => {
    const i = destinos[k];
    const atual = i >= 0 ? chaveDaEstrutura(linhas[i]) : null;
    const nova = chaveDaEstrutura(linha);
    if (i < 0 || !atual || !nova || !sel) {
      sobra.push(linha);
      return;
    }
    const conteudo = juntarConteudo(atual.resto, nova.resto);
    const r = document.createRange();
    r.selectNodeContents(blocos[i]);
    sel.removeAllRanges();
    sel.addRange(r);
    document.execCommand("insertHTML", false, `<b>${escapar(atual.rotulo)}:</b>  ${escapar(conteudo)}`);
    linhas[i] = `${atual.rotulo}:  ${conteudo}`;
    juntadas++;
  });
  // o que sobrou entra onde o cursor estava antes
  if (sobra.length && antes && sel) {
    sel.removeAllRanges();
    sel.addRange(antes);
  }
  return { sobra: sobra.join("\n"), juntadas };
};

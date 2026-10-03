// 03/10, pergunta dele: "pq a nuvem está dizendo que a IA está bloqueada?".
// A tela mostrava "a IA não respondeu (nuvem_bloqueada)": nem o que barrou, nem
// onde. O roteador (2026-10-03.1) passou a mandar o motivo com a explicação,
// "nuvem_bloqueada: data completa “12/08/2025” na folha"; aqui vira frase.
// Não é defeito: é a triagem da §17 (identificador não sai do computador).

/** "" quando o motivo não é recusa da triagem. */
export const motivoDoBloqueio = (motivo?: string): string => {
  const bruto = motivo || "";
  if (!bruto.toLowerCase().startsWith("nuvem_bloqueada")) return "";
  const oque = bruto.replace(/^nuvem_bloqueada\s*:?\s*/i, "").trim();
  return (
    "não enviei para a IA: " +
    (oque ||
      "o texto tem um identificador (data completa, número longo ou linha do paciente)") +
    ". Tire isso e aperte de novo."
  );
};

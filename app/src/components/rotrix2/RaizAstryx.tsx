// Rotrix v2, fase 6: o tema do Astryx em volta do app inteiro.
//
// O claro/escuro continua sendo o do Rotrix (Configurações › Aparência): ele
// escreve `data-theme` na raiz do documento (lib/utils/theme.ts) ou deixa o
// Windows decidir. Aqui só se acompanha esse atributo, para os componentes do
// Astryx seguirem o mesmo modo.
import React, { useEffect, useState } from "react";
import { Theme } from "@astryxdesign/core/theme";
import { themes, defaultThemeSlug } from "../../astryx-themes";

type Modo = "light" | "dark" | "system";

const modoAtual = (): Modo => {
  const t = document.documentElement.dataset.theme;
  return t === "light" || t === "dark" ? t : "system";
};

export const RaizAstryx: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [modo, setModo] = useState<Modo>(modoAtual);
  useEffect(() => {
    const obs = new MutationObserver(() => setModo(modoAtual()));
    obs.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
    return () => obs.disconnect();
  }, []);
  return (
    <Theme theme={themes[defaultThemeSlug]} mode={modo}>
      {children}
    </Theme>
  );
};

export default RaizAstryx;

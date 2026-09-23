/* eslint-disable i18next/no-literal-string */
// Rotrix L-1000 v2 — aba Configurações.
//
// As telas de ajuste que já existiam continuam as mesmas; o que muda é o
// caminho até elas: em cima, uma fileira de assuntos (Geral, Rotrix, Modelos,
// Avançado…) em vez de uma segunda barra lateral, porque a barra lateral agora
// é das abas do app.
import React, { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Palette } from "lucide-react";
import { SECTIONS_CONFIG, type SidebarSection } from "../Sidebar";
import { SeletorCores } from "../settings/rotrix/SeletorCores";
import { DebugSettings } from "../settings";
import type { OnboardingPreviewStep } from "../settings";
import AccessibilityPermissions from "../AccessibilityPermissions";
import SecureInputWarning from "../SecureInputWarning";
import { useSettings } from "../../hooks/useSettings";

interface Props {
  secao: SidebarSection;
  aoTrocarSecao: (s: SidebarSection) => void;
  aoVerOnboarding: (passo: OnboardingPreviewStep) => void;
}

export const ConfigPage: React.FC<Props> = ({
  secao,
  aoTrocarSecao,
  aoVerOnboarding,
}) => {
  const { t } = useTranslation();
  const { settings } = useSettings();
  const rolagem = useRef<HTMLDivElement>(null);
  const [cores, setCores] = useState(false);
  const caixaCores = useRef<HTMLDivElement>(null);

  useEffect(() => {
    rolagem.current?.scrollTo({ top: 0 });
  }, [secao]);

  useEffect(() => {
    if (!cores) return;
    const fora = (e: MouseEvent) => {
      if (caixaCores.current && !caixaCores.current.contains(e.target as Node)) {
        setCores(false);
      }
    };
    const esc = (e: KeyboardEvent) => {
      if (e.key === "Escape") setCores(false);
    };
    document.addEventListener("mousedown", fora);
    document.addEventListener("keydown", esc);
    return () => {
      document.removeEventListener("mousedown", fora);
      document.removeEventListener("keydown", esc);
    };
  }, [cores]);

  const assuntos = Object.entries(SECTIONS_CONFIG)
    .filter(([, c]) => c.enabled(settings))
    .map(([id, c]) => ({ id: id as SidebarSection, ...c }));

  const Ativa =
    secao === "debug"
      ? () => <DebugSettings onPreviewOnboarding={aoVerOnboarding} />
      : SECTIONS_CONFIG[secao]?.component || SECTIONS_CONFIG.general.component;

  return (
    <div className="flex flex-col h-full min-h-0 bg-mid-gray/5">
      {/* fileira de assuntos */}
      <div className="flex items-center gap-1 px-3 py-2 bg-background border-b border-mid-gray/20 overflow-x-auto">
        {assuntos.map((a) => {
          const Icone = a.icon;
          const ativo = secao === a.id;
          return (
            <button
              key={a.id}
              type="button"
              onClick={() => aoTrocarSecao(a.id)}
              className={`flex items-center gap-1.5 shrink-0 rounded-lg px-2.5 py-1 text-xs cursor-pointer transition-colors ${
                ativo
                  ? "bg-logo-primary/25 font-semibold"
                  : "hover:bg-mid-gray/15 opacity-85 hover:opacity-100"
              }`}
            >
              <Icone width={15} height={15} className="shrink-0" />
              {t(a.labelKey)}
            </button>
          );
        })}
        <div ref={caixaCores} className="relative ms-auto shrink-0">
          {cores && (
            <div className="absolute top-9 end-0 z-20 w-72 p-3 rounded-lg border border-mid-gray/30 bg-background shadow-lg">
              <p className="text-xs font-semibold mb-2">Cor do app</p>
              <SeletorCores />
            </div>
          )}
          <button
            type="button"
            aria-expanded={cores}
            onClick={() => setCores((v) => !v)}
            className={`flex items-center gap-1.5 rounded-lg px-2.5 py-1 text-xs cursor-pointer transition-colors ${
              cores ? "bg-mid-gray/20" : "hover:bg-mid-gray/15 opacity-85"
            }`}
          >
            <Palette width={15} height={15} /> Cores
          </button>
        </div>
      </div>

      <div ref={rolagem} className="flex-1 min-h-0 overflow-y-auto">
        <div className="flex flex-col items-center p-4 gap-4">
          <AccessibilityPermissions />
          <SecureInputWarning />
          <Ativa />
        </div>
      </div>
    </div>
  );
};

export default ConfigPage;

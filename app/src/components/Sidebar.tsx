import React, { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import {
  Cog,
  FlaskConical,
  History,
  Info,
  Sparkles,
  Cpu,
  Mic,
  Stethoscope,
  Palette,
} from "lucide-react";
import HandyTextLogo from "./icons/HandyTextLogo";
import { useSettings } from "../hooks/useSettings";
import {
  GeneralSettings,
  AdvancedSettings,
  HistorySettings,
  DebugSettings,
  AboutSettings,
  PostProcessingSettings,
  ModelsSettings,
} from "./settings";
import { RotrixSettings } from "./settings/rotrix/RotrixSettings";
import { SeletorCores } from "./settings/rotrix/SeletorCores";

export type SidebarSection = keyof typeof SECTIONS_CONFIG;

interface IconProps {
  width?: number | string;
  height?: number | string;
  size?: number | string;
  className?: string;
  [key: string]: any;
}

interface SectionConfig {
  labelKey: string;
  icon: React.ComponentType<IconProps>;
  component: React.ComponentType;
  enabled: (settings: any) => boolean;
}

export const SECTIONS_CONFIG = {
  general: {
    labelKey: "sidebar.general",
    icon: Mic,
    component: GeneralSettings,
    enabled: () => true,
  },
  rotrix: {
    labelKey: "sidebar.rotrix",
    icon: Stethoscope,
    component: RotrixSettings,
    enabled: () => true,
  },
  history: {
    labelKey: "sidebar.history",
    icon: History,
    component: HistorySettings,
    enabled: () => true,
  },
  models: {
    labelKey: "sidebar.models",
    icon: Cpu,
    component: ModelsSettings,
    enabled: () => true,
  },
  advanced: {
    labelKey: "sidebar.advanced",
    icon: Cog,
    component: AdvancedSettings,
    enabled: () => true,
  },
  postprocessing: {
    labelKey: "sidebar.postProcessing",
    icon: Sparkles,
    component: PostProcessingSettings,
    enabled: (settings) => settings?.post_process_enabled ?? false,
  },
  debug: {
    labelKey: "sidebar.debug",
    icon: FlaskConical,
    component: DebugSettings,
    enabled: (settings) => settings?.debug_mode ?? false,
  },
  about: {
    labelKey: "sidebar.about",
    icon: Info,
    component: AboutSettings,
    enabled: () => true,
  },
} as const satisfies Record<string, SectionConfig>;

interface SidebarProps {
  activeSection: SidebarSection;
  onSectionChange: (section: SidebarSection) => void;
}

export const Sidebar: React.FC<SidebarProps> = ({
  activeSection,
  onSectionChange,
}) => {
  const { t } = useTranslation();
  const { settings } = useSettings();

  // Rotrix: botão "Cores" no pé da barra, para trocar a cor a qualquer hora
  const [coresAberto, setCoresAberto] = useState(false);
  const caixaCores = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!coresAberto) return;
    const fora = (e: MouseEvent) => {
      if (caixaCores.current && !caixaCores.current.contains(e.target as Node)) {
        setCoresAberto(false);
      }
    };
    const esc = (e: KeyboardEvent) => {
      if (e.key === "Escape") setCoresAberto(false);
    };
    document.addEventListener("mousedown", fora);
    document.addEventListener("keydown", esc);
    return () => {
      document.removeEventListener("mousedown", fora);
      document.removeEventListener("keydown", esc);
    };
  }, [coresAberto]);

  const availableSections = Object.entries(SECTIONS_CONFIG)
    .filter(([_, config]) => config.enabled(settings))
    .map(([id, config]) => ({ id: id as SidebarSection, ...config }));

  return (
    <div className="flex flex-col w-40 h-full border-e border-mid-gray/20 items-center px-2">
      <HandyTextLogo width={120} className="m-4" />
      <div className="flex flex-col w-full items-center gap-1 pt-2 border-t border-mid-gray/20">
        {availableSections.map((section) => {
          const Icon = section.icon;
          const isActive = activeSection === section.id;

          return (
            <div
              key={section.id}
              className={`flex gap-2 items-center p-2 w-full rounded-lg cursor-pointer transition-colors ${
                isActive
                  ? "bg-logo-primary/25 font-semibold"
                  : "hover:bg-mid-gray/20 hover:opacity-100 opacity-85"
              }`}
              onClick={() => onSectionChange(section.id)}
            >
              <Icon width={24} height={24} className="shrink-0" />
              <p
                className="text-sm font-medium truncate"
                title={t(section.labelKey)}
              >
                {t(section.labelKey)}
              </p>
            </div>
          );
        })}
      </div>
      <div ref={caixaCores} className="relative w-full mt-auto pb-3 pt-2">
        {coresAberto && (
          <div className="absolute bottom-14 start-0 z-20 w-72 p-3 rounded-lg border border-mid-gray/30 bg-background shadow-lg">
            {/* eslint-disable-next-line i18next/no-literal-string */}
            <p className="text-xs font-semibold mb-2">Cor do app</p>
            <SeletorCores />
          </div>
        )}
        <button
          type="button"
          aria-expanded={coresAberto}
          onClick={() => setCoresAberto((v) => !v)}
          className={`flex gap-2 items-center p-2 w-full rounded-lg cursor-pointer transition-colors ${
            coresAberto ? "bg-mid-gray/20" : "hover:bg-mid-gray/20 opacity-85 hover:opacity-100"
          }`}
        >
          <Palette width={24} height={24} className="shrink-0" />
          {/* eslint-disable-next-line i18next/no-literal-string */}
          <p className="text-sm font-medium truncate">Cores</p>
        </button>
      </div>
    </div>
  );
};

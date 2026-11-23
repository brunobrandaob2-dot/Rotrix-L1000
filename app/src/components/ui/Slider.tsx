// Fase 6 (Astryx): a barra de arrastar é o Slider do Astryx. A linha (título,
// descrição), o valor à direita e o botão de voltar ao padrão continuam.
import React from "react";
import { Slider as AxSlider } from "@astryxdesign/core/Slider";
import { SettingContainer } from "./SettingContainer";
import { ResetButton } from "./ResetButton";

interface SliderProps {
  value: number;
  onChange: (value: number) => void;
  min: number;
  max: number;
  step?: number;
  disabled?: boolean;
  label: string;
  description: string;
  descriptionMode?: "inline" | "tooltip";
  grouped?: boolean;
  showValue?: boolean;
  formatValue?: (value: number) => string;
  onReset?: () => void;
  isResetting?: boolean;
}

export const Slider: React.FC<SliderProps> = ({
  value,
  onChange,
  min,
  max,
  step = 0.01,
  disabled = false,
  label,
  description,
  descriptionMode = "tooltip",
  grouped = false,
  showValue = true,
  formatValue = (v) => v.toFixed(2),
  onReset,
  isResetting = false,
}) => (
  <SettingContainer
    title={label}
    description={description}
    descriptionMode={descriptionMode}
    grouped={grouped}
    layout="horizontal"
    disabled={disabled}
  >
    {/* o Slider do Astryx não tem largura própria (o <input> antigo tinha):
        sem largura mínima ele sumia na linha da configuração */}
    <div className="w-full min-w-[220px] flex items-center gap-2">
      <div className="flex-1 min-w-[150px]">
        <AxSlider
          label={label}
          isLabelHidden
          value={value}
          onChange={(v: number) => onChange(v)}
          min={min}
          max={max}
          step={step}
          isDisabled={disabled}
          width="100%"
        />
      </div>
      {showValue && <span className="text-sm font-medium text-text/90 w-12 text-end">{formatValue(value)}</span>}
      {onReset && <ResetButton onClick={onReset} disabled={disabled || isResetting} />}
    </div>
  </SettingContainer>
);

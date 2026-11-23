// Fase 6 (Astryx): o interruptor das Configurações é o Switch do Astryx. A
// linha (título, descrição, dica) continua sendo a SettingContainer.
import React from "react";
import { Switch } from "@astryxdesign/core/Switch";
import { SettingContainer } from "./SettingContainer";

interface ToggleSwitchProps {
  checked: boolean;
  onChange: (checked: boolean) => void;
  disabled?: boolean;
  isUpdating?: boolean;
  label: string;
  description: string;
  descriptionMode?: "inline" | "tooltip";
  grouped?: boolean;
  tooltipPosition?: "top" | "bottom";
}

export const ToggleSwitch: React.FC<ToggleSwitchProps> = ({
  checked,
  onChange,
  disabled = false,
  isUpdating = false,
  label,
  description,
  descriptionMode = "tooltip",
  grouped = false,
  tooltipPosition = "top",
}) => (
  <SettingContainer
    title={label}
    description={description}
    descriptionMode={descriptionMode}
    grouped={grouped}
    disabled={disabled}
    tooltipPosition={tooltipPosition}
  >
    <Switch
      label={label}
      isLabelHidden
      value={checked}
      onChange={(v) => onChange(v)}
      isDisabled={disabled}
      isLoading={isUpdating}
      size="sm"
    />
  </SettingContainer>
);

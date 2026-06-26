import { useCallback, useState } from "react";
import {
  loadModeSettings,
  saveModeSettings,
  switchMode,
  type AppMode,
  type ModeSettings,
} from "../modeSettings";

export interface ModeSettingsState {
  modeSettings: ModeSettings;
  onboardingOpen: boolean;
  handleSwitchMode: (mode: AppMode) => void;
  handleOnboardingComplete: (next: ModeSettings) => void;
  handleOnboardingSkip: () => void;
}

export function useModeSettings(): ModeSettingsState {
  const [modeSettings, setModeSettings] = useState<ModeSettings>(() => loadModeSettings());
  const [onboardingOpen, setOnboardingOpen] = useState(() => !loadModeSettings().onboarded);

  const handleSwitchMode = useCallback((mode: AppMode) => {
    const next = switchMode(modeSettings, mode);
    setModeSettings(next);
    saveModeSettings(next);
  }, [modeSettings]);

  const handleOnboardingComplete = useCallback((next: ModeSettings) => {
    setModeSettings(next);
    saveModeSettings(next);
    setOnboardingOpen(false);
  }, []);

  const handleOnboardingSkip = useCallback(() => {
    const next: ModeSettings = { ...modeSettings, onboarded: true };
    setModeSettings(next);
    saveModeSettings(next);
    setOnboardingOpen(false);
  }, [modeSettings]);

  return {
    modeSettings,
    onboardingOpen,
    handleSwitchMode,
    handleOnboardingComplete,
    handleOnboardingSkip,
  };
}

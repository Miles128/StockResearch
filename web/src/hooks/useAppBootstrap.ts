import { useCallback, useEffect, useState } from "react";
import { api, type GlossaryTerm } from "../api";
import {
  loadModeSettings,
  modeSettingsFromApiPayload,
  modeSettingsToApiPayload,
  saveModeSettings,
  type ModeSettings,
} from "../modeSettings";
import { seedGlossaryCache } from "../TermPopover";

export interface AppBootstrapState {
  modeSettings: ModeSettings;
  onboardingOpen: boolean;
  glossary: Record<string, GlossaryTerm>;
  persistModeSettings: (next: ModeSettings) => void;
  handleOnboardingComplete: (next: ModeSettings) => void;
  handleOnboardingSkip: () => void;
}

export function useAppBootstrap(): AppBootstrapState {
  const [modeSettings, setModeSettings] = useState<ModeSettings>(() =>
    loadModeSettings(),
  );
  const [onboardingOpen, setOnboardingOpen] = useState(
    () => !loadModeSettings().onboarded,
  );
  const [glossary, setGlossary] = useState<Record<string, GlossaryTerm>>({});

  const persistModeSettings = useCallback((next: ModeSettings) => {
    setModeSettings(next);
    saveModeSettings(next);
    void api.saveModeSettings(modeSettingsToApiPayload(next)).catch(() => {});
    void api
      .glossary()
      .then((list) => {
        const map: Record<string, GlossaryTerm> = {};
        for (const item of list) map[item.id] = item;
        seedGlossaryCache(map);
        setGlossary(map);
      })
      .catch(() => {});
  }, []);

  const handleOnboardingComplete = useCallback(
    (next: ModeSettings) => {
      persistModeSettings(next);
      setOnboardingOpen(false);
    },
    [persistModeSettings],
  );

  const handleOnboardingSkip = useCallback(() => {
    persistModeSettings({ ...modeSettings, onboarded: true });
    setOnboardingOpen(false);
  }, [modeSettings, persistModeSettings]);

  useEffect(() => {
    const cachedModeSettings = loadModeSettings();
    void api
      .modeSettings()
      .then((remote) => {
        const remoteSettings = modeSettingsFromApiPayload(remote);
        if (!remoteSettings.onboarded && cachedModeSettings.onboarded) {
          persistModeSettings(cachedModeSettings);
          setOnboardingOpen(false);
          return;
        }
        setModeSettings(remoteSettings);
        saveModeSettings(remoteSettings);
        setOnboardingOpen(!remoteSettings.onboarded);
      })
      .catch(() => {
        setModeSettings(cachedModeSettings);
        setOnboardingOpen(!cachedModeSettings.onboarded);
      });
    void api
      .glossary()
      .then((list) => {
        const map: Record<string, GlossaryTerm> = {};
        for (const item of list) map[item.id] = item;
        seedGlossaryCache(map);
        setGlossary(map);
      })
      .catch(() => setGlossary({}));
  }, [persistModeSettings]);

  return {
    modeSettings,
    onboardingOpen,
    glossary,
    persistModeSettings,
    handleOnboardingComplete,
    handleOnboardingSkip,
  };
}

import { useEffect, useState } from "react";
import { api } from "../api";
import { isLlmConfiguredLocally, isServerLlmConfigured, type LlmSettingsMeta } from "../llmSettings";

export interface LlmInitState {
  llmConfigured: boolean;
  llmCheckDone: boolean;
  setupOpen: boolean;
  setSetupOpen: (open: boolean) => void;
  handleConfigured: () => void;
}

export function useLlmInit(): LlmInitState {
  const [llmConfigured, setLlmConfigured] = useState(false);
  const [llmCheckDone, setLlmCheckDone] = useState(false);
  const [setupOpen, setSetupOpen] = useState(false);

  useEffect(() => {
    void api
      .llmSettings()
      .then((meta: LlmSettingsMeta) => {
        const ok = isServerLlmConfigured(meta) || isLlmConfiguredLocally();
        setLlmConfigured(ok);
        setSetupOpen(!ok);
        setLlmCheckDone(true);
      })
      .catch(() => {
        const ok = isLlmConfiguredLocally();
        setLlmConfigured(ok);
        setSetupOpen(!ok);
        setLlmCheckDone(true);
      });
  }, []);

  function handleConfigured() {
    setLlmConfigured(true);
    setSetupOpen(false);
  }

  return {
    llmConfigured,
    llmCheckDone,
    setupOpen,
    setSetupOpen,
    handleConfigured,
  };
}

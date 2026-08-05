import { describe, expect, it } from "vitest";
import {
  modeSettingsFromApiPayload,
  modeSettingsToApiPayload,
  type ModeSettings,
} from "../modeSettings";

describe("modeSettings API conversion", () => {
  it("maps frontend camelCase settings to backend snake_case payload", () => {
    const settings: ModeSettings = {
      mode: "advisor",
      riskTolerance: "conservative",
      monthlyIncome: 18000,
      readingMode: "friendly",
      analysisDepth: "standard",
      enableDebate: false,
      enableGlossary: true,
      maxSignals: 5,
      onboarded: true,
      customGlossary: [{ id: "测试术语", short: "测试术语", def: "用于单测的自定义词条" }],
      holdingsView: "table",
      quoteRefreshMinutes: 10,
      briefingAutoEnabled: true,
      uiPollingEnabled: false,
    };

    expect(modeSettingsToApiPayload(settings)).toEqual({
      mode: "advisor",
      risk_tolerance: "conservative",
      monthly_income: 18000,
      reading_mode: "friendly",
      analysis_depth: "standard",
      enable_debate: false,
      enable_glossary: true,
      max_signals: 5,
      onboarded: true,
      custom_glossary: [
        {
          id: "测试术语",
          short: "测试术语",
          def: "用于单测的自定义词条",
          analogy: "",
          en: "",
        },
      ],
      quote_refresh_minutes: 10,
      briefing_auto_enabled: true,
      ui_polling_enabled: false,
    });
  });

  it("maps backend snake_case payload to frontend camelCase settings", () => {
    expect(
      modeSettingsFromApiPayload({
        mode: "research",
        risk_tolerance: "aggressive",
        monthly_income: null,
        reading_mode: "professional",
        analysis_depth: "deep",
        enable_debate: true,
        enable_glossary: false,
        max_signals: 20,
        onboarded: true,
        custom_glossary: [],
        quote_refresh_minutes: 20,
        briefing_auto_enabled: false,
        ui_polling_enabled: true,
      }),
    ).toEqual({
      mode: "research",
      riskTolerance: "aggressive",
      monthlyIncome: undefined,
      readingMode: "professional",
      analysisDepth: "deep",
      enableDebate: true,
      enableGlossary: false,
      maxSignals: 20,
      onboarded: true,
      customGlossary: [],
      holdingsView: "table",
      quoteRefreshMinutes: 20,
      briefingAutoEnabled: false,
      uiPollingEnabled: true,
    });
  });
});

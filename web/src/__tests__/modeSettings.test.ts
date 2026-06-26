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
      enableDebate: false,
      enableGlossary: true,
      maxSignals: 5,
      onboarded: true,
    };

    expect(modeSettingsToApiPayload(settings)).toEqual({
      mode: "advisor",
      risk_tolerance: "conservative",
      monthly_income: 18000,
      reading_mode: "friendly",
      enable_debate: false,
      enable_glossary: true,
      max_signals: 5,
      onboarded: true,
    });
  });

  it("maps backend snake_case payload to frontend camelCase settings", () => {
    expect(
      modeSettingsFromApiPayload({
        mode: "research",
        risk_tolerance: "aggressive",
        monthly_income: null,
        reading_mode: "professional",
        enable_debate: true,
        enable_glossary: false,
        max_signals: 20,
        onboarded: true,
      }),
    ).toEqual({
      mode: "research",
      riskTolerance: "aggressive",
      monthlyIncome: undefined,
      readingMode: "professional",
      enableDebate: true,
      enableGlossary: false,
      maxSignals: 20,
      onboarded: true,
    });
  });
});

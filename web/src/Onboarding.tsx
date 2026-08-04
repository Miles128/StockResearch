/**
 * 首次引导：选模式 →（投顾专属）10 题风险问卷 → 完成
 * PRD §4.5
 *
 * 问卷设计：10 题，每题 3 个选项（保守 1 分 / 稳健 2 分 / 进取 3 分）
 * 总分 10-16 → 保守，17-23 → 稳健，24-30 → 进取
 * 月收入单独一题（可选）
 */

import { useState } from "react";
import { useI18n } from "./i18n";
import type { AppMode, ModeSettings, RiskTolerance } from "./modeSettings";
import { ADVISOR_PRESET, RESEARCH_PRESET } from "./modeSettings";

interface OnboardingProps {
  /** 完成引导，传入最终设置 */
  onComplete: (settings: ModeSettings) => void;
  /** 跳过引导，用默认值 */
  onSkip: () => void;
}

type Step = "pickMode" | "questionnaire" | "done";

/** 问卷题目定义（i18n key + 选项分值） */
interface QuestionDef {
  /** i18n key，如 onboarding.q1.title */
  key: string;
  options: {
    id: "a" | "b" | "c";
    labelKey: "optA" | "optB" | "optC";
    score: number;
  }[];
}

const QUESTIONS: QuestionDef[] = [
  { key: "q1", options: buildOptions() },
  { key: "q2", options: buildOptions() },
  { key: "q3", options: buildOptions() },
  { key: "q4", options: buildOptions() },
  { key: "q5", options: buildOptions() },
  { key: "q6", options: buildOptions() },
  { key: "q7", options: buildOptions() },
  { key: "q8", options: buildOptions() },
  { key: "q9", options: buildOptions() },
  { key: "q10", options: buildOptions() },
];

function buildOptions(): QuestionDef["options"] {
  return [
    { id: "a", labelKey: "optA", score: 1 },
    { id: "b", labelKey: "optB", score: 2 },
    { id: "c", labelKey: "optC", score: 3 },
  ];
}

/** 总分映射风险等级 */
function scoreToTolerance(total: number): RiskTolerance {
  if (total <= 16) return "conservative";
  if (total <= 23) return "moderate";
  return "aggressive";
}

export function Onboarding({ onComplete, onSkip }: OnboardingProps) {
  const { t } = useI18n();
  const [step, setStep] = useState<Step>("pickMode");
  const [pickedMode, setPickedMode] = useState<AppMode>("advisor");
  const [answers, setAnswers] = useState<Record<number, string>>({});
  const [monthlyIncome, setMonthlyIncome] = useState<string>("");
  const [currentQ, setCurrentQ] = useState(0);

  function pickMode(mode: AppMode) {
    setPickedMode(mode);
    if (mode === "advisor") {
      setStep("questionnaire");
      setCurrentQ(0);
    } else {
      finish(mode, "moderate", undefined);
    }
  }

  function finish(mode: AppMode, tolerance: RiskTolerance, income: number | undefined) {
    const preset = mode === "advisor" ? ADVISOR_PRESET : RESEARCH_PRESET;
    onComplete({
      ...preset,
      mode,
      riskTolerance: tolerance,
      monthlyIncome: income,
      onboarded: true,
    });
  }

  function selectAnswer(qIndex: number, optionId: string) {
    setAnswers((prev) => ({ ...prev, [qIndex]: optionId }));
  }

  function computeScore(): number {
    let total = 0;
    QUESTIONS.forEach((q, i) => {
      const ans = answers[i];
      if (ans) {
        const opt = q.options.find((o) => o.id === ans);
        if (opt) total += opt.score;
      }
    });
    return total;
  }

  function handleQuestionnaireNext() {
    const total = computeScore();
    const tolerance = scoreToTolerance(total);
    const income = monthlyIncome.trim() === "" ? undefined : Number(monthlyIncome);
    finish(pickedMode, tolerance, income && income > 0 ? income : undefined);
  }

  function handleQuestionnaireSkip() {
    finish(pickedMode, "moderate", undefined);
  }

  const currentQuestion = QUESTIONS[currentQ];
  const currentAnswer = answers[currentQ];

  if (step === "pickMode") {
    return (
      <div className="onboarding-overlay">
        <div className="onboarding-modal">
          <h2 className="onboarding-title">{t("onboarding.welcome")}</h2>
          <p className="onboarding-subtitle">{t("onboarding.pickMode")}</p>

          <div className="onboarding-cards">
            <button type="button" className="onboarding-card" onClick={() => pickMode("advisor")}>
              <div className="onboarding-card-title">{t("onboarding.advisorCard.title")}</div>
              <ul className="onboarding-card-list">
                <li>{t("onboarding.advisorCard.desc1")}</li>
                <li>{t("onboarding.advisorCard.desc2")}</li>
                <li>{t("onboarding.advisorCard.desc3")}</li>
                <li className="onboarding-card-tag">{t("onboarding.advisorCard.desc4")}</li>
              </ul>
            </button>

            <button type="button" className="onboarding-card" onClick={() => pickMode("research")}>
              <div className="onboarding-card-title">{t("onboarding.researchCard.title")}</div>
              <ul className="onboarding-card-list">
                <li>{t("onboarding.researchCard.desc1")}</li>
                <li>{t("onboarding.researchCard.desc2")}</li>
                <li>{t("onboarding.researchCard.desc3")}</li>
                <li className="onboarding-card-tag">{t("onboarding.researchCard.desc4")}</li>
              </ul>
            </button>
          </div>

          <p className="onboarding-hint">{t("onboarding.pickModeHint")}</p>
          <button type="button" className="onboarding-skip-btn" onClick={onSkip}>
            {t("onboarding.skip")}
          </button>
        </div>
      </div>
    );
  }

  if (step === "questionnaire") {
    const isIncomeStep = currentQ === QUESTIONS.length;
    const progress = Math.round((currentQ / (QUESTIONS.length + 1)) * 100);

    return (
      <div className="onboarding-overlay">
        <div className="onboarding-modal onboarding-modal-wide">
          <div className="onboarding-progress-bar">
            <div className="onboarding-progress-fill" style={{ width: `${progress}%` }} />
          </div>
          <h2 className="onboarding-title">
            {t("onboarding.questionnaire.title")} ({currentQ + 1}/{QUESTIONS.length + 1})
          </h2>
          <p className="onboarding-subtitle">{t("onboarding.questionnaire.hint")}</p>

          {!isIncomeStep ? (
            <div className="onboarding-question">
              <div className="onboarding-question-text">
                {t(`onboarding.${currentQuestion.key}.title`)}
              </div>
              <div className="onboarding-question-options">
                {currentQuestion.options.map((opt) => (
                  <label
                    key={opt.id}
                    className={`onboarding-question-option${
                      currentAnswer === opt.id ? " active" : ""
                    }`}
                  >
                    <input
                      type="radio"
                      name={`q-${currentQ}`}
                      value={opt.id}
                      checked={currentAnswer === opt.id}
                      onChange={() => selectAnswer(currentQ, opt.id)}
                    />
                    <span className="onboarding-question-option-text">
                      {t(`onboarding.${currentQuestion.key}.${opt.labelKey}`)}
                    </span>
                  </label>
                ))}
              </div>
            </div>
          ) : (
            <div className="onboarding-income">
              <label className="onboarding-income-label" htmlFor="monthly-income">
                {t("onboarding.questionnaire.monthlyIncome")}
              </label>
              <p className="onboarding-income-hint">
                {t("onboarding.questionnaire.monthlyIncomeHint")}
              </p>
              <input
                id="monthly-income"
                type="number"
                inputMode="numeric"
                min={0}
                placeholder={t("onboarding.questionnaire.monthlyIncomePlaceholder")}
                value={monthlyIncome}
                onChange={(e) => setMonthlyIncome(e.target.value)}
                className="onboarding-income-input"
              />
            </div>
          )}

          <div className="onboarding-actions">
            <button type="button" className="onboarding-skip-btn" onClick={handleQuestionnaireSkip}>
              {t("onboarding.questionnaire.skip")}
            </button>
            <div className="onboarding-nav">
              {currentQ > 0 && (
                <button
                  type="button"
                  className="onboarding-prev-btn"
                  onClick={() => setCurrentQ((q) => q - 1)}
                >
                  {t("onboarding.questionnaire.prev")}
                </button>
              )}
              {!isIncomeStep ? (
                <button
                  type="button"
                  className="onboarding-next-btn"
                  onClick={() => setCurrentQ((q) => q + 1)}
                  disabled={!currentAnswer}
                >
                  {t("onboarding.questionnaire.next")}
                </button>
              ) : (
                <button
                  type="button"
                  className="onboarding-next-btn"
                  onClick={handleQuestionnaireNext}
                >
                  {t("onboarding.questionnaire.finish")}
                </button>
              )}
            </div>
          </div>
        </div>
      </div>
    );
  }

  return null;
}

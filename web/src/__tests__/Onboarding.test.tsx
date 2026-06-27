import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { Onboarding } from "../Onboarding";
import { I18nProvider } from "../i18n";

describe("Onboarding", () => {
  it("renders risk questionnaire answer labels", () => {
    render(
      <I18nProvider>
        <Onboarding onComplete={vi.fn()} onSkip={vi.fn()} />
      </I18nProvider>,
    );

    fireEvent.click(screen.getByRole("button", { name: /个人/i }));

    expect(screen.getByText("不到 1 年，刚开始")).toBeTruthy();
    expect(screen.getByText("1-5 年，有一定经验")).toBeTruthy();
    expect(screen.getByText("5 年以上，经验丰富")).toBeTruthy();
  });
});

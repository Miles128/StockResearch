import { describe, expect, it } from "vitest";
import { getBriefingKind } from "../briefingKind";

describe("getBriefingKind", () => {
  it("returns premarket before 09:30", () => {
    expect(getBriefingKind(new Date("2026-07-07T08:30:00"))).toBe("premarket");
    expect(getBriefingKind(new Date("2026-07-07T09:00:00"))).toBe("premarket");
    expect(getBriefingKind(new Date("2026-07-07T09:29:00"))).toBe("premarket");
  });

  it("returns intraday between 09:30 and 15:00", () => {
    expect(getBriefingKind(new Date("2026-07-07T09:30:00"))).toBe("intraday");
    expect(getBriefingKind(new Date("2026-07-07T11:35:00"))).toBe("intraday");
    expect(getBriefingKind(new Date("2026-07-07T14:59:00"))).toBe("intraday");
  });

  it("returns postmarket from 15:00 onwards", () => {
    expect(getBriefingKind(new Date("2026-07-07T15:00:00"))).toBe("postmarket");
    expect(getBriefingKind(new Date("2026-07-07T18:00:00"))).toBe("postmarket");
  });
});

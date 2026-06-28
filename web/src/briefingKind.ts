export type BriefingKind = "intraday" | "postmarket";

/** 根据 A 股交易时段返回应生成的简报类型：09:30–15:00 盘中，其余盘后 */
export function getBriefingKind(now: Date = new Date()): BriefingKind {
  const minutes = now.getHours() * 60 + now.getMinutes();
  if (minutes >= 570 && minutes < 900) return "intraday";
  return "postmarket";
}

export type BriefingKind = "premarket" | "intraday" | "postmarket";

/** 根据 A 股交易时段返回应生成的简报类型
 * 09:30 之前：盘前简报
 * 09:30–15:00：盘中简报
 * 15:00 之后：盘后简报
 */
export function getBriefingKind(now: Date = new Date()): BriefingKind {
  const minutes = now.getHours() * 60 + now.getMinutes();
  if (minutes < 570) return "premarket"; // < 09:30
  if (minutes < 900) return "intraday"; // 09:30–15:00
  return "postmarket";
}

/** Exact copy from Lazyweb "Line Numbers" mockup — StockResearch Copilot empty outline. */
export interface FourDimOutlineSection {
  id: string;
  title: string;
  lines: string[];
}

export const FOUR_DIM_LINE_OUTLINE: FourDimOutlineSection[] = [
  {
    id: "fundamental",
    title: "基本面",
    lines: [
      "公司财务状况如何？最新财报有哪些要点？",
      "行业排名和竞争格局怎样？",
      "估值水平是否合理？",
    ],
  },
  {
    id: "technical",
    title: "技术面",
    lines: [
      "当前股价趋势如何？",
      "关键支撑位和压力位在哪里？",
      "成交量有什么变化？",
    ],
  },
  {
    id: "sentiment",
    title: "情绪面",
    lines: [
      "市场情绪是乐观还是悲观？",
      "有哪些热门消息或舆情？",
      "投资者情绪指标如何？",
    ],
  },
  {
    id: "chips",
    title: "筹码面",
    lines: [
      "主力资金流向如何？",
      "筹码集中度高还是分散？",
      "大股东或机构有增减持吗？",
    ],
  },
];

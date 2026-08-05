export interface AboutReference {
  name: string;
  url: string;
  note?: string;
}

export const ABOUT_INFO = {
  product: "StockResearch",
  tagline: "AI 投研终端 · A 股 Multi-Agent",
  author: "Sihai",
  repoUrl: "https://github.com/Miles128/StockResearch",
  email: "myx28@qq.com",
  xiaohongshuId: "11009080268",
  xiaohongshuUrl: "https://www.xiaohongshu.com/user/profile/11009080268",
  references: [
    {
      name: "TradingAgents",
      url: "https://github.com/TauricResearch/TradingAgents",
      note: "多 Agent 辩论与分工协作",
    },
    {
      name: "TradingAgents-CN",
      url: "https://github.com/hsliuping/TradingAgents-CN",
      note: "A 股与国产大模型适配",
    },
    {
      name: "FinGenius",
      url: "https://github.com/HuaYaoAI/FinGenius",
      note: "研究-决策双阶段",
    },
    {
      name: "Vibe-Trading",
      url: "https://github.com/HKUDS/Vibe-Trading",
      note: "多源数据与 MCP 工具生态",
    },
    {
      name: "FinRobot",
      url: "https://github.com/AI4Finance-Foundation/FinRobot",
      note: "自动研报与分层架构",
    },
  ] as AboutReference[],
};

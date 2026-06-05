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
      note: "多空辩论式投研",
    },
    {
      name: "TradingAgents-CN",
      url: "https://github.com/hsliuping/TradingAgents-CN",
      note: "A 股 / 国产模型适配",
    },
    {
      name: "FinGenius",
      url: "https://github.com/PbRQianJiang/FinGenius",
      note: "Research-Battle 双阶段",
    },
    {
      name: "LangGraph",
      url: "https://github.com/langchain-ai/langgraph",
      note: "Agent 编排",
    },
  ] as AboutReference[],
};

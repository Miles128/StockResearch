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
      note: "多 Agent 辩论与 LangGraph 编排",
    },
    {
      name: "TradingAgents-CN",
      url: "https://github.com/hsliuping/TradingAgents-CN",
      note: "A 股与国产大模型适配",
    },
    {
      name: "FinGenius",
      url: "https://github.com/PbRQianJiang/FinGenius",
      note: "Research-Battle 双阶段",
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
    {
      name: "LangGraph",
      url: "https://github.com/langchain-ai/langgraph",
      note: "Agent 工作流编排",
    },
  ] as AboutReference[],
};

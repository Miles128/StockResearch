"""Financial ratio analysis agent — PE/PB/ROE/margins/trends for A-share stocks."""

import logging
from typing import Any

from stockresearch.data.providers.market import QuoteProvider
from stockresearch.utils.llm import LLMClient

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """你是财报比率分析 Agent。根据提供的财务数据，分析以下关键比率及其趋势：

1. 估值比率：市盈率(PE)、市净率(PB)
2. 盈利能力：ROE(净资产收益率)、ROE-摊薄、毛利率、净利率
3. 成长能力：营收增长率、净利润增长率
4. 偿债能力：资产负债率、流动比率、速动比率、产权比率
5. 运营效率：存货周转率、应收账款周转天数

数据来源：同花顺年度财报摘要。趋势列显示近3年数据变化。
请以表格形式输出，包含：指标名 | 当前值 | 趋势 | 行业参考 | 评价
最后给出综合评价和趋势判断。不要建议买卖。"""


class FinancialRatioAgent:
    """Fetch financial data and compute key ratios for a stock."""

    def __init__(self, llm: LLMClient | None = None) -> None:
        self._llm = llm

    async def run(self, symbol: str, name: str = "") -> dict[str, Any]:
        """Run financial ratio analysis.

        Returns a dict with:
          - symbol, name
          - ratios: list of {name, value, reference, assessment}
          - summary: text summary
          - raw_data: dict of raw financial figures
        """
        raw_data = await self._fetch_financial_data(symbol)

        # Compute ratios from raw data
        ratios = self._compute_ratios(raw_data, symbol, name)

        # If LLM available, get qualitative analysis
        summary = ""
        if self._llm:
            try:
                data_text = "\n".join(
                    f"{r['name']}: {r['value']}"
                    + (f" (趋势: {r['trend']})" if r.get('trend') else "")
                    + f" (参考: {r['reference']}, 评价: {r['assessment']})"
                    for r in ratios
                )
                summary = await self._llm.complete(
                    _SYSTEM_PROMPT,
                    f"股票：{name}({symbol})\n\n财务数据：\n{data_text}\n\n请分析以上比率。",
                )
            except Exception as exc:
                logger.warning("LLM analysis failed: %s", exc)
                summary = "AI 分析暂时不可用。"

        return {
            "symbol": symbol,
            "name": name,
            "ratios": ratios,
            "summary": summary,
            "raw_data": raw_data,
        }

    async def _fetch_financial_data(self, symbol: str) -> dict[str, Any]:
        """Fetch financial data from AkShare (stock_financial_abstract_ths)."""
        data: dict[str, Any] = {
            "symbol": symbol,
            "pe": None,
            "pb": None,
            "roe": None,
            "roe_diluted": None,
            "gross_margin": None,
            "net_margin": None,
            "revenue_growth": None,
            "profit_growth": None,
            "debt_ratio": None,
            "current_ratio": None,
            "quick_ratio": None,
            "price": None,
            "eps": None,
            "bvps": None,
            "inventory_turnover": None,
            "ar_turnover_days": None,
            "equity_ratio": None,
            "trends": {},
        }

        # Get current price for PE/PB calculation
        try:
            provider = QuoteProvider()
            quote = await provider.get_quote(symbol)
            data["price"] = quote.price
        except Exception:
            pass

        # Use stock_financial_abstract_ths (the only working API)
        try:
            import akshare as ak

            df = ak.stock_financial_abstract_ths(
                symbol=symbol, indicator="按年度"
            )
            if df is None or df.empty:
                logger.warning("No financial data returned for %s", symbol)
                return data

            # Latest year data
            latest = df.iloc[-1]
            # Previous year for trend
            prev = df.iloc[-2] if len(df) > 1 else None
            # 3 years ago for trend
            year3 = df.iloc[-3] if len(df) > 2 else None

            # Column mapping: AkShare column -> data key
            col_map = {
                "基本每股收益": "eps",
                "每股净资产": "bvps",
                "销售净利率": "net_margin",
                "销售毛利率": "gross_margin",
                "净资产收益率": "roe",
                "净资产收益率-摊薄": "roe_diluted",
                "资产负债率": "debt_ratio",
                "流动比率": "current_ratio",
                "速动比率": "quick_ratio",
                "营业总收入同比增长率": "revenue_growth",
                "净利润同比增长率": "profit_growth",
                "产权比率": "equity_ratio",
                "存货周转率": "inventory_turnover",
                "应收账款周转天数": "ar_turnover_days",
            }

            def _parse_pct(val: Any) -> float | None:
                """Parse percentage string like '52.49%' to float 52.49."""
                if val is None:
                    return None
                s = str(val).strip().replace(",", "")
                if s in ("False", "True", "", "-", "nan"):
                    return None
                if s.endswith("%"):
                    s = s[:-1]
                try:
                    return float(s)
                except (ValueError, TypeError):
                    return None

            def _parse_num(val: Any) -> float | None:
                """Parse number string, handling '亿' suffix."""
                if val is None:
                    return None
                s = str(val).strip().replace(",", "")
                if s in ("False", "True", "", "-", "nan"):
                    return None
                multiplier = 1.0
                if s.endswith("亿"):
                    s = s[:-1]
                    multiplier = 1e8
                elif s.endswith("万"):
                    s = s[:-1]
                    multiplier = 1e4
                try:
                    return float(s) * multiplier
                except (ValueError, TypeError):
                    return None

            for col, key in col_map.items():
                if col in latest.index or col in latest:
                    val = latest.get(col)
                    parsed = _parse_pct(val) if "率" in col or "增长" in col else _parse_num(val)
                    if parsed is not None:
                        data[key] = parsed

            # Calculate PE = price / eps
            if data["price"] and data["eps"] and data["eps"] > 0:
                data["pe"] = round(data["price"] / data["eps"], 2)

            # Calculate PB = price / bvps
            if data["price"] and data["bvps"] and data["bvps"] > 0:
                data["pb"] = round(data["price"] / data["bvps"], 2)

            # Build trend data (last 3 years)
            trend_keys = [
                "roe", "gross_margin", "net_margin",
                "revenue_growth", "profit_growth", "debt_ratio",
            ]
            for period_idx, period_df in enumerate([year3, prev, latest]):
                if period_df is None:
                    continue
                year = str(period_df.get("报告期", f"Y-{period_idx}"))
                for col, key in col_map.items():
                    if key in trend_keys:
                        val = period_df.get(col)
                        is_pct = "率" in col or "增长" in col
                        parsed = (
                            _parse_pct(val) if is_pct
                            else _parse_num(val)
                        )
                        if parsed is not None:
                            data["trends"].setdefault(key, {})[year] = parsed

        except ImportError:
            logger.warning("akshare not available")
        except Exception as exc:
            logger.warning("Financial data fetch failed for %s: %s", symbol, exc)

        return data

    def _compute_ratios(
        self, raw: dict[str, Any], symbol: str, name: str
    ) -> list[dict[str, str]]:
        """Compute and format financial ratios with industry references."""
        refs: dict[str, tuple[str, str]] = {
            "pe": ("市盈率 PE", "15-25"),
            "pb": ("市净率 PB", "1.5-3.0"),
            "roe": ("净资产收益率 ROE(%)", "10-15"),
            "roe_diluted": ("净资产收益率-摊薄(%)", "10-15"),
            "gross_margin": ("销售毛利率(%)", "25-40"),
            "net_margin": ("销售净利率(%)", "8-15"),
            "revenue_growth": ("营收增长率(%)", "10-20"),
            "profit_growth": ("净利润增长率(%)", "10-20"),
            "debt_ratio": ("资产负债率(%)", "40-60"),
            "current_ratio": ("流动比率", "1.5-2.0"),
            "quick_ratio": ("速动比率", "1.0-1.5"),
            "equity_ratio": ("产权比率", "0.5-1.5"),
            "inventory_turnover": ("存货周转率", "-"),
            "ar_turnover_days": ("应收账款周转天数", "-"),
            "eps": ("每股收益 EPS", "-"),
            "bvps": ("每股净资产", "-"),
        }

        ratios: list[dict[str, str]] = []
        for key, (label, ref) in refs.items():
            val = raw.get(key)
            if val is not None:
                val_str = f"{val:.2f}" if isinstance(val, float) else str(val)
                assessment = self._assess(key, val)
                # Add trend info
                trend_str = ""
                trends = raw.get("trends", {}).get(key, {})
                if trends and len(trends) > 1:
                    years = sorted(trends.keys())
                    vals = [f"{trends[y]:.1f}" for y in years]
                    trend_str = " → ".join(vals)
                ratios.append({
                    "name": label,
                    "value": val_str,
                    "reference": ref,
                    "assessment": assessment,
                    "trend": trend_str,
                })

        if len(ratios) < 3:
            ratios.append({
                "name": "数据状态",
                "value": "部分数据不可用",
                "reference": "-",
                "assessment": "数据有限",
                "trend": "",
            })

        return ratios

    def _assess(self, key: str, value: float) -> str:
        """Simple assessment of a financial ratio."""
        assessments: dict[str, Any] = {
            "pe": lambda v: (
                "偏低" if v < 15 else "合理" if v < 25
                else "偏高" if v < 40 else "过高"
            ),
            "pb": lambda v: "破净" if v < 1 else "合理" if v < 3 else "偏高",
            "roe": lambda v: (
                "优秀" if v > 15 else "良好" if v > 10
                else "一般" if v > 5 else "较差"
            ),
            "roe_diluted": lambda v: (
                "优秀" if v > 15 else "良好" if v > 10
                else "一般" if v > 5 else "较差"
            ),
            "gross_margin": lambda v: (
                "优秀" if v > 40 else "良好" if v > 25
                else "一般" if v > 15 else "较低"
            ),
            "net_margin": lambda v: (
                "优秀" if v > 15 else "良好" if v > 8
                else "一般" if v > 3 else "较低"
            ),
            "debt_ratio": lambda v: (
                "保守" if v < 30 else "合理" if v < 60
                else "偏高" if v < 80 else "高风险"
            ),
            "current_ratio": lambda v: (
                "偏强" if v > 2 else "合理" if v > 1.5
                else "偏弱" if v > 1 else "风险"
            ),
            "quick_ratio": lambda v: (
                "偏强" if v > 1.5 else "合理" if v > 1
                else "偏弱" if v > 0.5 else "风险"
            ),
            "revenue_growth": lambda v: (
                "高增" if v > 30 else "稳健" if v > 10
                else "放缓" if v > 0 else "下滑"
            ),
            "profit_growth": lambda v: (
                "高增" if v > 30 else "稳健" if v > 10
                else "放缓" if v > 0 else "下滑"
            ),
            "equity_ratio": lambda v: (
                "低杠杆" if v < 0.5 else "合理" if v < 1.5
                else "偏高" if v < 3 else "高杠杆"
            ),
        }
        fn = assessments.get(key)
        if fn:
            try:
                return fn(value)
            except (ValueError, TypeError):
                pass
        return "-"

# scripts/kimi_live_check.py
"""手动验证 Kimi Datasource 真实调用(消耗 Kimi Code 会员配额,慎用)。

用法: uv run python scripts/kimi_live_check.py
前置: 本机已安装 kimi CLI 并 /login,且 .env 中 KIMI_CLI_ENABLED=true
"""

import asyncio

from stockresearch.data.providers.kimi_macro import KimiMacroProvider
from stockresearch.data.providers.kimi_wind import KimiWindProvider


async def main() -> None:
    macro = await KimiMacroProvider().get_macro_snapshot(refresh=True)
    print("宏观指标数:", len(macro.get("indicators") or []))
    wind = await KimiWindProvider().get_daily_digest(refresh=True)
    print("公告数:", len(wind.get("announcements") or []))
    assert macro or wind, "两个数据源都为空,检查 kimi CLI 登录状态"


if __name__ == "__main__":
    asyncio.run(main())

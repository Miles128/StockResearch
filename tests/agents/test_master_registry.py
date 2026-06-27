from stockresearch.agents.master_commentary.registry import (
    get_master_config,
    resolve_master_ids,
)
from stockresearch.core.schemas import CustomMasterOut, ModeSettingsOut
from stockresearch.prompts import load_master_prompt


def test_load_builtin_master_prompts() -> None:
    for mid in ("buffett", "munger", "burry"):
        text = load_master_prompt(mid)
        assert "输出要求" in text or "框架" in text


def test_resolve_master_ids_respects_selection() -> None:
    settings = ModeSettingsOut(selected_masters=["buffett", "burry"])
    assert resolve_master_ids(settings) == ["buffett", "burry"]


def test_custom_master_config() -> None:
    settings = ModeSettingsOut(
        custom_masters=[
            CustomMasterOut(
                id="dalio",
                name="Ray Dalio",
                system_prompt="你是桥水风格宏观思维蒸馏体，关注债务周期与风险平价。",
            )
        ],
        selected_masters=["dalio"],
    )
    cfg = get_master_config("dalio", settings)
    assert cfg["name"] == "Ray Dalio"
    assert "JSON" in cfg["system"]

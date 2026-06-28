"""Glossary routes — expose term dictionary for frontend click-to-show popovers.

投顾模式下前端通过此接口获取词库，渲染 <term> 标签的可点击弹窗。
投研模式后端不标记术语，前端也不会请求本接口的数据。
"""

from fastapi import APIRouter

from stockresearch.services.glossary import get_glossary

router = APIRouter(prefix="/glossary", tags=["glossary"])


@router.get("")
def list_glossary() -> list[dict[str, str]]:
    """返回全部词库条目，供前端 TermPopover 查询。"""
    terms = get_glossary()
    return [
        {
            "id": t.id,
            "en": t.en,
            "short": t.short,
            "def": t.def_,
            "analogy": t.analogy,
        }
        for t in terms.values()
    ]

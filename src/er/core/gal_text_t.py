from typing import Protocol, TypeVar, runtime_checkable


@runtime_checkable
class GalTextCompatible(Protocol):
    """定义宿主类必须具备的结构"""

    # 角色名映射表：{原始姓名: 翻译后姓名}
    names: dict[str, str]
    # 文本条目列表：存储对话、旁白等详细信息
    items: list[dict[str, object]]
    # 检查时候存放的错误信息列表
    errors: list[str]


GalTextT = TypeVar("GalTextT", bound=GalTextCompatible)


DEFAULT_ITEM_TEXT_FIELDS: tuple[str, ...] = ("message", "name")

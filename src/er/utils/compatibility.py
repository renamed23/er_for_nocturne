from er.utils.fs import PathLike, to_path
from er.utils.misc import ensure_str, read_json


def load_uif_json_substitution(path: PathLike) -> dict[str, str]:
    """
    从 UIF 兼容配置 JSON 中加载单字符替换表。

    目标 JSON 格式如下::

        {
          "character_substitution": {
            "source_characters": "懐這樣擁緊邊親説",
            "target_characters": "怀这样拥紧边亲说"
          }
        }

    其中 source_characters 与 target_characters 必须一一对应，且字符数量必须相等。

    Args:
        path: UIF 兼容配置 JSON 文件路径。

    Returns:
        单字符替换映射表，格式为 ``{源字符: 目标字符}``。
    """
    data = read_json(to_path(path))

    if not isinstance(data, dict):
        raise TypeError("UIF 兼容配置 JSON 顶层必须是对象(dict)。")

    substitution = data.get("character_substitution")
    if not isinstance(substitution, dict):
        raise ValueError("UIF 兼容配置缺少 character_substitution 对象。")

    source_characters = ensure_str(
        substitution.get("source_characters"),
        "character_substitution.source_characters",
    )
    target_characters = ensure_str(
        substitution.get("target_characters"),
        "character_substitution.target_characters",
    )

    if len(source_characters) != len(target_characters):
        raise ValueError(
            "UIF 字符替换表长度不一致："
            f"source_characters={len(source_characters)}，"
            f"target_characters={len(target_characters)}"
        )

    return dict(zip(source_characters, target_characters, strict=True))

import re

from er.core.gal_text_t import GalTextT


# 构建静态转换表：0x0020 (空格) -> 0x3000, 0x0021-0x007E -> 0xFF01-0xFF5E
_ASCII_TO_FULL_MAP = {i: i + 65248 for i in range(33, 127)}

_ASCII_TO_FULL_MAP[32] = 12288  # 空格

_TRANSLATE_TABLE = str.maketrans({
    chr(k): chr(v) for k, v in _ASCII_TO_FULL_MAP.items()
})


def str_to_fullwidth(text: str, ignore_pattern: str | None = None) -> str:
    """
    全角转换。
    """
    if not text:
        return text

    if not ignore_pattern:
        return text.translate(_TRANSLATE_TABLE)

    # 如果有忽略模式，使用 re.split 保留分隔符进行处理
    pattern = re.compile(ignore_pattern)
    tokens = pattern.split(text)
    return "".join(
        t if pattern.fullmatch(t) else t.translate(_TRANSLATE_TABLE) for t in tokens
    )


class FullWidthMixin:
    """
    GalText 全角化混入类。
    """

    def apply_fullwidth(self: GalTextT, ignore_pattern: str | None = None) -> GalTextT:
        """
        对 items 和 names 进行全量全角化。
        """

        for k in self.names:
            self.names[k] = str_to_fullwidth(self.names[k], ignore_pattern)

        for item in self.items:
            name = item.get("name")
            if isinstance(name, str):
                item["name"] = str_to_fullwidth(name, ignore_pattern)
            message = item.get("message")
            if isinstance(message, str):
                item["message"] = str_to_fullwidth(message, ignore_pattern)

        return self

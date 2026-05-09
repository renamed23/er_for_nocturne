from collections.abc import Iterable, Iterator

from er.core.gal_text_t import GalTextT


DEFAULT_WRAP_SYMBOL = "\r\n"

DEFAULT_WRAP_SYMBOLS_TO_REMOVE = ("\r\n", "\n")

DEFAULT_SYMBOLS_TO_IGNORE_WRAP = ()

DEFAULT_ZERO_WIDTH_SYMBOLS = ()


def _char_width(char: str, zero_width_symbols: Iterable[str]) -> int:
    """
    获取单个字符的显示宽度。

    - zero_width_symbols 中字符宽度视为 0
    - ASCII 字符宽度为 1
    - 其他字符宽度为 2
    """
    if char in zero_width_symbols:
        return 0
    if ord(char) <= 127:
        return 1
    return 2


def _line_width(text: str, zero_width_symbols: Iterable[str]) -> int:
    """计算字符串总显示宽度。"""
    return sum(_char_width(ch, zero_width_symbols) for ch in text)


def str_remove_wrap(
    text: str,
    wrap_symbols_to_remove: tuple[str, ...] = DEFAULT_WRAP_SYMBOLS_TO_REMOVE,
) -> str:
    """
    移除文本中的换行符号。
    """
    if not text:
        return text

    for symbol in wrap_symbols_to_remove:
        text = text.replace(symbol, "")
    return text


def str_auto_wrap(
    text: str,
    max_width: int,
    wrap_symbol: str = DEFAULT_WRAP_SYMBOL,
    wrap_symbols_to_remove: tuple[str, ...] = DEFAULT_WRAP_SYMBOLS_TO_REMOVE,
    zero_width_symbols: tuple[str, ...] = DEFAULT_ZERO_WIDTH_SYMBOLS,
) -> str:
    """
    根据显示宽度自动换行。

    先移除已有换行，再按 max_width 重新分行。
    """
    text = str_remove_wrap(text, wrap_symbols_to_remove)
    if not text:
        return text

    lines: list[str] = []
    current_line = ""

    for char in text:
        char_width = _char_width(char, zero_width_symbols)
        current_width = _line_width(current_line, zero_width_symbols)

        if current_width + char_width > max_width:
            if current_line:
                lines.append(current_line)
                current_line = char
            else:
                lines.append(char)
                current_line = ""
        else:
            current_line += char

    if current_line:
        lines.append(current_line)

    return wrap_symbol.join(lines)


def _iter_wrappable_items(
    items: list[dict[str, object]],
    symbols_to_ignore_wrap: tuple[str, ...],
) -> Iterator[tuple[dict[str, object], str]]:
    """迭代可处理换行的条目。"""
    for item in items:
        message = item.get("message")
        if not isinstance(message, str):
            continue

        if item.get("should_wrap") is not True:
            continue

        if any(symbol in message for symbol in symbols_to_ignore_wrap):
            continue

        yield item, message


class AutoWrapMixin:
    """
    GalText 自动换行/移除换行混入类。

    仅处理 items 中 message 字段，不处理 names。
    """

    def apply_auto_wrap(
        self: GalTextT,
        max_width: int,
        wrap_symbol: str = DEFAULT_WRAP_SYMBOL,
        wrap_symbols_to_remove: tuple[str, ...] = DEFAULT_WRAP_SYMBOLS_TO_REMOVE,
        symbols_to_ignore_wrap: tuple[str, ...] = DEFAULT_SYMBOLS_TO_IGNORE_WRAP,
        zero_width_symbols: tuple[str, ...] = DEFAULT_ZERO_WIDTH_SYMBOLS,
    ) -> GalTextT:
        """
        对 items[*].message 应用自动换行。
        """
        for item, message in _iter_wrappable_items(self.items, symbols_to_ignore_wrap):
            item["message"] = str_auto_wrap(
                message,
                max_width=max_width,
                wrap_symbol=wrap_symbol,
                wrap_symbols_to_remove=wrap_symbols_to_remove,
                zero_width_symbols=zero_width_symbols,
            )

        return self

    def apply_remove_wrap(
        self: GalTextT,
        wrap_symbols_to_remove: tuple[str, ...] = DEFAULT_WRAP_SYMBOLS_TO_REMOVE,
        symbols_to_ignore_wrap: tuple[str, ...] = DEFAULT_SYMBOLS_TO_IGNORE_WRAP,
    ) -> GalTextT:
        """
        对 items[*].message 应用移除换行。
        """
        for item, message in _iter_wrappable_items(self.items, symbols_to_ignore_wrap):
            item["message"] = str_remove_wrap(
                message,
                wrap_symbols_to_remove=wrap_symbols_to_remove,
            )

        return self

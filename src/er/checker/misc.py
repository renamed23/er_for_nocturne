import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass

from er.core.gal_text_t import DEFAULT_ITEM_TEXT_FIELDS, GalTextT
from er.utils.misc import ensure_str, str_or_none


DEFAULT_DUPLICATE_QUOTES: tuple[str, ...] = ("「「", "」」", "『『", "』』")

DEFAULT_FORBIDDEN_WORDS: tuple[str, ...] = (
    "学长",  # 统一为前辈
    "学姐",
    "学弟",  # 统一为后辈
    "学妹",
    "酱",  # 使用'小XX'而不是'XX酱'
    "肉刃",
    "桑",
    "甬道",
    "妳",  # 使用'你'
    "name",
    "dst",
    "message",
    ":",
    "甫",  # 使用 '刚' 或者 '刚刚'
    "●",
    "�",
)

KOREAN_PATTERN = re.compile(r"[ㄱ-ㅎㅏ-ㅣ가-힣]")

HIRAGANA_PATTERN = re.compile(r"[\u3040-\u309F]")

KATAKANA_PATTERN = re.compile(r"[\u30A0-\u30FF]")

INVISIBLE_PATTERN = re.compile(
    r"[\u2000-\u200F\u2028\u2029\u202A-\u202E\u205F\u2060-\u2064\u206A-\u206F\uFEFF\u180E\u2063]"
)

INVISIBLE_CHAR_NAMES: dict[str, str] = {
    # 定宽空格 (En/Em/Mid/Thin Space 等，AI 乱缩进产物)
    "\u2000": "U+2000(半字宽空格/En Quad)",
    "\u2001": "U+2001(全字宽空格/Em Quad)",
    "\u2002": "U+2002(半字宽空格/En Space)",
    "\u2003": "U+2003(全字宽空格/Em Space)",
    "\u2004": "U+2004(三分之一字宽空格)",
    "\u2005": "U+2005(四分之一字宽空格)",
    "\u2006": "U+2006(六分之一字宽空格)",
    "\u2007": "U+2007(数字空格)",
    "\u2008": "U+2008(标点空格)",
    "\u2009": "U+2009(细空格)",
    "\u200a": "U+200A(极细空格)",
    # 零宽度与连接符
    "\u200b": "U+200B(零宽度空格)",
    "\u200c": "U+200C(零宽度非连接符)",
    "\u200d": "U+200D(零宽度连接符)",
    "\u200e": "U+200E(左至右标记)",
    "\u200f": "U+200F(右至左标记)",
    # 段落/行分隔符
    "\u2028": "U+2028(行分隔符)",
    "\u2029": "U+2029(段落分隔符)",
    # 双向文本控制 (容易导致排版逻辑错乱)
    "\u202a": "U+202A(左至右嵌入)",
    "\u202b": "U+202B(右至左嵌入)",
    "\u202c": "U+202C(弹出方向格式化)",
    "\u202d": "U+202D(左至右覆盖)",
    "\u202e": "U+202E(右至左覆盖)",
    # 数学/特殊占位
    "\u205f": "U+205F(中数学空格)",
    "\u2060": "U+2060(单词连接符)",
    "\u2061": "U+2061(函数应用)",
    "\u2062": "U+2062(不可见乘号)",
    "\u2063": "U+2063(不可见分隔符)",
    "\u2064": "U+2064(不可见加号)",
    "\u206a": "U+206A(不可见禁止对称交换)",
    "\u206b": "U+206B(不可见激活对称交换)",
    "\ufeff": "U+FEFF(零宽度不换行空格/BOM)",
    "\u180e": "U+180E(蒙古文元音分隔符)",
}

# Unicode 私用区范围：
# 1. BMP (E000-F8FF)
# 2. Plane 15 (F0000-FFFFD)
# 3. Plane 16 (100000-10FFFD)
PUA_PATTERN = re.compile(r"[\uE000-\uF8FF]|\U000F0000-\U000FFFFD|\U00100000-\U0010FFFD")

OPEN_TO_CLOSE_QUOTES: dict[str, str] = {
    "「": "」",
    "『": "』",
    "“": "”",
    "‘": "’",
    "（": "）",
}


@dataclass(frozen=True)
class TextCheckTarget:
    """
    封装检查目标的上下文信息。

    Attributes:
        location: 错误发生的位置描述（如 'items[10]'）。
        field: 检查的字段名（如 'message'）。
        raw_text: 该字段对应的原始文本。
        text: 待检查的译文文本。
    """

    location: str
    field: str
    raw_text: str
    text: str


def _highlight_literals(text: str, literals: Iterable[str]) -> str:
    """
    在文本中用【】包裹指定的字面量以实现高亮显示。

    Args:
        text: 目标文本。
        literals: 需要高亮的字符串列表。

    Returns:
        处理后的字符串。
    """
    highlighted = text
    for literal in sorted(set(literals), key=len, reverse=True):
        highlighted = highlighted.replace(literal, f"【{literal}】")
    return highlighted


def _iter_check_targets(
    names: dict[str, str],
    items: list[dict[str, object]],
    item_fields: tuple[str, ...] = DEFAULT_ITEM_TEXT_FIELDS,
    include_names: bool = True,
) -> Iterable[TextCheckTarget]:
    """
    生成器：遍历所有待检查的文本目标，自动关联原文与译文。

    Args:
        names: 角色名映射表。
        items: 文本条目列表。
        item_fields: 需要检查的项目字段。
        include_names: 是否包含角色名表的检查。

    Yields:
        TextCheckTarget 对象。
    """
    if include_names:
        for raw_name, name in names.items():
            yield TextCheckTarget(
                location=f"names['{raw_name}']",
                field="name",
                raw_text=raw_name,
                text=name,
            )

    for index, item in enumerate(items):
        for field in item_fields:
            value = str_or_none(item.get(field))
            if value is None:
                continue

            raw_text = ensure_str(item.get(f"raw_{field}"))

            yield TextCheckTarget(
                location=f"items[{index}]",
                field=field,
                raw_text=raw_text,
                text=value,
            )


def _append_block_error(
    errors: list[str],
    target: TextCheckTarget,
    title: str,
    detail: str,
    highlighted: str,
) -> None:
    """
    向错误列表中添加一个格式化的错误报告块。

    每个块包含位置、字段信息、原/译文对照及高亮显示，末尾带空行分隔。
    """
    errors.append(f"{target.location} {target.field}字段{title}: {detail}")
    errors.append(f"  原文{target.field}: {target.raw_text}")
    errors.append(f"  译文{target.field}: {target.text}")
    errors.append(f"  高亮显示: {highlighted}")
    errors.append("")


def _check_by_literals(
    names: dict[str, str],
    items: list[dict[str, object]],
    errors: list[str],
    literals: tuple[str, ...],
    title: str,
    item_fields: tuple[str, ...] = DEFAULT_ITEM_TEXT_FIELDS,
    include_names: bool = True,
) -> None:
    """
    基于固定字面量列表进行文本匹配检查。

    遍历所有检查目标，若译文中包含任意一个指定的字面量（如禁用词、重复引号），
    则生成一个格式化的错误块并追加到 errors 列表中。

    Args:
        names: 角色名映射表 {原文: 译文}。
        items: 文本条目列表。
        errors: 错误信息收集列表。注意：本函数会直接修改此列表。
        literals: 待匹配的字面量元组（如禁用词列表）。
        title: 错误块的标题描述（如 "中包含禁用词"）。
        item_fields: 需要检查的项目字段名集合。
        include_names: 是否同时检查角色名映射表。
    """
    for target in _iter_check_targets(
        names,
        items,
        item_fields=item_fields,
        include_names=include_names,
    ):
        found = [literal for literal in literals if literal in target.text]
        if not found:
            continue

        _append_block_error(
            errors,
            target,
            title=title,
            detail=", ".join(found),
            highlighted=_highlight_literals(target.text, found),
        )


def _check_by_char_matches(
    names: dict[str, str],
    items: list[dict[str, object]],
    errors: list[str],
    title: str,
    finder: Callable[[str], list[str]],
    item_fields: tuple[str, ...] = DEFAULT_ITEM_TEXT_FIELDS,
    include_names: bool = True,
    detail_builder: Callable[[list[str]], str] | None = None,
) -> None:
    """
    基于字符匹配逻辑（通常是正则）进行文本检查。

    通过传入的 finder 函数提取文本中的非法字符，并支持自定义详情构建。

    Args:
        names: 角色名映射表。
        items: 文本条目列表。
        errors: 错误信息收集列表。
        title: 错误块的标题描述（如 "中包含韩文字符"）。
        finder: 匹配函数。接收一个字符串，返回所有匹配到的非法字符列表。
            通常使用 re.findall 实现。
        item_fields: 需要检查的项目字段名集合。
        include_names: 是否检查角色名映射表。
        detail_builder: 可选。自定义错误详情字符串的构建逻辑。
            接收 finder 返回的字符列表，返回一段描述文本。若为 None，则默认使用字符集的排序列表。
    """
    for target in _iter_check_targets(
        names,
        items,
        item_fields=item_fields,
        include_names=include_names,
    ):
        matches = finder(target.text)
        if not matches:
            continue

        detail = (
            detail_builder(matches) if detail_builder else str(sorted(set(matches)))
        )
        _append_block_error(
            errors,
            target,
            title=title,
            detail=detail,
            highlighted=_highlight_literals(target.text, sorted(set(matches))),
        )


class MiscCheckerMixin:
    """
    GalText 检查混合类

    提供多样化的文本合规性检查方法。
    所有方法均遵循链式调用约定，返回 self 并将错误记录至 self.errors。
    """

    def check_duplicate_quotes(self: GalTextT) -> GalTextT:
        """
        检查译文中是否包含重复的引号（如「「）。
        """
        _check_by_literals(
            self.names,
            self.items,
            self.errors,
            DEFAULT_DUPLICATE_QUOTES,
            title="中包含重复引号",
        )
        return self

    def check_forbidden_words(self: GalTextT) -> GalTextT:
        """
        检查译文中是否包含禁用词（如残留的 JSON 键名或不符合规范的称呼）。
        """
        _check_by_literals(
            self.names,
            self.items,
            self.errors,
            DEFAULT_FORBIDDEN_WORDS,
            title="中包含禁用词",
        )
        return self

    def check_korean_characters(self: GalTextT) -> GalTextT:
        """
        检查译文中是否包含韩文字符（ㄱ-ㅎ, ㅏ-ㅣ, 가-힣）。
        """
        _check_by_char_matches(
            self.names,
            self.items,
            self.errors,
            title="中包含韩文字符",
            finder=lambda text: KOREAN_PATTERN.findall(text),
        )
        return self

    def check_japanese_characters(self: GalTextT) -> GalTextT:
        """
        检查译文中是否包含日语假名（平假名/片假名）。

        注：本检查不包含日语汉字，仅针对明确的假名残留。
        """

        def finder(text: str) -> list[str]:
            return HIRAGANA_PATTERN.findall(text) + KATAKANA_PATTERN.findall(text)

        def detail_builder(matches: list[str]) -> str:
            hiragana = sorted({ch for ch in matches if HIRAGANA_PATTERN.fullmatch(ch)})
            katakana = sorted({ch for ch in matches if KATAKANA_PATTERN.fullmatch(ch)})
            details: list[str] = []
            if hiragana:
                details.append(f"平假名{hiragana}")
            if katakana:
                details.append(f"片假名{katakana}")
            return " ".join(details)

        _check_by_char_matches(
            self.names,
            self.items,
            self.errors,
            title="中包含日语假名字符",
            finder=finder,
            detail_builder=detail_builder,
        )
        return self

    def check_invisible_characters(self: GalTextT) -> GalTextT:
        """
        检查并识别译文中的不可见字符（如零宽度空格 U+200B、定宽空格 U+2005）。

        高亮显示时会替换为字符对应的 Unicode 名称或编码，方便定位。
        """
        for target in _iter_check_targets(self.names, self.items):
            invisible_matches = INVISIBLE_PATTERN.findall(target.text)
            if not invisible_matches:
                continue

            char_count: dict[str, int] = {}
            for char in invisible_matches:
                char_count[char] = char_count.get(char, 0) + 1

            details: list[str] = []
            for char, count in char_count.items():
                char_name = INVISIBLE_CHAR_NAMES.get(
                    char, f"U+{ord(char):04X}(未知不可见字符)"
                )
                details.append(f"{char_name}: {count}次")

            highlighted = target.text
            for char in char_count:
                # 获取名称中的编码部分用于高亮，例如将 "U+200B(零宽度空格)" 提取为 "U+200B"
                char_info = INVISIBLE_CHAR_NAMES.get(char, f"U+{ord(char):04X}")
                char_code = char_info.split("(")[0]
                highlighted = highlighted.replace(char, f"【{char_code}】")

            _append_block_error(
                self.errors,
                target,
                title="中包含不可见字符",
                detail="; ".join(details),
                highlighted=highlighted,
            )
        return self

    def check_unpaired_quotes(self: GalTextT) -> GalTextT:
        """
        使用栈算法检查成对标点（「」、『』、“”、‘’、（））是否正确闭合。

        支持嵌套检查。如果发现未关闭或多余的引号，将记录具体位置。
        """
        close_to_open = {v: k for k, v in OPEN_TO_CLOSE_QUOTES.items()}

        for target in _iter_check_targets(self.names, self.items):
            stack: list[tuple[str, int]] = []
            details: list[str] = []

            for pos, char in enumerate(target.text):
                if char in OPEN_TO_CLOSE_QUOTES:
                    stack.append((char, pos))
                elif char in close_to_open:
                    if stack and stack[-1][0] == close_to_open[char]:
                        stack.pop()
                    else:
                        details.append(f"位置 {pos}: 多余的 '{char}'")

            for quote_char, pos in stack:
                details.append(f"位置 {pos}: 未关闭的 '{quote_char}'")

            if not details:
                continue

            highlighted_chars = list(target.text)
            for quote_char, pos in stack:
                highlighted_chars[pos] = f"【{quote_char}】"

            temp_stack: list[str] = []
            for pos, char in enumerate(target.text):
                if char in OPEN_TO_CLOSE_QUOTES:
                    temp_stack.append(char)
                elif char in close_to_open:
                    if temp_stack and temp_stack[-1] == close_to_open[char]:
                        temp_stack.pop()
                    else:
                        highlighted_chars[pos] = f"【{char}】"

            _append_block_error(
                self.errors,
                target,
                title="中存在未配对的引号",
                detail="; ".join(details),
                highlighted="".join(highlighted_chars),
            )

        return self

    def check_quote_consistency(self: GalTextT) -> GalTextT:
        """
        对比原文与译文的首尾引号是否一致。

        严格校验引号类型。如果原文以「开头，译文也必须以「开头。
        """

        def _contains_quote_marker(text: str) -> bool:
            return bool(text) and (text[0] in "「『」』" or text[-1] in "「『」』")

        for target in _iter_check_targets(self.names, self.items):
            raw_text = target.raw_text.strip()
            text = target.text.strip()

            if not raw_text or not text:
                continue

            if not (_contains_quote_marker(raw_text) or _contains_quote_marker(text)):
                continue

            has_error = False
            details: list[str] = []

            if raw_text[0] in "「『" and raw_text[0] != text[0]:
                has_error = True
                details.append(f"开头引号不一致: 原文'{raw_text[0]}' 译文'{text[0]}'")
            if raw_text[-1] in "」』" and raw_text[-1] != text[-1]:
                has_error = True
                details.append(f"结尾引号不一致: 原文'{raw_text[-1]}' 译文'{text[-1]}'")
            if text[0] in "「『" and raw_text[0] != text[0]:
                has_error = True
                details.append(
                    f"译文额外开头引号不一致: 原文'{raw_text[0]}' 译文'{text[0]}'"
                )
            if text[-1] in "」』" and raw_text[-1] != text[-1]:
                has_error = True
                details.append(
                    f"译文额外结尾引号不一致: 原文'{raw_text[-1]}' 译文'{text[-1]}'"
                )

            if has_error:
                _append_block_error(
                    self.errors,
                    target,
                    title="首尾引号不一致",
                    detail="; ".join(details),
                    highlighted=target.text,
                )
        return self

    def check_length_discrepancy(
        self: GalTextT,
        max_ratio: float = 2.0,
        min_ratio: float = 0.3,
    ) -> GalTextT:
        """
        根据原文长度校验译文长度的异常偏差。

        Args:
            max_ratio: 最大比例阈值，超过则视为过长。
            min_ratio: 最小比例阈值，低于则视为过短。
        """
        for target in _iter_check_targets(self.names, self.items):
            raw_len = len(target.raw_text)
            text_len = len(target.text)

            if raw_len == 0:
                continue

            ratio = text_len / raw_len
            if ratio > max_ratio:
                _append_block_error(
                    self.errors,
                    target,
                    title="长度过长",
                    detail=(
                        f"原文长度 {raw_len}，译文长度 {text_len}，"
                        f"比例 {ratio:.2f} (超过阈值 {max_ratio})"
                    ),
                    highlighted=target.text,
                )
            elif ratio < min_ratio:
                _append_block_error(
                    self.errors,
                    target,
                    title="长度过短",
                    detail=(
                        f"原文长度 {raw_len}，译文长度 {text_len}，"
                        f"比例 {ratio:.2f} (低于阈值 {min_ratio})"
                    ),
                    highlighted=target.text,
                )

        return self

    def check_max_text_len(self: GalTextT, max_text_len: int = 128) -> GalTextT:
        """
        检查译文单行是否超过游戏长度限制。

        Args:
            max_text_len: 允许的最大字符数。
        """
        for target in _iter_check_targets(
            self.names,
            self.items,
            item_fields=("message",),
            include_names=False,
        ):
            text_len = len(target.text)
            if text_len <= max_text_len:
                continue

            _append_block_error(
                self.errors,
                target,
                title="超长",
                detail=f"{text_len} > {max_text_len}",
                highlighted=target.text,
            )
        return self

    def check_pua_characters(self: GalTextT) -> GalTextT:
        """
        检查译文中是否包含 Unicode 私用区 (PUA) 字符（如  / U+E108）。

        这些字符通常是原游戏的自定义外字或图标，在译文中直接出现会导致乱码。
        """

        def finder(text: str) -> list[str]:
            return PUA_PATTERN.findall(text)

        def detail_builder(matches: list[str]) -> str:
            # 统计并显示具体的编码，方便定位
            unique_matches = sorted(set(matches))
            return ", ".join([f"U+{ord(m):04X}" for m in unique_matches])

        _check_by_char_matches(
            self.names,
            self.items,
            self.errors,
            title="中包含私用区(PUA)乱码字符",
            finder=finder,
            detail_builder=detail_builder,
        )
        return self

    def check_font_glyphs(self: GalTextT, font_path: str) -> GalTextT:
        """
        检查译文中的所有字符是否都能在指定的字体文件中找到对应字形。
        使用 fontTools 扫描 cmap 表以确保字符可用性。
        """
        try:
            from fontTools.ttLib import TTFont

            font = TTFont(font_path)
            cmap = font.getBestCmap()
            font.close()

            if cmap is None:
                raise ValueError("无法获取字体的 Cmap 表")
        except Exception as e:
            self.errors.append(f"系统错误: 无法加载检查字体 '{font_path}': {e}")
            return self

        def finder(text: str) -> list[str]:
            missing_chars = []
            for char in text:
                # 忽略空白字符（通常不需要字形）
                if char.isspace():
                    continue
                # 检查字符的 Unicode 编码是否在字体的 cmap 中
                if ord(char) not in cmap:
                    missing_chars.append(char)
            return missing_chars

        def detail_builder(matches: list[str]) -> str:
            unique_chars = sorted(set(matches))
            char_info = [f"'{c}'(U+{ord(c):04X})" for c in unique_chars]
            return f"字体 [{font_path}] 缺失字形: {', '.join(char_info)}"

        _check_by_char_matches(
            self.names,
            self.items,
            self.errors,
            title="中包含字体无法显示的生僻字",
            finder=finder,
            detail_builder=detail_builder,
        )

        return self

    def check_per_line_limit(self: GalTextT, chars_per_line: int = 24) -> GalTextT:
        """
        检查 message 字段是否超过 (line * chars_per_line) 的总字符限制。
        """
        # 我们只针对 message 字段进行逻辑检查
        for index, item in enumerate(self.items):
            # 1. 提取必要字段
            message = str_or_none(item.get("message"))
            line_count = item.get("line")

            # 2. 只有当 message 存在且 line 是有效数字时才检查
            if message is None or not isinstance(line_count, int):
                continue

            # 3. 计算阈值
            max_allowed = int(line_count) * chars_per_line
            actual_len = len(message)

            if actual_len > max_allowed:
                # 构建 target 以复用错误汇报格式
                target = TextCheckTarget(
                    location=f"items[{index}]",
                    field="message",
                    raw_text=ensure_str(item.get("raw_message")),
                    text=message,
                )

                _append_block_error(
                    self.errors,
                    target,
                    title="行数长度超标",
                    detail=(
                        f"该条目限制为 {line_count} 行，每行预设 {chars_per_line} 字，"
                        f"最大允许 {max_allowed} 字，实际 {actual_len} 字"
                    ),
                    highlighted=message,
                )
        return self

    def check_keep_len_limit(self: GalTextT) -> GalTextT:
        """
        检查 message 字段是否超过字节长度限制。

        逻辑：
        1. 如果 keep_len 为 True：
        2. 若存在 len 字段，则 message 编码后的字节数不得大于该值。
        3. 若不存在 len 字段，则 message 编码后的字节数不得大于 raw_message 编码后的字节数。
        """
        for index, item in enumerate(self.items):
            # 只有 keep_len 为 True 时才进行检查
            if item.get("keep_len") is not True:
                continue

            message = str_or_none(item.get("message"))
            if message is None:
                continue

            # 获取字节长度限制
            limit_len = item.get("len")
            raw_msg = ensure_str(item.get("raw_message"))

            # 如果没有显式的 len 字段，则动态计算原文的 CP932 长度
            if not isinstance(limit_len, int):
                limit_len = len(raw_msg.encode("cp932"))

            # 计算译文的 CP932 长度
            actual_bytes_len = len(message.encode("cp932"))

            if actual_bytes_len > limit_len:
                offset_info = (
                    f" (Offset: 0x{item['offset']:X})" if "offset" in item else ""
                )
                target = TextCheckTarget(
                    location=f"items[{index}]{offset_info}",
                    field="message",
                    raw_text=raw_msg,
                    text=message,
                )

                _append_block_error(
                    self.errors,
                    target,
                    title="字节长度溢出",
                    detail=(
                        f"要求保持原长度。限制字节数: {limit_len}, "
                        f"实际字节数(CP932): {actual_bytes_len}"
                    ),
                    highlighted=message,
                )

        return self

    def check_at_sign_count_consistency(self: GalTextT) -> GalTextT:
        """
        检查原文与译文中 '@' 符号的数量是否一致。
        """
        for target in _iter_check_targets(self.names, self.items):
            raw_count = target.raw_text.count("@")
            text_count = target.text.count("@")
            if raw_count == text_count:
                continue

            detail = f"原文 '@' 数量: {raw_count}, 译文 '@' 数量: {text_count}"
            _append_block_error(
                self.errors,
                target,
                title="中 '@' 符号数量不一致",
                detail=detail,
                highlighted=target.text,
            )
        return self

    def check_empty_translation(self: GalTextT) -> GalTextT:
        """
        检查原文非空但译文为空字符串（长度为0）的情况。
        """
        for target in _iter_check_targets(self.names, self.items):
            # 原文为空则跳过
            if not target.raw_text:
                continue
            # 译文长度为0
            if len(target.text) == 0:
                _append_block_error(
                    self.errors,
                    target,
                    title="译文为空",
                    detail="原文存在内容但译文为空字符串",
                    highlighted="【空】",
                )
        return self

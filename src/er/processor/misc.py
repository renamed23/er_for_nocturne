import re
from collections.abc import Callable
from er.core.gal_text_t import DEFAULT_ITEM_TEXT_FIELDS, GalTextT


DEFAULT_TAG_MAPPINGS: dict[str, str] = {
    "is_select": "[select]",
    "is_title": "[title]",
}


FULLWIDTH_SPACE_REMOVE_MAP: dict[str, str] = {"\u3000": ""}

BACKSLASH_ESCAPE_MAP: dict[str, str] = {"\\": "@"}

BACKSLASH_UNESCAPE_MAP: dict[str, str] = {"@": "\\"}

RARE_CHARACTER_MAP: dict[str, str] = {
    "𫚕鱼": "季鱼",
    "𬶮鱼": "宗鱼",
}

GBK_UNSUPPORTED_CHAR_MAP: dict[str, str] = {
    "〜": "～",
    "・": "·",
    "♪": "～",
    "♥": "～",
    "♡": "～",
}

QUOTATION_MARK_MAP: dict[str, str] = {
    "〝": "『",
    "〟": "』",
}


def str_replace_standard_quotes(text: str) -> str:
    """
    将文本中成对出现的双引号 “” 替换为直角引号 「」。

    逻辑：使用栈追踪““”，只有当成功匹配到对应的“””时，才将这一对字符进行替换。
    不匹配的单边引号将保持原样，避免破坏特定语境下的文本。
    """
    if "“" not in text and "”" not in text:
        return text

    stack: list[int] = []  # 存储左引号 “ 的索引
    result_chars = list(text)

    for index, char in enumerate(text):
        if char == "“":
            stack.append(index)
        elif char == "”" and stack:
            # 找到匹配的一对
            start_index = stack.pop()
            result_chars[start_index] = "「"
            result_chars[index] = "」"

    # 栈中剩下的 start_index 说明是未闭合的 “，result_chars 中保持原样即可
    return "".join(result_chars)


def str_remove_hiragana(text: str, count: int) -> str:
    """
    删除文本中的前count个平假名。
    用于模拟文本变短，同时保留后续平假名供其他测试使用。
    """
    if not text:
        return text
    return re.sub(r"[\u3040-\u309f]", "", text, count)


def str_map_all_to_zhong(text: str) -> str:
    """
    将文本中所有的汉字、平假名、片假名全部映射为 '中'。
    用于快速肉眼检测是否提漏了文本（如果处理后还剩下日文字符，说明没提全）。
    """
    if not text:
        return text

    # [ \u4e00-\u9fff ] : 涵盖了绝大多数常用和增补汉字
    # [ \u3400-\u4dbf ] : CJK Extension A (也是很常用的生僻字区)
    # [ \u3040-\u309f ] : 平假名
    # [ \u30a0-\u30ff ] : 片假名
    pattern = r"[\u4e00-\u9fff\u3400-\u4dbf\u3040-\u309f\u30a0-\u30ff]"

    return re.sub(pattern, "中", text)


def str_add_test_prefix_suffix(text: str) -> str:
    """
    在文本开头加上 '中文测试'。
    如果开头为 [，则在末尾加上 '中文测试'。
    """
    if not text:
        return "中文测试"

    if text.startswith("["):
        return f"{text}中文测试"

    return f"中文测试{text}"


def str_replace_by_map(text: str, mapping: dict[str, str]) -> str:
    """
    按映射表进行全量文本替换。

    Args:
        text: 待处理的原始文本。
        mapping: 替换映射表 {旧字符串: 新字符串}。

    Returns:
        替换后的文本。若 text 为空则原样返回。
    """
    if not text:
        return text

    result = text
    for old, new in mapping.items():
        result = result.replace(old, new)
    return result


def str_replace_nested_brackets(text: str) -> str:
    """
    将文本中嵌套层级的「」自动替换为外圆内方的『』。

    逻辑：使用栈追踪深度，只有当深度 >= 2 时的括号对才会被替换。
    常用于 GalGame 翻译中处理对话内套对话的标点规范。
    """
    if "「" not in text and "」" not in text:
        return text

    stack: list[int] = []
    result_chars = list(text)

    for index, char in enumerate(text):
        if char == "「":
            stack.append(index)
        elif char == "」" and stack:
            start_index = stack.pop()
            if len(stack) >= 1:
                result_chars[start_index] = "『"
                result_chars[index] = "』"

    return "".join(result_chars)


def apply_text_transform_to_data(
    names: dict[str, str],
    items: list[dict[str, object]],
    transform: Callable[[str], str],
    item_fields: tuple[str, ...],
    include_names: bool = True,
) -> None:
    """
    通用底层分发函数：对名字表和正文条目列表执行统一的映射替换。

    Args:
        names: 角色名映射字典。
        items: 条目字典列表。
        transform: 对文本的处理函数
        item_fields: items 中需要被处理的字段名。
        include_names: 是否同时处理 names 表中的译文值。
    """
    if include_names:
        for raw_name, name in names.items():
            names[raw_name] = transform(name)

    for item in items:
        for field in item_fields:
            value = item.get(field)
            if isinstance(value, str):
                item[field] = transform(value)


class MiscProcessorMixin:
    """
    杂项文本处理混入类，提供 GalGame 文本清理和格式标准化以及生成测试数据的链式调用接口。

    要求宿主类必须符合 GalTextT 协议。
    """

    def apply_transform(
        self: GalTextT,
        transform: Callable[[str], str],
        item_fields: tuple[str, ...] = DEFAULT_ITEM_TEXT_FIELDS,
        include_names: bool = True,
    ) -> GalTextT:
        """
        通用文本处理接口，允许自定义字段和映射表。

        Args:
            transform: 对文本的处理函数
            item_fields: items 中需要被处理的字段名。
            include_names: 是否同时处理 names 表中的译文值。
        """
        apply_text_transform_to_data(
            self.names,
            self.items,
            transform,
            item_fields=item_fields,
            include_names=include_names,
        )
        return self

    def apply_current_to_raw_fields(self: GalTextT) -> GalTextT:
        """
        将当前条目中的 name/message 覆盖回 raw_name/raw_message。

        用于在完成一系列文本处理后，把处理结果写回“原文字段”，
        便于后续检查逻辑以最新文本作为对照基准。
        """
        for item in self.items:
            name = item.get("name")
            if isinstance(name, str):
                item["raw_name"] = name

            message = item.get("message")
            if isinstance(message, str):
                item["raw_message"] = message

        return self

    def apply_raw_to_current_fields(self: GalTextT) -> GalTextT:
        """
        将 raw_name/raw_message 覆盖回当前条目中的 name/message。

        用于撤销之前的处理结果，将当前显示的文本还原为原始文本，
        或者在处理流程出错时进行回滚。
        """
        for item in self.items:
            # 还原 name 字段
            raw_name = item.get("raw_name")
            if isinstance(raw_name, str):
                item["name"] = raw_name

            # 还原 message 字段
            raw_message = item.get("raw_message")
            if isinstance(raw_message, str):
                item["message"] = raw_message

        return self

    def apply_mark_whitespace(self: GalTextT) -> GalTextT:
        """
        若 message 以全角空格开头，则在 item 中注入 need_whitespace=True 标记。
        用于在处理过程中暂时去除空格，最后再还原。
        """
        for item in self.items:
            message = item.get("message")
            if isinstance(message, str) and message.startswith("\u3000"):
                item["need_whitespace"] = True
        return self

    def apply_restore_whitespace(self: GalTextT) -> GalTextT:
        """
        根据 need_whitespace 标记，强制在 message 开头补回全角空格。
        """
        for item in self.items:
            if item.get("need_whitespace") is not True:
                continue
            message = item.get("message")
            if isinstance(message, str) and not message.startswith("\u3000"):
                item["message"] = f"\u3000{message}"
        return self

    def apply_add_tags(
        self: GalTextT,
        tag_mappings: dict[str, str] = DEFAULT_TAG_MAPPINGS,
    ) -> GalTextT:
        """
        根据 item 中的布尔标记（如 is_select），在 message 前缀添加可视化标签。
        常用于提供给翻译者识别该文本是选项还是标题。
        """
        for item in self.items:
            message = item.get("message")
            if not isinstance(message, str):
                continue

            for field, tag in tag_mappings.items():
                if item.get(field) is True and not message.startswith(tag):
                    message = f"{tag}{message}"

            item["message"] = message
        return self

    def apply_remove_tags(
        self: GalTextT,
        tag_mappings: dict[str, str] = DEFAULT_TAG_MAPPINGS,
        strict: bool = True,
    ) -> GalTextT:
        """
        移除 apply_add_tags 添加的前缀标签。

        Args:
            strict: 若为 True，当字段标记为 True 但 message 却没有标签时抛出 ValueError。
        """
        for item in self.items:
            message = item.get("message")
            if not isinstance(message, str):
                continue

            for field, tag in tag_mappings.items():
                if item.get(field) is not True:
                    continue

                if message.startswith(tag):
                    message = message[len(tag) :]
                    continue

                if strict:
                    raise ValueError(
                        f"数据不一致：字段 {field}=True，但文本未发现标签 {tag}。文本内容: {message}"
                    )

            item["message"] = message
        return self

    def apply_replace_nested_brackets(
        self: GalTextT,
    ) -> GalTextT:
        """统一应用嵌套括号替换。"""
        apply_text_transform_to_data(
            self.names,
            self.items,
            str_replace_nested_brackets,
            item_fields=("message",),
            include_names=False,
        )
        return self

    def apply_replace_standard_quotes(self: GalTextT) -> GalTextT:
        """将所有的双引号 “” 替换为直角引号 「」。"""
        apply_text_transform_to_data(
            self.names,
            self.items,
            str_replace_standard_quotes,
            item_fields=("message",),
            include_names=False,
        )
        return self

    def apply_remove_fullwidth_spaces(self: GalTextT) -> GalTextT:
        """清理全角空格。建议在 apply_mark_whitespace 之后使用。"""
        apply_text_transform_to_data(
            self.names,
            self.items,
            lambda value: str_replace_by_map(value, FULLWIDTH_SPACE_REMOVE_MAP),
            DEFAULT_ITEM_TEXT_FIELDS,
        )
        return self

    def apply_escape_backslashes(self: GalTextT) -> GalTextT:
        """转义反斜杠为 @，防止某些正则或翻译引擎将其识别为转义符。"""
        apply_text_transform_to_data(
            self.names,
            self.items,
            lambda value: str_replace_by_map(value, BACKSLASH_ESCAPE_MAP),
            DEFAULT_ITEM_TEXT_FIELDS,
        )
        return self

    def apply_unescape_backslashes(self: GalTextT) -> GalTextT:
        """将 @ 还原回反斜杠。"""
        apply_text_transform_to_data(
            self.names,
            self.items,
            lambda value: str_replace_by_map(value, BACKSLASH_UNESCAPE_MAP),
            DEFAULT_ITEM_TEXT_FIELDS,
        )
        return self

    def apply_replace_rare_characters(self: GalTextT) -> GalTextT:
        """替换系统不支持的罕见字/生僻字（如鱼类名称）。"""
        apply_text_transform_to_data(
            self.names,
            self.items,
            lambda value: str_replace_by_map(value, RARE_CHARACTER_MAP),
            DEFAULT_ITEM_TEXT_FIELDS,
        )
        return self

    def apply_replace_quotation_marks(self: GalTextT) -> GalTextT:
        """将某些引擎特有的引号（如〝〟）标准化为直角引号。仅处理 message。"""
        apply_text_transform_to_data(
            self.names,
            self.items,
            lambda value: str_replace_by_map(value, QUOTATION_MARK_MAP),
            item_fields=("message",),
            include_names=False,
        )
        return self

    def apply_map_gbk_unsupported_chars(self: GalTextT) -> GalTextT:
        """
        将繁体或日文特有的符号映射为 GBK 编码支持的近似符号。
        防止封包后在旧系统或特定引擎上出现乱码。
        """
        apply_text_transform_to_data(
            self.names,
            self.items,
            lambda value: str_replace_by_map(value, GBK_UNSUPPORTED_CHAR_MAP),
            DEFAULT_ITEM_TEXT_FIELDS,
        )
        return self

    def apply_remove_hiragana(self: GalTextT, count: int) -> GalTextT:
        """测试用：仅删除前count个平假名，模拟文本长度缩减。"""
        apply_text_transform_to_data(
            self.names,
            self.items,
            lambda value: str_remove_hiragana(value, count),
            DEFAULT_ITEM_TEXT_FIELDS,
        )
        return self

    def apply_map_all_to_zhong(self: GalTextT) -> GalTextT:
        """测试用：将汉字/平假名/片假名替换为“中”。"""
        apply_text_transform_to_data(
            self.names,
            self.items,
            str_map_all_to_zhong,
            DEFAULT_ITEM_TEXT_FIELDS,
        )
        return self

    def apply_add_chinese_test_tag(self: GalTextT) -> GalTextT:
        """测试用：在文本边界添加“中文测试”标记。"""
        apply_text_transform_to_data(
            self.names,
            self.items,
            str_add_test_prefix_suffix,
            DEFAULT_ITEM_TEXT_FIELDS,
        )
        return self

    def apply_align_leading_whitespace(self: GalTextT) -> GalTextT:
        """
        根据 raw_message 自动对齐全角空格。
        如果原始文本以全角空格开头，而当前 message 没有，则强行补齐。
        """
        for item in self.items:
            raw_msg = item.get("raw_message")
            msg = item.get("message")

            if isinstance(raw_msg, str) and isinstance(msg, str):
                if raw_msg.startswith("\u3000") and not msg.startswith("\u3000"):
                    item["message"] = f"\u3000{msg}"
        return self

    def apply_align_brackets_closure(self: GalTextT) -> GalTextT:
        """
        根据 raw_message 的状态对齐 message 的括号。
        无视头尾的空白字符进行判断，但不会删除这些空白字符。
        """
        for item in self.items:
            raw_msg = item.get("raw_message")
            msg = item.get("message")

            if not isinstance(raw_msg, str) or not isinstance(msg, str) or not raw_msg:
                continue

            # --- 处理开头 「 ---
            # 找到第一个非空白字符是否为 「
            raw_has_leading = re.search(r"^\s*「", raw_msg) is not None
            msg_leading_match = re.search(r"^(\s*)(「?)", msg)

            if msg_leading_match:
                spaces_before = msg_leading_match.group(1)
                has_bracket = msg_leading_match.group(2) == "「"

                if raw_has_leading and not has_bracket:
                    # raw有，msg没有 -> 补上，保留原有空格
                    msg = re.sub(r"^\s*", f"{spaces_before}「", msg)
                elif not raw_has_leading and has_bracket:
                    # raw没有，msg有 -> 删掉括号，保留空格
                    msg = re.sub(r"^(\s*)「", r"\1", msg)

            # --- 处理结尾 」 ---
            # 找到最后一个非空白字符是否为 」
            raw_has_trailing = re.search(r"」\s*$", raw_msg) is not None
            msg_trailing_match = re.search(r"(」?)(\s*)$", msg)

            if msg_trailing_match:
                has_bracket = msg_trailing_match.group(1) == "」"
                spaces_after = msg_trailing_match.group(2)

                if raw_has_trailing and not has_bracket:
                    # raw有，msg没有 -> 补上
                    msg = re.sub(r"\s*$", f"」{spaces_after}", msg)
                elif not raw_has_trailing and has_bracket:
                    # raw没有，msg有 -> 删掉
                    msg = re.sub(r"」(\s*)$", r"\1", msg)

            item["message"] = msg
        return self

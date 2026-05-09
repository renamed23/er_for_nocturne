import json

from er.checker.misc import MiscCheckerMixin
from er.processor.ascii_to_fullwidth import FullWidthMixin
from er.processor.auto_wrap import AutoWrapMixin
from er.processor.mapping import MappingMixin
from er.processor.misc import MiscProcessorMixin
from er.utils.console import console
from er.utils.fs import PathLike, to_path
from er.utils.misc import ensure_str, read_json, str_or_none, write_json


class GalJson(
    MappingMixin,
    FullWidthMixin,
    AutoWrapMixin,
    MiscProcessorMixin,
    MiscCheckerMixin,
):
    """
    GalGame 翻译文本 JSON 处理类。

    用于管理角色名称映射表和文本条目列表。
    支持从特定格式的 JSON 数据中恢复状态，并支持导出供翻译使用的格式。
    """

    def __init__(self) -> None:
        # 角色名映射表：{原始姓名: 翻译后姓名}
        self.names: dict[str, str] = {}
        # 文本条目列表：存储对话、旁白等详细信息
        self.items: list[dict[str, object]] = []
        # 当前读取进度指针
        self._item_cursor: int = 0
        # 检查时候存放的错误信息列表
        self.errors: list[str] = []

    def add_name(self, raw_name: str) -> None:
        """添加一个新的待翻译角色名，若已存在则跳过"""
        if raw_name not in self.names:
            self.names[raw_name] = raw_name

    def add_item(self, item: dict[str, object]) -> None:
        """添加条目，并自动提取其中的角色名到映射表"""
        name = str_or_none(item.get("name"))
        if name is not None:
            self.add_name(name)
            if "raw_name" not in item:
                item["raw_name"] = name
        message = ensure_str(item.get("message"))
        if "raw_message" not in item:
            item["raw_message"] = message

        self.items.append(item)

    @staticmethod
    def load(data: list[dict[str, object]]) -> "GalJson":
        """
        从 JSON 数据加载内容。
        """
        gal_json = GalJson()

        parsing_names = True  # 状态标志：是否处于名字解析阶段

        for entry in data:
            if parsing_names and entry.get("is_name") is True:
                # 处于名字阶段且确实是名字条目
                raw_name = ensure_str(entry.get("raw_message"))
                name = ensure_str(entry.get("message", raw_name))
                gal_json.names[raw_name] = name
            else:
                # 一旦遇到非名字条目，永久关闭名字解析阶段
                parsing_names = False
                # 检查：名字条目必须全部在前，不能穿插在正文中
                if entry.get("is_name") is True:
                    raise ValueError(
                        "JSON 格式错误：名字条目必须全部位于数据开头，"
                        + f"不能在正文中穿插名字条目。问题条目: {entry}"
                    )
                gal_json.items.append(entry)

        return gal_json

    @staticmethod
    def load_from_path(path_str: PathLike) -> "GalJson":
        """
        从文件路径加载 JSON 数据并初始化 GalJson 对象。
        """

        path = to_path(path_str)

        if not path.exists():
            raise FileNotFoundError(f"找不到指定的 JSON 文件: {path}")

        try:
            data = read_json(path)
        except json.JSONDecodeError as e:
            raise ValueError(f"JSON 解析失败 '{path}': {e}")
        except Exception as e:
            raise RuntimeError(f"读取文件 '{path}' 时发生未知错误: {e}")

        if not isinstance(data, list):
            raise ValueError(
                f"JSON 数据格式异常: 顶层必须是列表 (list)，当前文件: {path}"
            )

        return GalJson.load(data)

    def get_translated_name(self, raw_name: str) -> str:
        """
        获取翻译后的角色名。
        强制要求：raw_name 必须存在于 names 表中且 message 不为空。
        """
        if raw_name not in self.names:
            raise KeyError(f"未找到角色名 '{raw_name}' 的有效译文，请检查名字表。")
        return self.names[raw_name]

    def dump(self, dump_names: bool = True) -> list[dict[str, object]]:
        """
        导出为翻译格式。
        顺序为：所有名字条目在前，所有正文条目在后。

        Args:
            dump_names: 是否导出角色名映射表
        """
        res: list[dict[str, object]] = []

        # 导出名字映射表
        if dump_names:
            for raw, trans in self.names.items():
                res.append({"message": trans, "is_name": True, "raw_message": raw})

        # 导出正文条目
        res.extend(self.items)
        return res

    def save_to_path(self, path_str: PathLike, dump_names: bool = True) -> "GalJson":
        """
        使用 pathlib 将内容保存到路径。
        """
        path = to_path(path_str)
        path.parent.mkdir(parents=True, exist_ok=True)

        data = self.dump(dump_names=dump_names)

        try:
            write_json(path, data)
        except Exception as e:
            raise IOError(f"写入文件失败 '{path}': {e}")

        return self

    def pop_next_item(self) -> dict[str, object]:
        """弹出下一个文本条目，并移动指针"""
        if self._item_cursor >= len(self.items):
            raise IndexError(
                "译文项已耗尽，脚本索引超出预期！请检查脚本逻辑与 JSON 文件是否匹配。"
            )
        item = self.items[self._item_cursor]
        self._item_cursor += 1
        return item

    def pop_next_message(self) -> str:
        """获取下一个条目的文本内容 (message 字段)"""
        message = ensure_str(
            self.pop_next_item()["message"], f"Item curosr {self._item_cursor - 1}"
        )
        return message

    def reset_cursor(self) -> "GalJson":
        """重置指针"""
        self._item_cursor = 0
        return self

    def is_ran_out(self) -> bool:
        """检查所有文本条目是否已处理完毕"""
        return self._item_cursor == len(self.items)

    def consumed_count(self) -> int:
        """获取当前已消费条目数。

        Returns:
            已消费的文本条目数量。
        """
        return self._item_cursor

    def remaining_count(self) -> int:
        """获取当前剩余未消费条目数。

        Returns:
            剩余未消费的文本条目数量。
        """
        return len(self.items) - self._item_cursor

    def total_count(self) -> int:
        """获取文本条目总数。

        Returns:
            文本条目总数。
        """
        return len(self.items)

    def clear_errors(self) -> "GalJson":
        """清除所有检查时产生的错误"""
        self.errors.clear()
        return self

    def ok_or_print_error_and_exit(self, code: int = 1) -> "GalJson":
        """
        如果检查无错误则返回，否则打印错误信息并以code退出
        """
        if self.errors:
            console.print("检查发现以下错误:", style="error")
            for error in self.errors:
                console.print(error, style="error")
            exit(code)
        return self

    def get_all_chars(
        self, include_names: bool = True, include_raw: bool = False
    ) -> set[str]:
        """
        获取当前对象中所有使用的字符集合。

        Args:
            include_names: 是否包含角色名映射表中的翻译字符。
            include_raw: 是否包含原始字符。

        Returns:
            所使用的字符。
        """
        collector = []
        if include_names:
            for raw, trans in self.names.items():
                collector.append(trans)
                if include_raw:
                    collector.append(raw)

        for item in self.items:
            collector.append(ensure_str(item.get("message", "")))
            if include_raw:
                collector.append(ensure_str(item.get("raw_message", "")))

        return set("".join(collector))

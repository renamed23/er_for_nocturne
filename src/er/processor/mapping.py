from collections import deque
from enum import Enum

from er.core.gal_text_t import GalTextCompatible, GalTextT
from er.utils.fs import PathLike, to_path
from er.utils.misc import ensure_str, read_json, write_json


class EncodingType(Enum):
    """
    支持的编码类型枚举。

    提供编码能力检测、建议字符范围查询和代码页信息。
    """

    CP932 = "cp932"
    SHIFT_JIS = "shift_jis"
    GBK = "gbk"

    def contains_char(self, ch: str) -> bool:
        """
        检查单个字符是否能被当前编码表示。

        ASCII字符始终返回True。非ASCII字符尝试编码，
        失败则返回False。
        """
        if ch.isascii():
            return True
        try:
            ch.encode(self.value, errors="strict")
            return True
        except UnicodeEncodeError:
            return False

    def suggested_ranges(self) -> list[tuple[int, int]]:
        """
        获取该编码建议的替身字符Unicode范围。

        CP932/SHIFT_JIS返回日文相关字符范围（假名、汉字）。
        GBK返回中文相关字符范围（汉字、标点）。

        Returns:
            Unicode码点范围列表，每项为(起始, 结束)元组
        """
        if self in (EncodingType.CP932, EncodingType.SHIFT_JIS):
            return [
                (0x3041, 0x3096),  # 平假名 (Hiragana)
                (0x30A1, 0x30FA),  # 片假名 (Katakana)
                (0x30FD, 0x30FE),  # 片假名重复标记
                (0x31F0, 0x31FF),  # 片假名语音扩展
                (0x4E00, 0x9FFF),  # CJK统一汉字
                (0x3400, 0x4DBF),  # CJK扩展A区
            ]
        else:
            return [
                (0x4E00, 0x9FFF),  # CJK统一汉字
                (0x3400, 0x4DBF),  # CJK扩展A区
                (0x2000, 0x206F),  # 通用标点
                (0x3000, 0x303F),  # CJK符号和标点
            ]

    def code_page(self) -> int:
        """
        获取该编码对应的Windows代码页标识符。

        Returns:
            932 (日文) 或 936 (简体中文)
        """
        return 932 if self in (EncodingType.CP932, EncodingType.SHIFT_JIS) else 936


class ReplacementPool:
    """
    替身字符池管理器。

    管理替身字符的分配和回收，维护原始字符到替身字符的双向映射。
    采用FIFO策略分配替身字符。
    """

    def __init__(self, encoding: EncodingType, pool_chars: list[str]) -> None:
        """
        初始化替身池。

        Args:
            encoding: 目标编码类型
            pool_chars: 可用作替身的字符列表
        """
        self.encoding: EncodingType = encoding
        self.pool: list[str] = pool_chars
        self.free: deque[str] = deque(self.pool)
        self.orig_to_repl: dict[str, str] = {}
        self.repl_to_orig: dict[str, str] = {}

    @staticmethod
    def load(data: dict[str, object]) -> "ReplacementPool":
        """从字典数据加载替身池配置。"""
        encoding = EncodingType(data["encoding"])
        pool = data["pool"]

        assert isinstance(pool, list)

        # 校验所有字符是否可被目标编码表示
        invalid = [c for c in pool if not encoding.contains_char(c)]
        if invalid:
            raise ValueError(
                f"替身池中包含目标编码 [{encoding.value}] 无法表示的字符: {invalid}"
            )

        return ReplacementPool(encoding, pool)

    @staticmethod
    def load_from_path(path: PathLike) -> "ReplacementPool":
        """从JSON文件加载替身池配置。"""
        path = to_path(path)
        if not path.exists():
            raise FileNotFoundError(f"替身池文件未找到: {path}")

        data = read_json(path)
        return ReplacementPool.load(data)

    def dump(self) -> dict[str, object]:
        """导出替身池配置为字典。"""
        return {
            "encoding": self.encoding.value,
            "pool": self.pool,
        }

    def save_to_path(self, path: PathLike) -> None:
        """将替身池配置保存为JSON文件。"""
        path = to_path(path)

        data = self.dump()
        write_json(path, data)

    def dump_mapping(self) -> dict[str, object]:
        """
        导出当前的字符映射表。
        包含代码页信息（供外部工具识别编码）和双向映射关系。
        """
        return {
            "code_page": self.encoding.code_page(),
            "mapping": self.repl_to_orig,
        }

    def save_mapping_to_path(self, path: PathLike) -> None:
        """将字符映射表保存为JSON文件。"""
        path = to_path(path)

        data = self.dump_mapping()
        write_json(path, data)

    def get(self, orig: str) -> str:
        """
        为原始字符分配一个替身字符。

        如果该原始字符已有分配的替身，直接返回。
        否则从可用池中取出一个（FIFO策略）并建立映射。
        """
        if orig in self.orig_to_repl:
            return self.orig_to_repl[orig]

        if not self.free:
            raise RuntimeError(
                f"替身池已耗尽！无法为字符 '{orig}' (U+{ord(orig):04X}) 分配新的替身。"
                + f"池大小: {len(self.pool)}"
            )

        repl = self.free.popleft()
        self.orig_to_repl[orig] = repl
        self.repl_to_orig[repl] = orig
        return repl

    def map_text(self, text: str) -> str:
        """
        对整段文本执行编码适配转换。

        遍历文本中的每个字符：
        - 如果字符可被目标编码表示，保持不变
        - 否则替换为分配的替身字符
        """
        out: list[str] = []
        for ch in text:
            if self.encoding.contains_char(ch):
                out.append(ch)
            else:
                out.append(self.get(ch))
        return "".join(out)


class ReplacementPoolBuilder:
    """
    替身池构建器。

    通过链式调用配置编码类型、排除字符、自定义范围等参数，
    最终生成ReplacementPool实例。

    Example:
        >>> pool = (ReplacementPoolBuilder()
        ...     .with_encoding(EncodingType.CP932)
        ...     .exclude_chars("あいう")
        ...     .exclude_from_path(Path("data.json"))
        ...     .build())
    """

    def __init__(self) -> None:
        self._encoding: EncodingType = EncodingType.CP932
        self._exclude_chars: set[str] = set()
        self._include_ranges: list[tuple[int, int]] | None = None

    def with_encoding(self, encoding: EncodingType) -> "ReplacementPoolBuilder":
        """设置目标编码类型。"""
        self._encoding = encoding
        return self

    def exclude_chars(
        self, chars: str | set[str] | list[str]
    ) -> "ReplacementPoolBuilder":
        """
        排除特定字符不进入替身池。

        如果传入字符串，会被拆分为单个字符处理。
        """
        self._exclude_chars.update(chars)
        return self

    def exclude_from_gal_text(
        self, gal_text: GalTextCompatible, *, exclude_raw: bool = False
    ) -> "ReplacementPoolBuilder":
        """从 GalText 内容中收集字符并排除出替身池。

        默认排除：
        - ``names`` 的 value
        - ``items`` 的 ``name``、``message``

        当 ``exclude_raw=True`` 时，额外排除：
        - ``names`` 的 key
        - ``items`` 的 ``raw_name``、``raw_message``

        Args:
            gal_text: 提供 ``names`` 与 ``items`` 数据结构的对象。
            exclude_raw: 是否额外排除原文字段字符。

        Returns:
            当前构建器实例，便于链式调用。
        """
        for raw_name, name in gal_text.names.items():
            self.exclude_chars(name)
            if exclude_raw:
                self.exclude_chars(raw_name)

        for item in gal_text.items:
            name = item.get("name")
            if isinstance(name, str):
                self.exclude_chars(name)
                if exclude_raw:
                    raw_name = ensure_str(item.get("raw_name"))
                    self.exclude_chars(raw_name)

            message = item.get("message")
            if isinstance(message, str):
                self.exclude_chars(message)
                if exclude_raw:
                    raw_message = ensure_str(item.get("raw_message"))
                    self.exclude_chars(raw_message)

        return self

    def with_custom_ranges(
        self, ranges: list[tuple[int, int]]
    ) -> "ReplacementPoolBuilder":
        """
        设置自定义Unicode范围替代默认范围。
        """
        self._include_ranges = ranges
        return self

    def build(self) -> ReplacementPool:
        """
        根据当前配置构建ReplacementPool实例。

        遍历指定Unicode范围内的所有码点，筛选出：
        1. 不被排除的字符
        2. 可被目标编码表示的字符

        字符按Unicode码点降序排列（通常生僻字在前，常用字在后），
        使得常用字优先被保留，生僻字优先作为替身使用。
        """
        search_ranges = self._include_ranges or self._encoding.suggested_ranges()

        final_pool: set[str] = set()
        for start, end in search_ranges:
            for code in range(start, end + 1):
                ch = chr(code)
                if ch not in self._exclude_chars and self._encoding.contains_char(ch):
                    final_pool.add(ch)

        # 降序排列：码点大的（通常是生僻字）在前，优先作为替身
        pool_chars = sorted(final_pool, reverse=True)
        return ReplacementPool(self._encoding, pool_chars)


class MappingMixin:
    """
    GalText 字符映射混入类。

    对 GalText 中的文本应用 ReplacementPool.map_text()
    """

    def apply_mapping(self: GalTextT, pool: ReplacementPool) -> GalTextT:
        """
        对 self.items 以及 self.names 中的所有条目应用字符映射。
        """

        for k in self.names:
            self.names[k] = pool.map_text(self.names[k])

        for item in self.items:
            # 映射 name
            name = item.get("name")
            if isinstance(name, str):
                item["name"] = pool.map_text(name)

            # 映射 message
            message = item.get("message")
            if isinstance(message, str):
                item["message"] = pool.map_text(message)

        return self

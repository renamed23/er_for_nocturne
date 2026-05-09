import os
import struct
from dataclasses import dataclass, field
from typing import Callable, Protocol, Type, cast, runtime_checkable


type StringDecoder = Callable[[bytes, int], tuple[str, int]]
type StringEncoder = Callable[[str], bytes]

type TypedValue = U8 | U16 | U32 | U64 | I8 | I16 | I32 | I64 | String | Bytes


@runtime_checkable
class BinaryType(Protocol):
    TAG: str
    STRUCT: struct.Struct | None

    def __new__(cls, value) -> TypedValue: ...


class BinaryError(Exception):
    """二进制读写基础异常。"""


class BufferUnderflowError(BinaryError):
    """读取超出缓冲区时抛出。"""


class CStringNotTerminatedError(BinaryError):
    """读取 C 字符串时找不到 NULL 终止符时抛出。"""


class InvalidTypedValueError(BinaryError):
    """类型值与声明类型不匹配时抛出。"""


class U8(int):
    TAG: str = "u8"
    STRUCT: struct.Struct | None = struct.Struct("<B")

    def __new__(cls, value: int) -> "U8":
        if not isinstance(value, int):
            raise TypeError("u8 应该是 int 类型")
        if not (0 <= value <= 0xFF):
            raise InvalidTypedValueError(f"u8 超出范围: {value}")
        return cast(U8, int.__new__(cls, value))


class U16(int):
    TAG: str = "u16"
    STRUCT: struct.Struct | None = struct.Struct("<H")

    def __new__(cls, value: int) -> "U16":
        if not isinstance(value, int):
            raise TypeError("u16 应该是 int 类型")
        if not (0 <= value <= 0xFFFF):
            raise InvalidTypedValueError(f"u16 超出范围: {value}")
        return cast(U16, int.__new__(cls, value))


class U32(int):
    TAG: str = "u32"
    STRUCT: struct.Struct | None = struct.Struct("<I")

    def __new__(cls, value: int) -> "U32":
        if not isinstance(value, int):
            raise TypeError("u32 应该是 int 类型")
        if not (0 <= value <= 0xFFFFFFFF):
            raise InvalidTypedValueError(f"u32 超出范围: {value}")
        return cast(U32, int.__new__(cls, value))


class U64(int):
    TAG: str = "u64"
    STRUCT: struct.Struct | None = struct.Struct("<Q")

    def __new__(cls, value: int) -> "U64":
        if not isinstance(value, int):
            raise TypeError("u64 应该是 int 类型")
        if not (0 <= value <= 0xFFFFFFFFFFFFFFFF):
            raise InvalidTypedValueError(f"u64 超出范围: {value}")
        return cast(U64, int.__new__(cls, value))


class I8(int):
    TAG: str = "i8"
    STRUCT: struct.Struct | None = struct.Struct("<b")

    def __new__(cls, value: int) -> "I8":
        if not isinstance(value, int):
            raise TypeError("i8 应该是 int 类型")
        if not (-0x80 <= value <= 0x7F):
            raise InvalidTypedValueError(f"i8 超出范围: {value}")
        return cast(I8, int.__new__(cls, value))


class I16(int):
    TAG: str = "i16"
    STRUCT: struct.Struct | None = struct.Struct("<h")

    def __new__(cls, value: int) -> "I16":
        if not isinstance(value, int):
            raise TypeError("i16 应该是 int 类型")
        if not (-0x8000 <= value <= 0x7FFF):
            raise InvalidTypedValueError(f"i16 超出范围: {value}")
        return cast(I16, int.__new__(cls, value))


class I32(int):
    TAG: str = "i32"
    STRUCT: struct.Struct | None = struct.Struct("<i")

    def __new__(cls, value: int) -> "I32":
        if not isinstance(value, int):
            raise TypeError("i32 应该是 int 类型")
        if not (-0x80000000 <= value <= 0x7FFFFFFF):
            raise InvalidTypedValueError(f"i32 超出范围: {value}")
        return cast(I32, int.__new__(cls, value))


class I64(int):
    TAG: str = "i64"
    STRUCT: struct.Struct | None = struct.Struct("<q")

    def __new__(cls, value: int) -> "I64":
        if not isinstance(value, int):
            raise TypeError("i64 应该是 int 类型")
        if not (-0x8000000000000000 <= value <= 0x7FFFFFFFFFFFFFFF):
            raise InvalidTypedValueError(f"i64 超出范围: {value}")
        return cast(I64, int.__new__(cls, value))


class String(str):
    TAG: str = "str"
    STRUCT: struct.Struct | None = None

    def __new__(cls, value: str) -> "String":
        if not isinstance(value, str):
            raise TypeError("String 应该是 str 类型")
        return cast(String, str.__new__(cls, value))


class Bytes(bytes):
    TAG: str = "bytes"
    STRUCT: struct.Struct | None = None

    def __new__(cls, value: bytes) -> "Bytes":
        if not isinstance(value, bytes):
            raise TypeError("Bytes 应该是 bytes 类型")
        return cast(Bytes, bytes.__new__(cls, value))


TYPE_REGISTRY: dict[str, Type[TypedValue]] = {
    U8.TAG: U8,
    U16.TAG: U16,
    U32.TAG: U32,
    U64.TAG: U64,
    I8.TAG: I8,
    I16.TAG: I16,
    I32.TAG: I32,
    I64.TAG: I64,
    Bytes.TAG: Bytes,
    String.TAG: String,
}


def decode_cstr(data: bytes, offset: int, encoding: str) -> tuple[str, int]:
    """
    读取以 NULL 结尾的 C 字符串。

    Args:
        data: 原始二进制数据。
        offset: 起始读取偏移。
        encoding: 文本解码所用编码。

    Returns:
        tuple[str, int]: 解码后的字符串与下一个读取偏移（跳过终止符）。

    Raises:
        CStringNotTerminatedError: 在 `offset` 之后未找到终止符 `0x00`。
    """
    end = data.find(0x00, offset)
    if end < 0:
        raise CStringNotTerminatedError(
            f"未找到 C 字符串结尾: offset={offset}, length={len(data)}"
        )
    return data[offset:end].decode(encoding), end + 1


def encode_cstr(text: str, encoding: str) -> bytes:
    """
    将字符串编码为以 NULL 结尾的 C 字符串字节序列。

    Args:
        text: 待编码文本。
        encoding: 文本编码。

    Returns:
        bytes: 编码结果，末尾附带 `0x00`。
    """
    return text.encode(encoding) + b"\x00"


def to_hex(value: bytes) -> str:
    """
    将字节序列转为大写十六进制字符串（空格分隔）。

    Args:
        value: 待转换字节序列。

    Returns:
        str: 形如 ``"AA BB CC"`` 的十六进制字符串。
    """
    return value.hex(" ").upper()


def retype_like(template: BinaryType, value) -> TypedValue:
    """
    根据模板值的类型，对给定值进行重新构造。

    该函数会使用 `template` 的实际类型（如 U32 / I16 / String / Bytes 等），
    尝试用 `value` 构造一个新的同类型实例。

    本质等价于：`type(template)(value)`，并对异常进行统一包装。

    Args:
        template: 用于提供目标类型的实例（仅使用其类型信息）。
        value: 待转换的原始值。

    Returns:
        TypedValue: 与 `template` 同类型的新实例。
    """
    target_type = type(template)

    try:
        return cast(TypedValue, target_type(value))
    except Exception as exc:
        raise InvalidTypedValueError(
            f"无法将值 {value!r} 转换为类型 {target_type.__name__}"
        ) from exc


def se(value: BinaryType) -> str:
    """
    将带类型信息的值序列化为文本。

    Args:
        value: 待序列化值。

    Returns:
        str: 序列化文本。
            - `Bytes` 输出为 `bytes:AA BB`；
            - `String` 直接输出原文；
            - 其他标量输出为 `tag:value`。
    """
    tag = value.TAG
    if tag == Bytes.TAG:
        return f"{tag}:{to_hex(cast(bytes, value))}"
    if tag == String.TAG:
        return str(value)
    return f"{tag}:{value}"


def de(value: str) -> TypedValue:
    """
    将 `se` 生成的文本反序列化为强类型值。

    Args:
        value: 待反序列化文本。

    Returns:
        TypedValue: 反序列化结果。
            - 不含 `:` 时返回 `String`；
            - 类型标签未知时，回退为原始 `String`；
            - 已知标签按对应类型解析。
    """
    if ":" not in value:
        return String(value)

    raw_type, raw_value = value.split(":", 1)

    cls = TYPE_REGISTRY.get(raw_type)
    if not cls:
        return String(value)
    elif cls is Bytes:
        return Bytes(bytes.fromhex(raw_value))
    elif cls is String:
        return String(raw_value)
    else:
        return cls(int(raw_value, 10))  # type: ignore


@dataclass(slots=True)
class BinaryReader:
    """高性能二进制读取器。"""

    data: bytes
    offset: int = 0
    _view: memoryview = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._view = memoryview(self.data)

    def is_eof(self) -> bool:
        """
        检查是否已到达数据末尾。

        当偏移量 >= 数据总长度时返回 True，表示下一次读取将触发 BufferUnderflowError。
        """
        return self.offset >= len(self._view)

    def seek(self, offset: int, whence: int = os.SEEK_SET) -> int:
        """
        改变当前读取位置。

        Args:
            offset: 偏移量。
            whence: 相对位置基准：
                - os.SEEK_SET (0): 从起始位置开始（默认）。
                - os.SEEK_CUR (1): 从当前位置开始。
                - os.SEEK_END (2): 从末尾位置开始。

        Returns:
            int: 移动后的绝对偏移量位置。

        Raises:
            ValueError: 如果 whence 参数无效，或计算出的偏移量为负数值。
        """
        if whence == os.SEEK_SET:
            new_offset = offset
        elif whence == os.SEEK_CUR:
            new_offset = self.offset + offset
        elif whence == os.SEEK_END:
            new_offset = len(self._view) + offset
        else:
            raise ValueError(f"无效的 whence 参数: {whence}。应为 0, 1 或 2。")

        # 核心约束：偏移量不能为负
        if new_offset < 0:
            raise ValueError(f"非法的 seek 位置: {new_offset} (不能为负数)")

        # 注意：在只读模式下，通常允许 seek 超过 len(data)，
        # 但这会导致下一次 read 时触发你定义的 _require 报错。
        # 这种设计符合 Python IO 规范，也保持了 seek 操作的 O(1) 性能。
        self.offset = new_offset
        return self.offset

    def tell(self) -> int:
        """
        获取当前读取偏移。

        Returns:
            int: 当前偏移。
        """
        return self.offset

    def fork(self, offset: int | None = None) -> "BinaryReader":
        """
        基于同一底层数据创建一个新的读取器。

        Args:
            offset: 新读取器的起始偏移。若为 ``None``，则使用当前偏移。

        Returns:
            BinaryReader: 指向同一 ``data`` 的新读取器实例。
        """
        target_offset = self.offset if offset is None else offset
        return BinaryReader(self.data, target_offset)

    def startswith(self, prefix: bytes, offset: int | None = None) -> bool:
        """
        判断指定偏移处是否以给定前缀开头。

        Args:
            prefix: 待匹配的字节前缀。
            offset: 匹配起点。若为 ``None``，使用当前偏移。

        Returns:
            bool: 是否匹配成功。
        """
        target_offset = self.offset if offset is None else offset
        return self.data.startswith(prefix, target_offset)

    def _require(self, size: int) -> None:
        if self.offset + size > len(self._view):
            raise BufferUnderflowError(
                f"读取越界: offset={self.offset}, need={size}, total={len(self._view)}"
            )

    def read_scalar[T: BinaryType](self, cls: Type[T]) -> T:
        """
        按给定标量类型读取定长值。

        Args:
            cls: 标量类型（必须定义 `STRUCT`）。

        Returns:
            T: 对应类型实例。

        Raises:
            TypeError: 传入类型不支持定长读取。
            BufferUnderflowError: 缓冲区剩余长度不足。
        """
        if not cls.STRUCT:
            raise TypeError("read方法仅支持定长标量，变长请使用 read_bytes/read_str")

        size = cls.STRUCT.size
        self._require(size)

        val = cls.STRUCT.unpack_from(self._view, self.offset)[0]
        self.offset += size
        return cast(T, cls(val))

    def read_u8(self) -> U8:
        """读取无符号 8 位整数。

        Returns:
            U8: 读取结果。

        Raises:
            BufferUnderflowError: 缓冲区剩余长度不足。
        """
        return self.read_scalar(U8)

    def read_u16(self) -> U16:
        """读取无符号 16 位整数。

        Returns:
            U16: 读取结果。

        Raises:
            BufferUnderflowError: 缓冲区剩余长度不足。
        """
        return self.read_scalar(U16)

    def read_u32(self) -> U32:
        """读取无符号 32 位整数。

        Returns:
            U32: 读取结果。

        Raises:
            BufferUnderflowError: 缓冲区剩余长度不足。
        """
        return self.read_scalar(U32)

    def read_u64(self) -> U64:
        """读取无符号 64 位整数。

        Returns:
            U64: 读取结果。

        Raises:
            BufferUnderflowError: 缓冲区剩余长度不足。
        """
        return self.read_scalar(U64)

    def read_i8(self) -> I8:
        """读取有符号 8 位整数。

        Returns:
            I8: 读取结果。

        Raises:
            BufferUnderflowError: 缓冲区剩余长度不足。
        """
        return self.read_scalar(I8)

    def read_i16(self) -> I16:
        """读取有符号 16 位整数。

        Returns:
            I16: 读取结果。

        Raises:
            BufferUnderflowError: 缓冲区剩余长度不足。
        """
        return self.read_scalar(I16)

    def read_i32(self) -> I32:
        """读取有符号 32 位整数。

        Returns:
            I32: 读取结果。

        Raises:
            BufferUnderflowError: 缓冲区剩余长度不足。
        """
        return self.read_scalar(I32)

    def read_i64(self) -> I64:
        """读取有符号 64 位整数。

        Returns:
            I64: 读取结果。

        Raises:
            BufferUnderflowError: 缓冲区剩余长度不足。
        """
        return self.read_scalar(I64)

    def read_bytes(self, length: int) -> Bytes:
        """
        读取指定长度字节。

        Args:
            length: 字节长度。

        Returns:
            Bytes: 读取结果。

        Raises:
            BufferUnderflowError: 缓冲区剩余长度不足。
        """
        self._require(length)
        start = self.offset
        self.offset += length
        return Bytes(self._view[start : start + length].tobytes())

    def read_str(
        self,
        *,
        codec: StringDecoder = lambda data, offset: decode_cstr(data, offset, "cp932"),
    ) -> String:
        """
        读取字符串。

        Args:
            codec: 自定义解码器，输入为 `(data, offset)`，输出为
                `(text, new_offset)`。

        Returns:
            String: 读取并解码后的字符串。
        """
        text, new_offset = codec(self.data, self.offset)
        self.offset = new_offset
        return String(text)


@dataclass(slots=True)
class BinaryWriter:
    """高性能二进制写入器。"""

    _buf: bytearray = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._buf = bytearray()

    def write_u8(self, value: int) -> None:
        """
        写入无符号 8 位整数。

        Args:
            value: 待写入整数。

        Returns:
            None
        """
        self._buf += U8.STRUCT.pack(value)  # type: ignore

    def write_u16(self, value: int) -> None:
        """
        写入无符号 16 位整数。

        Args:
            value: 待写入整数。

        Returns:
            None
        """
        self._buf += U16.STRUCT.pack(value)  # type: ignore

    def write_u32(self, value: int) -> None:
        """
        写入无符号 32 位整数。

        Args:
            value: 待写入整数。

        Returns:
            None
        """
        self._buf += U32.STRUCT.pack(value)  # type: ignore

    def write_u64(self, value: int) -> None:
        """
        写入无符号 64 位整数。

        Args:
            value: 待写入整数。

        Returns:
            None
        """
        self._buf += U64.STRUCT.pack(value)  # type: ignore

    def write_i8(self, value: int) -> None:
        """
        写入有符号 8 位整数。

        Args:
            value: 待写入整数。

        Returns:
            None
        """
        self._buf += I8.STRUCT.pack(value)  # type: ignore

    def write_i16(self, value: int) -> None:
        """
        写入有符号 16 位整数。

        Args:
            value: 待写入整数。

        Returns:
            None
        """
        self._buf += I16.STRUCT.pack(value)  # type: ignore

    def write_i32(self, value: int) -> None:
        """
        写入有符号 32 位整数。

        Args:
            value: 待写入整数。

        Returns:
            None
        """
        self._buf += I32.STRUCT.pack(value)  # type: ignore

    def write_i64(self, value: int) -> None:
        """
        写入有符号 64 位整数。

        Args:
            value: 待写入整数。

        Returns:
            None
        """
        self._buf += I64.STRUCT.pack(value)  # type: ignore

    def write_bytes(self, value: bytes) -> None:
        """
        写入原始字节序列。

        Args:
            value: 待写入字节序列。

        Returns:
            None

        Raises:
            InvalidTypedValueError: 传入值不是 `bytes`。
        """
        if not isinstance(value, bytes):
            raise InvalidTypedValueError("bytes 需要 bytes")
        self._buf += value

    def write_str(
        self,
        value: str,
        *,
        codec: StringEncoder = lambda value: encode_cstr(value, "cp932"),
    ) -> None:
        """写入字符串。

        Args:
            value: 待写入字符串。
            codec: 字符串编解码器。

        Returns:
            None
        """
        if not isinstance(value, str):
            raise InvalidTypedValueError("str 需要 str")
        self._buf += codec(value)

    def write(
        self,
        value: BinaryType,
        *,
        codec: StringEncoder = lambda value: encode_cstr(value, "cp932"),
    ) -> None:
        """
        按值类型自动写入。

        Args:
            value: 待写入的强类型值。
            codec: 字符串编码器，仅在 `String` 类型时使用。

        Returns:
            None

        Raises:
            TypeError: 遇到不支持的类型。
        """
        cls = type(value)

        if cls.STRUCT:
            self._buf += cls.STRUCT.pack(value)
        elif isinstance(value, Bytes):
            self._buf += value
        elif isinstance(value, String):
            self._buf += codec(value)
        else:
            raise TypeError(f"未知类型: {value}")

    def to_bytes(self) -> bytes:
        """
        导出当前缓冲区内容。

        Returns:
            bytes: 写入器中的全部字节数据。
        """
        return bytes(self._buf)

    def tell(self) -> int:
        """
        返回当前已写入的数据长度（即下一个写入位置的偏移量）。

        Returns:
            int: 当前已写入的数据长度偏移。
        """
        return len(self._buf)

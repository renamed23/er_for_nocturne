from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import TypedDict

from er.utils.binary import (
    BinaryReader,
    BinaryWriter,
    StringEncoder,
    de,
    encode_cstr,
    se,
    to_hex,
)
from er.utils.misc import ensure_str


class InstError(Exception):
    """指令解析异常。"""


class MatchFailed(InstError):
    """当前 opcode 候选匹配失败（可回溯尝试下一个候选）。"""


class EndOfParsing(InstError):
    """主动终止解析。"""


class UnknownOpcodeError(InstError):
    """遇到未知 opcode。"""


type InstArg = str


class Instruction(TypedDict):
    """单条指令的结构化表示。"""

    op: str
    offset: int
    args: list[InstArg]


type ParseContext = Instruction
type HandlerResult = InstArg | list[InstArg] | None
type HandlerCallable = Callable[[BinaryReader, ParseContext], HandlerResult]
type HandlerCallableWithArgs = Callable[..., HandlerResult]
type FixOffsetIndicesResolver = Callable[[Instruction], list[int]]


@dataclass(frozen=True, slots=True)
class ParseOptions:
    """解析配置。"""

    file_name: str = "<unknown>"
    offset: int = 0
    max_chunk_print_size: int = 18


def _normalize_parse_options(
    debug_info: ParseOptions | Mapping[str, object],
) -> ParseOptions:
    """
    将输入配置规整为 ParseOptions。

    Args:
        debug_info: `ParseOptions` 或兼容旧接口的 `Mapping`。

    Returns:
        规整后的 `ParseOptions` 对象。
    """
    if isinstance(debug_info, ParseOptions):
        return debug_info

    file_name = str(debug_info.get("file_name", "<unknown>"))
    base_offset = debug_info.get("offset", 0)
    max_chunk_print_size = debug_info.get("max_chunk_print_size", 18)
    if not isinstance(base_offset, int):
        raise TypeError(f"debug_info.offset 需要 int，实际为: {base_offset}")
    if not isinstance(max_chunk_print_size, int):
        raise TypeError(
            f"debug_info.max_chunk_print_size 需要 int，实际为: {max_chunk_print_size}"
        )

    return ParseOptions(
        file_name=file_name,
        offset=base_offset,
        max_chunk_print_size=max_chunk_print_size,
    )


def _ensure_scalar_inst_arg(value: HandlerResult, *, source: str) -> InstArg:
    """
    校验 handler 结果必须为标量字符串值。

    Args:
        value: handler 返回值。
        source: 调用来源标识，用于生成报错文案。

    Returns:
        合法的 `InstArg` 字符串。
    """
    if not isinstance(value, str):
        raise ValueError(f"{source} 只支持标量字符串结果，实际得到: {value}")
    return value


class Handler:
    def __init__(self, func: HandlerCallableWithArgs) -> None:
        self.func: HandlerCallableWithArgs = func

    def __call__(self, reader: BinaryReader, ctx: ParseContext) -> HandlerResult:
        return self.func(reader, ctx)

    def repeat(self, count: int) -> "Handler":
        """
        构造固定次数重复 handler。

        Args:
            count: 重复次数。

        Returns:
            新的重复 handler。
        """

        def wrapped_handler(reader: BinaryReader, ctx: ParseContext) -> HandlerResult:
            results: list[InstArg] = []

            for _ in range(count):
                result = _ensure_scalar_inst_arg(
                    self.func(reader, ctx), source="repeat"
                )
                results.append(result)

            return results

        return Handler(wrapped_handler)

    def repeat_var(self, var_index: int = -1) -> "Handler":
        """
        构造按上下文变量次数重复的 handler。

        Args:
            var_index: 从 `ctx["args"]` 中读取重复次数的索引。

        Returns:
            新的重复 handler。
        """

        def wrapped_handler(reader: BinaryReader, ctx: ParseContext) -> HandlerResult:
            # 从上下文中获取重复次数
            args = ctx["args"]
            if not args:
                raise ValueError("repeat_var 上下文 args 为空")

            count_value = args[var_index]
            count = de(count_value)
            if not isinstance(count, int) or count <= 0:
                raise ValueError(f"非法的 count_value: {count_value}")

            results: list[InstArg] = []

            for _ in range(count):
                result = _ensure_scalar_inst_arg(
                    self.func(reader, ctx), source="repeat_var"
                )
                results.append(result)

            return results

        return Handler(wrapped_handler)

    def args(self, *handler_args: object) -> "Handler":
        """
        构造带固定额外参数的 handler。

        Args:
            *handler_args: 固定附加参数。

        Returns:
            新的包装 handler。
        """

        def wrapped_handler(reader: BinaryReader, ctx: ParseContext) -> HandlerResult:
            return self.func(reader, ctx, *handler_args)

        return Handler(wrapped_handler)

    def verify(self, predicate: Callable[[object], bool]) -> "Handler":
        """通用校验：传入一个 lambda/函数，如果返回 False 则匹配失败并回溯"""

        def wrapped_handler(reader: BinaryReader, ctx: ParseContext) -> HandlerResult:
            res = self.func(reader, ctx)
            raw_val: object = res
            if isinstance(res, str):
                raw_val = de(res)

            if not predicate(raw_val):
                raise MatchFailed()
            return res

        return Handler(wrapped_handler)

    def eq(self, target: object) -> "Handler":
        """值匹配校验快捷方式"""
        return self.verify(lambda x: x == target)


def u8_handler(reader: BinaryReader, ctx: ParseContext) -> HandlerResult:
    _ = ctx
    return se(reader.read_u8())


def u16_handler(reader: BinaryReader, ctx: ParseContext) -> HandlerResult:
    _ = ctx
    return se(reader.read_u16())


def u32_handler(reader: BinaryReader, ctx: ParseContext) -> HandlerResult:
    _ = ctx
    return se(reader.read_u32())


def i8_handler(reader: BinaryReader, ctx: ParseContext) -> HandlerResult:
    _ = ctx
    return se(reader.read_i8())


def i16_handler(reader: BinaryReader, ctx: ParseContext) -> HandlerResult:
    _ = ctx
    return se(reader.read_i16())


def i32_handler(reader: BinaryReader, ctx: ParseContext) -> HandlerResult:
    _ = ctx
    return se(reader.read_i32())


def string_handler(reader: BinaryReader, ctx: ParseContext) -> HandlerResult:
    _ = ctx
    return se(reader.read_str())


def end_handler(reader: BinaryReader, ctx: ParseContext) -> HandlerResult:
    _ = reader, ctx
    raise EndOfParsing()


def byte_slice_handler(
    reader: BinaryReader, ctx: ParseContext, length: int
) -> HandlerResult:
    _ = ctx
    return se(reader.read_bytes(length))


u8 = Handler(u8_handler)
u16 = Handler(u16_handler)
u32 = Handler(u32_handler)
i8 = Handler(i8_handler)
i16 = Handler(i16_handler)
i32 = Handler(i32_handler)
string = Handler(string_handler)
byte_slice = Handler(byte_slice_handler)
end = Handler(end_handler)


def parse_data(
    debug_info: ParseOptions | Mapping[str, object],
    reader: BinaryReader,
    inst_map: Mapping[bytes, list[Handler] | list[list[Handler]]],
    fallback_handler: Handler | None = None,
) -> list[Instruction]:
    """
    按照声明式 `inst_map` 解析二进制流。

    Args:
        debug_info: 解析调试配置，兼容 `ParseOptions` 与旧版 dict 传参。
        reader: 二进制读取器。
        inst_map: opcode 到 handler 链（或 handler 链列表）的映射表。
        fallback_handler: 兜底处理函数，当所有 opcode 均不匹配时调用。

    Returns:
        解析后的指令列表。
    """
    options = _normalize_parse_options(debug_info)
    file_name = options.file_name
    base_offset = options.offset
    max_chunk_print_size = options.max_chunk_print_size

    insts: list[Instruction] = []

    # 按键长度降序排序
    sorted_keys = sorted(inst_map.keys(), key=len, reverse=True)

    while not reader.is_eof():
        matched = False
        start_offset = reader.tell()

        for signature in sorted_keys:
            if reader.startswith(signature, start_offset):
                raw_handlers = inst_map[signature]
                handler_chains: list[list[Handler]]
                if len(raw_handlers) > 0 and isinstance(raw_handlers[0], list):
                    handler_chains = raw_handlers  # type: ignore
                else:
                    handler_chains = [raw_handlers]  # type: ignore

                signature_len = len(signature)

                # 尝试每一个候选链 (Any 逻辑)
                for handlers in handler_chains:
                    cur_inst: Instruction = {
                        "op": to_hex(signature),
                        "offset": start_offset + base_offset,
                        "args": [],
                    }
                    param_offset = start_offset + signature_len
                    trial_reader = reader.fork(param_offset)
                    try:
                        for handler in handlers:
                            res = handler(trial_reader, cur_inst)
                            if res is not None:
                                if isinstance(res, list):
                                    cur_inst["args"].extend(res)
                                else:
                                    cur_inst["args"].append(res)

                        # 整个链条处理成功
                        param_offset = trial_reader.tell()
                        insts.append(cur_inst)
                        reader.seek(param_offset)
                        matched = True
                        break  # 跳出候选链循环
                    except MatchFailed:
                        # 当前链不匹配，尝试下一个候选链
                        continue
                    except EndOfParsing:
                        param_offset = trial_reader.tell()
                        insts.append(cur_inst)
                        reader.seek(param_offset)
                        return insts
                    except Exception as exc:
                        prev_inst = insts[-1] if insts else None
                        raise InstError(
                            f"{file_name}: 处理 Opcode {to_hex(signature)} 在 "
                            + f"{hex(start_offset + base_offset)} 发生致命错误\n"
                            + f"当前指令草稿: {cur_inst}\n"
                            + f"前一条已解析指令: {prev_inst}\n"
                            + f"原始异常: {type(exc).__name__}: {exc}"
                        ) from exc

                if matched:
                    break

        # 尝试兜底处理
        if not matched and fallback_handler:
            cur_inst = {
                "op": "",
                "offset": start_offset + base_offset,
                "args": [],
            }
            trial_reader = reader.fork(start_offset)
            try:
                res = fallback_handler(trial_reader, cur_inst)
                if res is not None:
                    if isinstance(res, list):
                        cur_inst["args"].extend(res)
                    else:
                        cur_inst["args"].append(res)

                insts.append(cur_inst)
                reader.seek(trial_reader.tell())
                matched = True
            except MatchFailed:
                pass
            except EndOfParsing:
                param_offset = trial_reader.tell()
                insts.append(cur_inst)
                reader.seek(param_offset)
                return insts
            except Exception as exc:
                prev_inst = insts[-1] if insts else None
                raise InstError(
                    f"{file_name}: fallback 处理器在 "
                    + f"{hex(start_offset + base_offset)} 发生致命错误\n"
                    + f"当前指令草稿: {cur_inst}\n"
                    + f"前一条已解析指令: {prev_inst}\n"
                    + f"原始异常: {type(exc).__name__}: {exc}"
                ) from exc

        if not matched:
            unknown_byte = reader.data[start_offset]
            chunk = reader.data[start_offset : start_offset + max_chunk_print_size]
            has_more = (len(reader.data) - start_offset) > max_chunk_print_size
            suffix = "..." if has_more else ""
            prev_inst = insts[-1] if insts else None

            # print(
            #     f"\n{'=' * 40}\n"
            #     + f"解析失败 [文件: {file_name}]\n"
            #     + f"未知 Opcode: {hex(unknown_byte)} 偏移在: {hex(start_offset + base_offset)}\n"
            #     + f"数据片段 (HEX):    {to_hex(chunk)}{suffix}\n"
            #     + f"数据片段 (ASCII): {repr(chunk)}{suffix}\n"
            #     + f"{'-' * 40}\n"
            #     + f"前一条已解析指令: {prev_inst}\n"
            #     + f"{'=' * 40}"
            # )
            raise UnknownOpcodeError(
                f"\n{'=' * 40}\n"
                + f"解析失败 [文件: {file_name}]\n"
                + f"未知 Opcode: {hex(unknown_byte)} 偏移在: {hex(start_offset + base_offset)}\n"
                + f"数据片段 (HEX):    {to_hex(chunk)}{suffix}\n"
                + f"数据片段 (ASCII): {repr(chunk)}{suffix}\n"
                + f"{'-' * 40}\n"
                + f"前一条已解析指令: {prev_inst}\n"
                + f"{'=' * 40}"
            )
            return insts

    return insts


def h(hex_str: str) -> bytes:
    """
    将十六进制字符串转换为 bytes。

    Args:
        hex_str: 例如 ``"01 FF"``。

    Returns:
        对应字节串。
    """
    return bytes.fromhex(hex_str)


def assemble_one_inst(
    entry: Instruction,
    codec: StringEncoder = lambda value: encode_cstr(value, "cp932"),
) -> bytes:
    """
    将一条反汇编后的指令 JSON 转换为二进制。

    Args:
        entry: 指令对象。
        codec: 字符串编码器。

    Returns:
        单条指令的二进制数据。
    """
    writer = BinaryWriter()

    # 1. opcode
    # "00 03" -> bytes
    op_bytes = bytes.fromhex(ensure_str(entry["op"]))
    writer.write_bytes(op_bytes)

    # 2. 参数顺序拼接
    args = entry.get("args", [])

    for item in args:
        writer.write(de(item), codec=codec)

    return writer.to_bytes()


def fix_offset(
    file: str,
    insts: list[Instruction],
    old2new: Mapping[int, int],
    fix_inst_map: Mapping[str, list[int] | FixOffsetIndicesResolver],
) -> list[Instruction]:
    """
    修复指令中的偏移，将旧偏移映射为新偏移。

    Args:
        file: 当前处理文件名。
        insts: 指令列表。
        old2new: 旧偏移到新偏移的映射。
        fix_inst_map: 需要修复的指令的参数索引（或索引解析器）。

    Returns:
        修复后的指令列表（原地修改并返回）。
    """
    for inst in insts:
        key = ensure_str(inst["op"])
        if key not in fix_inst_map:
            continue

        indices_spec = fix_inst_map[key]

        # 支持列表或回调函数
        if callable(indices_spec):
            indices = indices_spec(inst)
        else:
            indices = indices_spec

        args = inst.get("args")

        for i in indices:
            raw_value = args[i]

            old_offset = de(raw_value)
            if not isinstance(old_offset, int):
                raise TypeError(f"偏移字段不是整型: {raw_value}")

            if old_offset not in old2new:
                raise ValueError(f"{file}, {inst} 指向不存在的 offset: {old_offset}")

            new_offset = old2new[old_offset]
            args[i] = se(type(old_offset)(new_offset))

    return insts

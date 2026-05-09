from er.utils.console import console
from er.utils.instructions import (
    Handler,
    HandlerResult,
    Instruction,
    ParseContext,
    assemble_one_inst,
    fix_offset,
    h,
    parse_data,
    string,
    u8,
    u16,
)
from er.utils.binary import BinaryReader
from er.utils.fs import PathLike, collect_files, to_path
from er.utils.misc import read_json, write_json


def string_array_until_empty_handler(
    reader: BinaryReader, ctx: ParseContext
) -> HandlerResult:
    _ = ctx
    results = []
    while True:
        s = reader.read_str()
        results.append(s)
        if s == "":
            break
    return results


string_array_until_empty = Handler(string_array_until_empty_handler)

FIX_INST_MAP = {
    "10": [0],
    "11": [5],
}

INST_MAP = {
    h("08"): [u16, u16],
    # [偏移] 第一个u16
    h("10"): [u16],
    # [偏移] 最后一个u16
    h("11"): [u8, u16, u8.eq(0x15), u16, u16, u16],
    # [文本]
    h("15"): [string],
    # [选项]
    h("17 02 00"): [string_array_until_empty],
    h("18"): [string],
    h("20"): [u8],
    h("21"): [],
    h("2B 00 00"): [u8],
    h("2C"): [u16],
    h("33"): [],
    h("35"): [],
    h("36"): [],
    h("46"): [u16],
    h("4C 00"): [],
    h("50 07"): [],
    h("54"): [u8, string],
    h("55"): [u8, string],
    h("5B"): [u8, string],
    h("5C"): [],
    h("6B"): [u8],
    h("7B"): [u8, u8],
    h("87 12"): [],
    h("88"): [],
    h("FF"): [],
    h("34 35 39 53 02"): [],
}


def decompile(input_path: PathLike, output_path: PathLike) -> None:
    """反编译：将二进制文件转换为JSON"""
    input_root = to_path(input_path)
    output_root = to_path(output_path)
    files = collect_files(input_root)

    for file in files:
        reader = BinaryReader(file.read_bytes())

        insts = parse_data(
            {
                "file_name": str(file),
                "offset": 0,
            },
            reader,
            INST_MAP,
        )

        assert reader.is_eof()

        # 保存为JSON
        rel_path = file.relative_to(input_root)
        out_file = output_root / f"{rel_path.as_posix()}.json"
        out_file.parent.mkdir(parents=True, exist_ok=True)

        write_json(out_file, insts)

    console.print(f"[OK] decompile 完成: {input_path} -> {output_path}", style="info")


def compile(input_path: PathLike, output_path: PathLike) -> None:
    """编译：将JSON转换回二进制文件"""
    input_root = to_path(input_path)
    output_root = to_path(output_path)
    files = collect_files(input_root, "json")

    for file in files:
        insts: list[Instruction] = read_json(file)

        # ========= 第一步：assemble instruction，计算新 offset =========
        old2new = {}  # old_offset -> new_offset
        cursor = 0

        for inst in insts:
            old_offset = inst["offset"]
            b = assemble_one_inst(inst)

            old2new[old_offset] = cursor
            cursor += len(b)

        # ========= 第二步：修复指令的偏移 =========
        insts = fix_offset(str(file), insts, old2new, FIX_INST_MAP)

        # ========= 第三步：assemble 修复过偏移的指令 =========
        new_blob = b"".join([assemble_one_inst(inst) for inst in insts])
        new_blob_len = len(new_blob)
        if new_blob_len > 0xFA00:
            raise ValueError(
                f"文件 {file} 的长度 ({new_blob_len}) 超出了游戏的物理限制 0xFA00"
            )

        # 保存二进制文件
        rel_path = file.relative_to(input_root)
        out_file = output_root / rel_path.with_suffix("")
        out_file.parent.mkdir(parents=True, exist_ok=True)

        out_file.write_bytes(new_blob)

    console.print(f"[OK] compile 完成: {input_path} -> {output_path}", style="info")

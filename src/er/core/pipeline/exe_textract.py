import os
from typing import cast

from er.core.gal_json import GalJson
from er.utils.binary import BinaryReader
from er.utils.console import console
from er.utils.fs import PathLike, to_path
from er.utils.misc import ensure_str


def should_ignore(s: str) -> bool:
    if s is None:
        return True
    if s == "":
        return True
    if s.isascii():
        return True

    if len(s) == 1:
        return True

    # 检查Unicode私有区域字符和半角日语字符
    for char in s:
        code_point = ord(char)
        # 私有使用区: U+E000 - U+F8FF
        if 0xE000 <= code_point <= 0xF8FF:
            return True
        # 补充私有使用区-A: U+F0000 - U+FFFFF
        if 0xF0000 <= code_point <= 0xFFFFF:
            return True
        # 补充私有使用区-B: U+100000 - U+10FFFF
        if 0x100000 <= code_point <= 0x10FFFF:
            return True
        # 半角日语字符(标点+片假名): U+FF61 - U+FF9F
        if 0xFF61 <= code_point <= 0xFF9F:
            return True

        # 控制字符: C0 (0-31, 127) 和 C1 (128-159)
        if code_point < 32 and char not in ("\n", "\r", "\t"):
            return True
        if code_point == 127 or (128 <= code_point <= 159):
            return True
    return False


def get_blocks(bin: bytes) -> list[dict]:
    blocks = []
    reader = BinaryReader(bin)
    while not reader.is_eof():
        try:
            trial_reader = reader.fork()
            s = trial_reader.read_str()
            if should_ignore(s):
                reader.seek(1, os.SEEK_CUR)
                continue
            blocks.append({
                "message": s,
                "offset": reader.tell(),
                "len": trial_reader.tell() - reader.tell(),
                "keep_len": True,
            })
            reader.seek(trial_reader.tell())
        except Exception as _:
            reader.seek(1, os.SEEK_CUR)
            pass

    return blocks


def extract(input_exe: PathLike, gal_json: GalJson) -> None:
    """
    提取目录下脚本文本到容器中。

    Args:
        input_exe: 目标exe路径。
        gal_json: 原文容器。

    Returns:
        None
    """
    source = to_path(input_exe)

    for block in get_blocks(source.read_bytes()):
        if should_ignore(block["message"]):
            continue
        gal_json.add_item(block)

    console.print(
        f"[OK] 文本提取完成: {source} , {gal_json.total_count()} items)",
        style="info",
    )


def apply(input_exe: PathLike, gal_json: GalJson, output_exe: PathLike) -> None:
    """
    将 GalJson 中的译文应用到原始脚本，新文件输出到新目录中

    Args:
        input_exe: 原始exe路径。
        gal_json: 译文容器。
        output_exe: 替换后exe输出目录。

    Returns:
        None
    """

    source = to_path(input_exe)
    output = to_path(output_exe)
    gal_json.reset_cursor()

    raw_data = source.read_bytes()
    data = bytearray(raw_data)

    while not gal_json.is_ran_out():
        item = gal_json.pop_next_item()
        translation = ensure_str(item["message"])
        original_len = cast(int, item["len"])
        offset = cast(int, item["offset"])
        assert item["keep_len"] is True

        new_bytes = translation.encode("cp932")
        new_len = len(new_bytes)

        if new_len > original_len:
            raise ValueError(
                f"译文字节长度 ({new_len}) 超过原始空间 ({original_len})！\n"
                f"偏移位置: 0x{offset:X}\n"
                f"文本内容: {item['raw_message']} => {translation}"
            )

        padding = b"\x00" * (original_len - new_len)
        data[offset : offset + original_len] = new_bytes + padding

    assert gal_json.is_ran_out()

    # 3. 写出最终结果
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(data)

    console.print(
        f"[OK] 文本替换完成: {source} -> {output} (共替换 {gal_json.consumed_count()} 处)",
        style="info",
    )

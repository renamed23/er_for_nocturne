from pathlib import Path
import re

from er.core.gal_json import GalJson
from er.utils.console import console
from er.utils.fs import PathLike, collect_files, to_path
from er.utils.instructions import Instruction
from er.utils.misc import ensure_str, read_json, write_json


def _extract_from_script(
    script_path: Path,
    gal_json: GalJson,
) -> None:
    """
    从单个脚本中提取可翻译条目。

    Args:
        script_path: 输入脚本路径。
        gal_json: 原文容器。

    Returns:
        None
    """
    insts: list[Instruction] = read_json(script_path)

    for index, inst in enumerate(insts):
        op = ensure_str(inst.get("op"))
        args = inst["args"]

        match op:
            case "17 02 00":
                for arg in args[:-1]:
                    message = ensure_str(arg)
                    item = {"message": message, "is_select": True}
                    gal_json.add_item(item)

            case "15":
                raw_text = ensure_str(args[0])
                # 1. 按照 \u0001 进行切割，并过滤掉空字符串
                parts = [p for p in raw_text.split("\u0001")]

                for i, part in enumerate(parts):
                    # 2. 提取开头和结尾的控制字符 (ASCII 0x00-0x1F)
                    # prefix: 匹配开头的控制字符
                    # message: 核心文本
                    # suffix: 匹配结尾的控制字符
                    match = re.match(
                        r"^([\x00-\x1f]*)(.*?)([\x00-\x1f]*)$", part, re.DOTALL
                    )
                    assert match

                    prefix, text, suffix = match.groups()
                    assert text is not None

                    item: dict = {
                        "prefix": prefix,
                        "message": text,
                        "suffix": suffix,
                    }

                    # 3. 标记子句（除了最后一句）
                    if i != len(parts) - 1:
                        item["sub_parts"] = True

                    # 4. 尝试提取 {name}「{message}」结构
                    name_match = re.match(r"^(.*?)(「.*?」)$", text, re.DOTALL)
                    if name_match and name_match.group(1):
                        item["name"] = name_match.group(1)
                        item["message"] = name_match.group(2)

                    gal_json.add_item(item)

            case _:
                continue


def _apply_translation_to_script(
    script_path: Path,
    gal_json: GalJson,
    output_root: Path,
    base_root: Path,
) -> None:
    """
    将译文应用到单个脚本。

    Args:
        script_path: 输入脚本路径。
        gal_json: 译文数据容器。
        output_root: 输出目录。
        base_root: 输入根目录，用于计算相对路径。

    Returns:
        None
    """
    insts: list[Instruction] = read_json(script_path)

    for index, inst in enumerate(insts):
        op = ensure_str(inst.get("op"))
        args = inst["args"]

        match op:
            case "17 02 00":
                for i in range(len(args) - 1):
                    item = gal_json.pop_next_item()
                    args[i] = ensure_str(item.get("message"))

            case "15":
                collected_parts = []
                while True:
                    item: dict = gal_json.pop_next_item()
                    translated_msg = ensure_str(item.get("message"))

                    # 还原角色名
                    if "name" in item:
                        translated_msg = f"{item['name']}{translated_msg}"

                    # 还原控制字符
                    full_part = f"{ensure_str(item.get('prefix'))}{translated_msg}{ensure_str(item.get('suffix'))}"
                    collected_parts.append(full_part)

                    # 检查是否是该指令的最后一个子句
                    if not item.get("sub_parts"):
                        break

                # 重新拼合回指令参数
                args[0] = "\u0001".join(collected_parts)

            case _:
                continue

    output_path = output_root / script_path.relative_to(base_root)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    write_json(output_path, insts)


def extract(input_dir: PathLike, gal_json: GalJson) -> None:
    """
    提取目录下脚本文本到容器中。

    Args:
        input_dir: 反汇编后的脚本目录（json）。
        gal_json: 原文容器。

    Returns:
        None
    """
    source_root = to_path(input_dir)
    files = collect_files(source_root, "json")

    for file in files:
        _extract_from_script(file, gal_json)

    console.print(
        f"[OK] 文本提取完成: {source_root} ({len(files)} files, {gal_json.total_count()} items)",
        style="info",
    )


def apply(input_dir: PathLike, gal_json: GalJson, output_dir: PathLike) -> None:
    """
    将 GalJson 中的译文应用到原始脚本，新文件输出到新目录中

    Args:
        input_dir: 原始脚本目录（json）。
        gal_json: 译文容器。
        output_dir: 替换后脚本输出目录。

    Returns:
        None
    """
    source_root = to_path(input_dir)
    output_root = to_path(output_dir)

    files = collect_files(source_root, "json")
    gal_json.reset_cursor()

    for file in files:
        _apply_translation_to_script(
            script_path=file,
            gal_json=gal_json,
            output_root=output_root,
            base_root=source_root,
        )

    if not gal_json.is_ran_out():
        raise ValueError(
            "替换完成但仍有未消费译文条目："
            f"remaining={gal_json.remaining_count()}, consumed={gal_json.consumed_count()}, "
            f"total={gal_json.total_count()}"
        )

    console.print(
        f"[OK] 文本替换完成: {source_root} -> {output_root} ({len(files)} files)",
        style="info",
    )

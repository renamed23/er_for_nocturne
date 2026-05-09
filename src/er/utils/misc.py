import json
from typing import Any

from er.utils.console import console
from er.utils.fs import PathLike, collect_files, to_path


def str_or_none(val: object, context: str = "") -> str | None:
    """确保val为str或None，否则抛出TypeError异常"""
    if isinstance(val, (str, type(None))):
        return val
    msg = f"预期 str/None，但收到了  {type(val).__name__}"
    if context:
        msg += f" (上下文: {context})"
    raise TypeError(msg)


def ensure_str(val: object, context: str = "") -> str:
    """确保val为str，否则抛出TypeError异常"""
    if not isinstance(val, str):
        msg = f"期待 str，但收到了 {type(val).__name__}"
        if context:
            msg += f" (上下文: {context})"
        raise TypeError(msg)
    return val


def write_json(
    path: PathLike,
    value: object,
    *,
    create_dir: bool = True,
    ensure_ascii: bool = False,
    indent: int | None = 2,
    encoding: str = "utf-8",
):
    """
    将 Python 对象序列化为 JSON 并写入文件。（如果路径没有目录，默认会创建）

    默认配置针对人类可读性优化：使用 UTF-8 编码支持非 ASCII 字符（如中文），
    并启用缩进格式化。

    Args:
        path: 目标文件路径，支持字符串或 Path 对象
        value: 要序列化的 Python 对象，需为 JSON 可序列化类型
    """
    path = to_path(path)
    if create_dir:
        path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding=encoding) as f:
        json.dump(value, f, ensure_ascii=ensure_ascii, indent=indent)


def read_json(path: PathLike, encoding: str = "utf-8") -> Any:
    """
    从文件读取并解析 JSON 内容。

    返回解析后的原始 Python 对象（dict/list 等）。

    Args:
        path: JSON 文件路径，支持字符串或 Path 对象

    Returns:
        解析后的 Python 对象。
    """
    path = to_path(path)
    with path.open("r", encoding=encoding) as f:
        return json.load(f)


def ensure_patch_length_consistent(
    raw_patch_dir: PathLike, translated_patch_dir: PathLike
) -> None:
    """
    检查原始文件与翻译后文件的字节大小（Byte size）是否完全一致。

    Args:
        raw_patch_dir: 原始 Patch 目录。
        translated_patch_dir: 翻译后的 Patch 目录。
    """
    raw_root = to_path(raw_patch_dir)
    trans_root = to_path(translated_patch_dir)

    if not raw_root.is_dir():
        raise NotADirectoryError(f"源目录无效: {raw_root}")
    if not trans_root.is_dir():
        raise NotADirectoryError(f"目标目录无效: {trans_root}")

    # 递归获取所有文件
    raw_files = collect_files(raw_root)
    errors: list[str] = []

    for raw_path in raw_files:
        rel_path = raw_path.relative_to(raw_root)
        trans_path = trans_root / rel_path

        if not trans_path.exists():
            errors.append(f"[缺失] 目标路径找不到文件: {rel_path}")
            continue

        # 获取字节大小
        raw_size = raw_path.stat().st_size
        trans_size = trans_path.stat().st_size

        if raw_size != trans_size:
            errors.append(
                f"[长度不一致] 文件: {rel_path}, "
                + f"原始大小: {raw_size} 字节, 翻译大小: {trans_size} 字节"
            )

    if errors:
        error_msg = "\n".join(errors)
        console.print(f"字节对齐校验失败:\n{error_msg}", style="error")
        raise RuntimeError(f"Patch 长度校验未通过，发现 {len(errors)} 处不一致。")

    console.print(f"字节校验通过: 共检查 {len(raw_files)} 个文件", style="info")


def is_cp932_lead_byte(b: int) -> bool:
    """
    确认输入的整数是否落在 CP932 双字节序列的高位字节（首字节）范围内。

    范围：
    - 0x81 <= b <= 0x9F
    - 0xE0 <= b <= 0xFC
    """
    return (0x81 <= b <= 0x9F) or (0xE0 <= b <= 0xFC)

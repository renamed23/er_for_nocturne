import os
import shutil
from pathlib import Path

from natsort import natsorted

from er.utils.console import console

type PathLike = str | os.PathLike[str]


def to_path(path: PathLike) -> Path:
    """将输入路径统一转换为 ``Path`` 对象。

    Args:
        path: 字符串路径或 ``Path`` 对象。

    Returns:
        规范化后的 ``Path`` 对象。
    """
    return path if isinstance(path, Path) else Path(path)


def _normalize_suffix(suffix: str) -> str:
    """标准化后缀名，确保以 ``.`` 开头。

    Args:
        suffix: 原始后缀名（可带或不带 ``.``）。

    Returns:
        标准化后的后缀名。

    Raises:
        ValueError: 传入空字符串时抛出。
    """
    if not suffix:
        raise ValueError("后缀名不能为空字符串")
    return suffix if suffix.startswith(".") else f".{suffix}"


def _remove_existing_target(path: Path) -> None:
    """删除已存在目标路径（文件/软链接/目录）。

    Args:
        path: 需要删除的目标路径。

    Returns:
        None

    Raises:
        ValueError: 路径存在但类型未知时抛出。
    """
    if path.is_file() or path.is_symlink():
        path.unlink()
        return
    if path.is_dir():
        shutil.rmtree(path)
        return
    raise ValueError(f"无法删除未知路径类型: {path}")


def rename_path(
    original_path: PathLike, new_name: str, overwrite: bool = False
) -> Path:
    """将路径重命名为同目录下的新名称。

    Args:
        original_path: 原路径（文件或目录）。
        new_name: 新名称（仅名称，不含父目录）。
        overwrite: 当目标已存在时是否覆盖。

    Returns:
        重命名后的目标路径。
    """
    source = to_path(original_path)
    if not source.exists():
        raise FileNotFoundError(f"源路径不存在: {source}")

    target = source.with_name(new_name)
    if target.exists():
        if not overwrite:
            raise FileExistsError(f"目标路径已存在: {target}")
        _remove_existing_target(target)
        console.print(f"已删除已存在路径: {target}", style="warn")

    source.rename(target)
    console.print(f"重命名成功: {source} -> {target}", style="info")
    return target


def rename_extensions_in_dir(
    directory: PathLike,
    old_extension: str,
    new_extension: str,
    overwrite: bool = False,
) -> tuple[int, int]:
    """在指定目录（非递归）批量重命名文件扩展名。

    Args:
        directory: 目标目录路径。
        old_extension: 旧后缀（如 ``txt`` 或 ``.txt``）。
        new_extension: 新后缀（如 ``json`` 或 ``.json``）。
        overwrite: 目标已存在时是否覆盖。

    Returns:
        一个二元组 ``(success_count, fail_count)``。

    Raises:
        FileNotFoundError: 目录不存在时抛出。
        NotADirectoryError: 目标不是目录时抛出。
        Exception: 遇到非预期错误时向上抛出。
    """
    root = to_path(directory)
    if not root.exists():
        raise FileNotFoundError(f"目录不存在: {root}")
    if not root.is_dir():
        raise NotADirectoryError(f"路径不是目录: {root}")

    old_ext = _normalize_suffix(old_extension).lower()
    new_ext = _normalize_suffix(new_extension)

    candidates = [
        item
        for item in root.iterdir()
        if item.is_file() and item.suffix.lower() == old_ext
    ]
    if not candidates:
        console.print(f"目录 {root} 中没有后缀为 {old_ext} 的文件", style="warn")
        return 0, 0

    success_count = 0
    fail_count = 0
    for source in natsorted(candidates, key=lambda p: p.name):
        target = source.with_suffix(new_ext)
        if source == target:
            console.print(f"跳过（目标不变）: {source.name}", style="warn")
            continue

        if target.exists() and not overwrite:
            fail_count += 1
            console.print(
                f"重命名失败（目标已存在）: {source} -> {target}", style="error"
            )
            continue

        rename_path(source, target.name, overwrite=overwrite)
        success_count += 1

    console.print(
        f"扩展名重命名完成: 成功 {success_count}，失败 {fail_count}",
        style="info",
    )
    return success_count, fail_count


def copy_entry(
    source: PathLike, destination: PathLike, overwrite: bool = False
) -> Path:
    """复制文件或目录到目标位置。

    Args:
        source: 源文件或目录路径
        destination: 目标路径
        overwrite: 如果为True，则覆盖已存在的文件/目录；如果为False，则报错

    Returns:
        最终复制到的目标路径。
    """
    source_path = to_path(source)
    dest_path = to_path(destination)

    if not source_path.exists():
        raise FileNotFoundError(f"源路径不存在: {source_path}")

    if source_path.is_file() and dest_path.exists() and dest_path.is_dir():
        dest_path = dest_path / source_path.name

    if dest_path.exists():
        if not overwrite:
            raise FileExistsError(f"目标路径已存在（overwrite=False）: {dest_path}")
        _remove_existing_target(dest_path)
        console.print(f"已删除已存在目标: {dest_path}", style="warn")

    dest_path.parent.mkdir(parents=True, exist_ok=True)

    if source_path.is_file():
        shutil.copy2(source_path, dest_path)
        console.print(f"文件复制成功: {source_path} -> {dest_path}", style="info")
        return dest_path

    if source_path.is_dir():
        shutil.copytree(source_path, dest_path)
        console.print(f"目录复制成功: {source_path} -> {dest_path}", style="info")
        return dest_path

    raise ValueError(f"源路径既不是文件也不是目录: {source_path}")


def merge_dir(source: PathLike, destination: PathLike, overwrite: bool = False) -> None:
    """将源目录内容递归合并到目标目录。

    Args:
        source: 源目录路径
        destination: 目标目录路径
        overwrite: 如果为True，则覆盖已存在的文件；如果为False，则跳过已存在的文件

    Returns:
        None
    """
    source_path = to_path(source)
    dest_path = to_path(destination)

    if not source_path.exists():
        raise FileNotFoundError(f"源目录不存在: {source_path}")
    if not source_path.is_dir():
        raise NotADirectoryError(f"源路径不是目录: {source_path}")

    dest_path.parent.mkdir(parents=True, exist_ok=True)
    if not dest_path.exists():
        shutil.copytree(source_path, dest_path)
        console.print(
            f"目标不存在，已整体复制: {source_path} -> {dest_path}", style="info"
        )
        return
    if not dest_path.is_dir():
        raise NotADirectoryError(f"目标路径不是目录: {dest_path}")

    for item in source_path.iterdir():
        dest_item = dest_path / item.name
        if item.is_dir():
            if not dest_item.exists():
                shutil.copytree(item, dest_item)
                console.print(f"复制目录: {item} -> {dest_item}", style="info")
                continue

            if dest_item.is_dir():
                merge_dir(item, dest_item, overwrite=overwrite)
                continue

            if overwrite:
                _remove_existing_target(dest_item)
                shutil.copytree(item, dest_item)
                console.print(
                    f"覆盖非目录目标并复制目录: {item} -> {dest_item}", style="warn"
                )
            else:
                console.print(
                    f"跳过（同名非目录目标已存在）: {dest_item}", style="warn"
                )
            continue

        if item.is_file():
            if dest_item.exists() and not overwrite:
                console.print(f"跳过已存在文件: {dest_item}", style="warn")
                continue

            if dest_item.exists() and overwrite:
                _remove_existing_target(dest_item)
                console.print(f"覆盖目标: {dest_item}", style="warn")

            shutil.copy2(item, dest_item)
            console.print(f"复制文件: {item} -> {dest_item}", style="info")


def collect_files(path: PathLike, suffix: str | None = None) -> list[Path]:
    """递归收集目录下文件，并按相对路径自然排序。

    Args:
        path: 根目录路径。
        suffix: 可选后缀过滤（如 ``.txt`` 或 ``txt``）。

    Returns:
        按相对路径自然排序后的文件路径列表。

    Raises:
        NotADirectoryError: 输入路径不是目录时抛出。
    """
    root = to_path(path)
    if not root.is_dir():
        raise NotADirectoryError(f"不是有效目录: {root}")

    normalized_suffix = (
        _normalize_suffix(suffix).lower() if suffix is not None else None
    )
    files = [
        p
        for p in root.rglob("*")
        if p.is_file()
        and (normalized_suffix is None or p.suffix.lower() == normalized_suffix)
    ]
    return natsorted(files, key=lambda p: p.relative_to(root).as_posix())

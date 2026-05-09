import os
import shutil
import subprocess
from pathlib import Path
from typing import Literal

from er.utils.console import console
from er.utils.fs import PathLike, copy_entry, merge_dir, rename_path, to_path


class TextHookBuilder:
    """text-hook 构建流程封装。"""

    def __init__(self, project_path: PathLike) -> None:
        """初始化 TextHookBuilder。

        Args:
            project_path: 项目目录路径。

        Returns:
            None
        """
        self.project_path: Path = to_path(project_path)
        self.current_dir: Path = Path.cwd()
        self.assets_dir: Path = self.project_path / "crates" / "text-hook" / "assets"
        self.generated_dir: Path = self.current_dir / "workspace" / "generated"
        self.dist_dir: Path = self.current_dir / "workspace" / "generated" / "dist"

    def _run_command(
        self,
        command: list[str],
        *,
        env: dict[str, str] | None = None,
    ) -> None:
        """在项目根目录执行命令并在失败时抛异常。

        Args:
            command: 待执行命令参数列表。
            env: 可选环境变量字典。为 ``None`` 时继承当前环境。

        Returns:
            None
        """
        console.print(
            f"执行命令: {' '.join(command)} (cwd={self.project_path})",
            style="info",
        )
        try:
            subprocess.run(command, cwd=self.project_path, env=env, check=True)
        except subprocess.CalledProcessError as e:
            console.print(
                f"命令执行失败 (退出码: {e.returncode}): {' '.join(command)}",
                style="error",
            )
            raise SystemExit(e.returncode)

    def copy_assets_for_build(self) -> None:
        """复制构建所需的资源文件。

        Returns:
            None
        """
        self.assets_dir.mkdir(parents=True, exist_ok=True)

        assets_dist = self.assets_dir / "dist"
        if assets_dist.exists():
            shutil.rmtree(assets_dist)
            console.print(f"已删除 assets 中的 dist 目录: {assets_dist}", style="warn")

        asset_dirs = [
            "hijacked",
            "x64dbg_1337_patch",
        ]
        for dir_name in asset_dirs:
            current_dir = self.current_dir / "assets" / dir_name
            target_dir = self.assets_dir / dir_name

            if current_dir.exists() and any(current_dir.iterdir()):
                console.print(
                    f"检测到非空的 {dir_name} 目录: {current_dir}",
                    style="info",
                )

                if target_dir.exists():
                    shutil.rmtree(target_dir)
                    console.print(
                        f"已删除目标 {dir_name} 目录: {target_dir}",
                        style="warn",
                    )

                copy_entry(current_dir, target_dir, overwrite=True)
            else:
                console.print(
                    f"{dir_name} 目录不存在或为空: {current_dir}", style="warn"
                )

        generated_dirs = [
            "font",
            "raw_patch",
            "translated_patch",
            "raw_text",
            "translated_text",
            "resource_pack",
            "misc",
            "exe",
        ]
        for dir_name in generated_dirs:
            current_dir = self.generated_dir / dir_name
            target_dir = self.assets_dir / dir_name

            if target_dir.exists():
                shutil.rmtree(target_dir)
                console.print(f"已删除: {target_dir}", style="warn")

            if current_dir.exists():
                copy_entry(current_dir, target_dir, overwrite=True)
            else:
                console.print(
                    f"源 {dir_name} 目录不存在: {current_dir}，忽略", style="warn"
                )

        config_files = [
            "mapping.json",
            "config.json",
            "hook_lists.json",
            "sjis_ext.bin",
        ]
        for filename in config_files:
            src_file = self.generated_dir / filename
            if src_file.exists():
                console.print(f"复制 {filename}", style="info")
                copy_entry(src_file, self.assets_dir, overwrite=True)

    def build_dll(
        self,
        features: list[str],
        arch: Literal["x86", "x64"] = "x86",
        panic: Literal["unwind", "abort", "immediate-abort"] = "unwind",
        clean: bool = False,
        output_name: str | None = None,
    ) -> None:
        """构建 DLL 文件。

        Args:
            features: cargo build 的 features 参数。
            arch: 目标架构，支持 ``x86`` 或 ``x64``。
            panic: panic 策略。
            clean: 是否在构建前执行 ``cargo clean``。
            output_name: 可选的输出 DLL 文件名；为 ``None`` 时按现有规则自动决定。

        Returns:
            None
        """
        match arch:
            case "x86":
                alias = "build-text-hook"
                source_dll_rel = to_path(
                    "target/i686-pc-windows-msvc/release/text_hook.dll"
                )
            case "x64":
                alias = "build-text-hook64"
                source_dll_rel = to_path(
                    "target/x86_64-pc-windows-msvc/release/text_hook.dll"
                )

        self.dist_dir.mkdir(parents=True, exist_ok=True)

        features_joined = ",".join(features)
        if panic == "immediate-abort":
            build_command = [
                "cargo",
                "+nightly",
                alias,
                "--features",
                features_joined,
                "-Z",
                "build-std",
            ]
            rustflags = "-C panic=immediate-abort -Z unstable-options"
            console.print(
                "使用 Nightly 工具链编译 (immediate-abort 模式)", style="info"
            )
        else:
            build_command = ["cargo", alias, "--features", features_joined]
            rustflags = f"-C panic={panic}"

        console.print(
            f"在项目根目录 {self.project_path} 中执行构建命令: {' '.join(build_command)}",
            style="info",
        )
        console.print(f"目标架构: {arch}, 使用 panic 策略: {panic}", style="info")

        build_env = os.environ.copy()
        build_env["RUSTFLAGS"] = (
            f"{os.environ.get('RUSTFLAGS', '')} {rustflags}".strip()
        )

        if clean:
            console.print(
                "执行 cargo clean 以确保所有依赖按新策略重新编译...",
                style="warn",
            )
            self._run_command(["cargo", "clean"])

        self._run_command(build_command, env=build_env)

        source_dll = self.project_path / source_dll_rel
        if not source_dll.exists():
            raise FileNotFoundError(f"找不到生成的 DLL 文件: {source_dll}")

        dest_dll = self.dist_dir / "text_hook.dll"
        copy_entry(source_dll, dest_dll, overwrite=True)

        final_dll = dest_dll
        if output_name is not None:
            console.print(f"使用显式指定的 DLL 名称: {output_name}", style="info")
            final_dll = rename_path(dest_dll, output_name, overwrite=True)
        else:
            hijacked_dir = self.current_dir / "assets" / "hijacked"
            if hijacked_dir.exists() and any(hijacked_dir.iterdir()):
                console.print(
                    f"检测到非空的 hijacked 目录: {hijacked_dir}", style="info"
                )
                hijacked_files = list(hijacked_dir.iterdir())

                if len(hijacked_files) == 1:
                    new_dll_name = hijacked_files[0].name
                    console.print(
                        f"根据 hijacked 自动将 DLL 重命名为: {new_dll_name}",
                        style="info",
                    )
                    final_dll = rename_path(dest_dll, new_dll_name, overwrite=True)
                else:
                    console.print(
                        (
                            "警告: hijacked 目录包含 "
                            f"{len(hijacked_files)} 个文件，但预期只有1个文件"
                        ),
                        style="warn",
                    )
                    console.print("跳过 DLL 重命名", style="warn")
            else:
                console.print(
                    f"hijacked 目录不存在或为空: {hijacked_dir}", style="warn"
                )

        assets_dist = self.assets_dir / "dist"
        if assets_dist.exists():
            console.print(
                f"检测到 assets 中的 dist 目录，合并到: {self.dist_dir}",
                style="info",
            )
            merge_dir(assets_dist, self.dist_dir, overwrite=True)
            console.print("合并完成", style="info")

        console.print(f"DLL 构建并复制成功: {final_dll}", style="info")

    def build(
        self,
        features: list[str],
        arch: Literal["x86", "x64"] = "x86",
        panic: Literal["unwind", "abort", "immediate-abort"] = "unwind",
        clean: bool = False,
        output_name: str | None = None,
    ) -> None:
        """执行完整构建流程。

        Args:
            features: cargo build 的 features 参数。
            arch: 目标架构，支持 ``x86`` 或 ``x64``。
            panic: panic 策略。
            clean: 是否在构建前执行 ``cargo clean``。
            output_name: 可选的输出 DLL 文件名；为 ``None`` 时按现有规则自动决定。

        Returns:
            None
        """
        console.print(f"开始构建流程 ({arch})...", style="info")
        console.print(f"panic 策略: {panic}", style="info")

        self.copy_assets_for_build()
        console.print("资源文件复制完成", style="info")

        self.build_dll(
            features,
            arch=arch,
            panic=panic,
            clean=clean,
            output_name=output_name,
        )
        console.print("构建流程完成", style="info")

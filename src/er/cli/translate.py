import os
import subprocess
import tomlkit

from er.utils import fs
from er.utils.fs import to_path


def _run_translator() -> None:
    """运行翻译器"""
    gppcli_dir = to_path(os.environ["GPPCLI_PATH"])
    gppcli_path = gppcli_dir / "GalTranslPP_CLI.exe"
    config_path = to_path(os.getcwd()) / "misc" / "gpp" / "config.toml"
    subprocess.run(
        [str(gppcli_path), "--project-path", str(config_path)],
        cwd=gppcli_dir,
        check=True,
    )


def _change_trans_engine(new_engine: str) -> None:
    """修改翻译器的翻译引擎"""
    config_path = to_path("misc/gpp/config.toml")
    config = tomlkit.loads(config_path.read_text(encoding="utf-8"))
    config["plugins"]["transEngine"] = new_engine  # type: ignore
    config_path.write_text(tomlkit.dumps(config), encoding="utf-8")


def translate() -> None:
    """
    翻译正文(translate)，向AI输入TSV格式的对话并要求AI以TSV格式回复，
    使用 FORGALTSV_SYSTEM 和 FORGALTSV_TRANS_PROMPT_EN 作为提示词
    """
    fs.copy_entry("workspace/raw_json", "misc/gpp/gt_input", overwrite=True)
    fs.copy_entry(
        "workspace/人名替换表.toml", "misc/gpp/人名替换表.toml", overwrite=True
    )
    fs.copy_entry(
        "workspace/项目GPT字典.toml", "misc/gpp/项目GPT字典.toml", overwrite=True
    )

    _change_trans_engine("ForGalTsv")
    _run_translator()

    fs.copy_entry("misc/gpp/gt_output", "workspace/translated_json", overwrite=True)


def translate_name() -> None:
    """
    翻译人名表(translate_name)，如果没有则先Dump，使用 NAMETRANS_SYSTEM 和 NAMETRANS_PROMPT 作为提示词
    """
    fs.copy_entry("workspace/raw_json", "misc/gpp/gt_input", overwrite=True)

    _change_trans_engine("NameTrans")
    _run_translator()

    fs.copy_entry(
        "misc/gpp/人名替换表.toml", "workspace/人名替换表.toml", overwrite=True
    )


def rebuild() -> None:
    """
    重建结果(rebuild)，即使problem或orig_text中包含retranslKey也不会重翻，只根据缓存翻译重建结果
    """
    _change_trans_engine("Rebuild")
    _run_translator()

    fs.copy_entry("misc/gpp/gt_output", "workspace/translated_json", overwrite=True)


def dump_name() -> None:
    """
    导出人名(dump_name)，更新 人名替换表.toml 以供替换人名
    """
    fs.copy_entry("workspace/raw_json", "misc/gpp/gt_input", overwrite=True)

    _change_trans_engine("DumpName")
    _run_translator()

    fs.copy_entry(
        "misc/gpp/人名替换表.toml", "workspace/人名替换表.toml", overwrite=True
    )


def generate_dict() -> None:
    """
    生成术语表(generate_dict)，借助AI自动生成术语表，使用 GENDIC_SYSTEM 和 GENDIC_PROMPT 作为提示词
    """
    fs.copy_entry("workspace/raw_json", "misc/gpp/gt_input", overwrite=True)

    _change_trans_engine("GenDict")
    _run_translator()

    fs.copy_entry(
        "misc/gpp/项目GPT字典.toml", "workspace/项目GPT字典.toml", overwrite=True
    )

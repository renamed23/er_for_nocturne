from er.core.gal_json import GalJson
from er.utils.fs import collect_files


def generate_testfile_shorten():
    """生成变短的测试文件(generate_testfile_shorten)"""
    files = collect_files("workspace/raw_json")
    for file in files:
        (
            GalJson
            .load_from_path(file)
            .apply_remove_hiragana(5)
            .apply_map_all_to_zhong()
            .save_to_path(f"workspace/translated_json/{file.name}")
        )


def generate_testfile_lengthen():
    """生成变长的测试文件(generate_testfile_lengthen)"""
    files = collect_files("workspace/raw_json")
    for file in files:
        (
            GalJson
            .load_from_path(file)
            .apply_add_chinese_test_tag()
            .save_to_path(f"workspace/translated_json/{file.name}")
        )

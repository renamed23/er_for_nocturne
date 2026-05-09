import os

from er.core import text_hook
from er.core import config
from er.core.config import CONFIG, FEATURES
from er.core.gal_json import GalJson
from er.core.pipeline import exe_textract, packer, scrpiler, textract
from er.processor.mapping import ReplacementPoolBuilder
from er.utils import fs
from er.utils.console import console


def extract() -> None:
    """提取(extract)相关逻辑"""
    console.print("执行提取...", style="info")

    packer.unpack("workspace/nocturne", "workspace/script")

    scrpiler.decompile("workspace/script", "workspace/raw")

    gal_json = GalJson()
    textract.extract("workspace/raw", gal_json)

    (
        gal_json
        # .apply_remove_fullwidth_spaces()
        .apply_transform(lambda s: s.replace("\u0005", "@"))
        .apply_fullwidth(ignore_pattern=r"(@)")
        # .apply_escape_backslashes()
        .apply_current_to_raw_fields()
        .apply_add_tags()
        .save_to_path("workspace/raw_json/game_text.json")
    )

    # exe_gal_json = GalJson()
    # exe_textract.extract("workspace/anos3_raw.exe", exe_gal_json)
    # exe_gal_json.save_to_path("workspace/raw_json/exe_text.json")

    console.print("提取完成", style="info")


def replace(check: bool = True) -> None:
    """替换(replace)相关逻辑"""
    console.print("执行替换...", style="info")

    # exe_gal_json = GalJson.load_from_path("workspace/translated_json/exe_text.json")
    gal_json = GalJson.load_from_path("workspace/translated_json/game_text.json")
    gal_json.apply_remove_tags()

    if check:
        (
            gal_json
            .check_pua_characters()
            .check_korean_characters()
            .check_japanese_characters()
            .check_duplicate_quotes()
            .check_length_discrepancy()
            .check_quote_consistency()
            .check_invisible_characters()
            .check_forbidden_words()
            .check_unpaired_quotes()
            .check_max_text_len(28 * 4)
            .check_at_sign_count_consistency()
            .check_empty_translation()
            # .check_font_glyphs("assets/font/ZiYueYingYinSong-2.ttf")
            # .check_per_line_limit()
            .ok_or_print_error_and_exit()
        )

    (
        gal_json
        # .apply_unescape_backslashes()
        .apply_restore_whitespace()
        .apply_replace_rare_characters()
        .apply_replace_nested_brackets()
        .apply_replace_quotation_marks()
        .apply_fullwidth(ignore_pattern=r"(@)")
        .apply_transform(lambda s: s.replace("@", "\u0005"))
        # .apply_map_gbk_unsupported_chars()
    )

    pool = (
        ReplacementPoolBuilder()
        .exclude_from_gal_text(gal_json)
        # .exclude_from_gal_text(exe_gal_json)
        .build()
    )
    gal_json.apply_mapping(pool)
    # exe_gal_json.apply_mapping(pool)
    pool.save_mapping_to_path("workspace/generated/mapping.json")

    # if check:
    #     exe_gal_json.check_keep_len_limit().ok_or_print_error_and_exit()

    textract.apply("workspace/raw", gal_json, "workspace/generated/translated")

    scrpiler.compile(
        "workspace/generated/translated", "workspace/generated/translated_patch"
    )
    fs.copy_entry(
        "workspace/nocturne.json",
        "workspace/generated/misc/nocturne.json",
        overwrite=True,
    )

    fs.copy_entry("assets/exe", "workspace/generated/exe", overwrite=True)
    fs.merge_dir("assets/exe", "workspace/generated/dist", overwrite=True)
    config.generate_config_files()

    fs.copy_entry("assets/raw_text", "workspace/generated/raw_text", overwrite=True)
    fs.copy_entry(
        "assets/translated_text", "workspace/generated/translated_text", overwrite=True
    )

    text_hook.TextHookBuilder(os.environ["TEXT_HOOK_PROJECT_PATH"]).build(
        FEATURES, panic="immediate-abort", output_name="nocturne_chs.dll"
    )

    console.print("替换完成", style="info")


def fix_translated() -> None:
    """修复翻译JSON(fix_translated)的逻辑"""
    gal_json = GalJson.load_from_path("workspace/translated_json/game_text.json")
    (
        gal_json
        .apply_replace_standard_quotes()
        .apply_align_leading_whitespace()
        .apply_align_brackets_closure()
        .save_to_path("workspace/translated_json/game_text.json")
    )

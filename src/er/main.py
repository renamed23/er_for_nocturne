import typer

from er.cli.core import extract, fix_translated, replace
from er.cli.testfile import generate_testfile_lengthen, generate_testfile_shorten
from er.cli.translate import (
    dump_name,
    generate_dict,
    rebuild,
    translate,
    translate_name,
)

app = typer.Typer()

app.command(name="e")(extract)
app.command(name="r")(replace)
app.command(name="ft")(fix_translated)

app.command(name="t")(translate)
app.command(name="tn")(translate_name)
app.command(name="rb")(rebuild)
app.command(name="dn")(dump_name)
app.command(name="gd")(generate_dict)

app.command(name="gts")(generate_testfile_shorten)
app.command(name="gtl")(generate_testfile_lengthen)


def main() -> None:
    app()

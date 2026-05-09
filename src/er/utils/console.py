from rich.console import Console
from rich.theme import Theme

custom_theme = Theme({"info": "cyan", "warn": "magenta", "error": "bold red"})

console = Console(theme=custom_theme)

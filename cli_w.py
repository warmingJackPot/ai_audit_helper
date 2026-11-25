"""cli_w"""
from rich.console import Console
from rich.panel import Panel
from audit_helper import cli_skillhub_v02

import warnings
# warnings.filterwarnings("ignore", category=DeprecationWarning, module="langchain")
# warnings.filterwarnings("ignore", message=".*LangChainDeprecationWarning.*")
warnings.filterwarnings("ignore")

console = Console()
console.print(Panel.fit("...UV+A_A+GENT..", style="bold blue"))
console.print("[dim]Запуск...[/dim]\n")

# Просто запускаем вашу функцию
cli_skillhub_v02.main()

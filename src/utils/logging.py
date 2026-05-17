"""Simple logging utilities using rich for pretty console output.

Provides a module‑level ``logger`` with ``info``, ``warning`` and ``error``
methods that delegate to ``rich.console.Console``.
"""

from rich.console import Console
from rich.pretty import Pretty

console = Console()

class _RichLogger:
    def info(self, msg: str, *args, **kwargs) -> None:
        console.print(f"[green]INFO[/green] {msg}", *args, **kwargs)

    def warning(self, msg: str, *args, **kwargs) -> None:
        console.print(f"[yellow]WARN[/yellow] {msg}", *args, **kwargs)

    def error(self, msg: str, *args, **kwargs) -> None:
        console.print(f"[red]ERROR[/red] {msg}", *args, **kwargs)

    def debug(self, msg: str, *args, **kwargs) -> None:
        # Debug can be toggled via an env var if needed; for now always show.
        console.print(f"[dim]DEBUG[/dim] {msg}", *args, **kwargs)

logger = _RichLogger()

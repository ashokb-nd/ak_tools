"""Clipboard utility helpers for CLI commands."""

from __future__ import annotations

import base64
import os
import shutil
import subprocess
import sys

COPY_ALIASES: dict[str, str] = {
    "attach": "docker attach ashok_trt8",
    "reprocess": """git clean -fdx
make -j8 -C /data4/ashok/REPROCESSING/analytics  all PYTHON3=1 PROC_ENV_KPI=1 REPROCESS=1
    """,
"analytics_ignore": """/ipe/
/proto/
/analytics_service/
*.c"""
}


def get_copy_aliases() -> dict[str, str]:
    """Return configured copy aliases.

    Edit COPY_ALIASES in this file to change or add aliases.
    """
    return dict(sorted(COPY_ALIASES.items(), key=lambda item: item[0]))


def _copy_with_tool(command: list[str], text: str) -> bool:
    """Try to copy text using a clipboard command. Return True on success."""
    try:
        subprocess.run(
            command,
            input=text,
            text=True,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
    except (OSError, subprocess.CalledProcessError):
        return False


def _linux_display_env() -> tuple[bool, bool]:
    """Return display availability as (has_wayland, has_x11)."""
    has_wayland = bool(os.environ.get("WAYLAND_DISPLAY"))
    has_x11 = bool(os.environ.get("DISPLAY"))
    return has_wayland, has_x11


def _copy_with_tmux(text: str) -> bool:
    """Copy text into tmux paste buffer if available."""
    if not os.environ.get("TMUX") or not shutil.which("tmux"):
        return False

    try:
        subprocess.run(["tmux", "set-buffer", "--", text], check=True)
        return True
    except (OSError, subprocess.CalledProcessError):
        return False


def _copy_with_osc52(text: str) -> bool:
    """Copy text using OSC52 escape sequence (works in many SSH terminals)."""
    if not sys.stdout.isatty():
        return False

    encoded = base64.b64encode(text.encode("utf-8")).decode("ascii")
    sequence = f"\033]52;c;{encoded}\a"

    try:
        sys.stdout.write(sequence)
        sys.stdout.flush()
        return True
    except OSError:
        return False


def _copy_to_clipboard_backend(text: str) -> str | None:
    """Copy text to system clipboard.

    Linux priority: wl-copy -> xclip -> xsel.
    Also supports macOS (`pbcopy`) and Windows (`clip`) for portability.
    """
    if not text:
        raise ValueError("Cannot copy empty text to clipboard.")

    candidates: list[tuple[str, list[str]]] = []

    if sys.platform.startswith("linux"):
        has_wayland, has_x11 = _linux_display_env()
        if has_wayland:
            candidates.append(("wl-copy", ["wl-copy"]))
        if has_x11:
            candidates.append(("xclip", ["xclip", "-selection", "clipboard"]))
            candidates.append(("xsel", ["xsel", "--clipboard", "--input"]))
    else:
        candidates.extend(
            [
                ("pbcopy", ["pbcopy"]),
                ("clip", ["clip"]),
            ]
        )

    for binary, command in candidates:
        if shutil.which(binary) and _copy_with_tool(command, text):
            return binary

    if _copy_with_tmux(text):
        return "tmux"

    if _copy_with_osc52(text):
        return "osc52"

    return None


def copy_to_clipboard(text: str) -> None:
    """Copy text to system clipboard or raise a RuntimeError if no backend works."""
    backend = _copy_to_clipboard_backend(text)
    if backend is not None:
        return

    is_headless_linux = sys.platform.startswith("linux") and not (
        os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")
    )

    if is_headless_linux:
        raise RuntimeError(
            "No GUI clipboard available in this headless session. "
            "Use a terminal with OSC52 support, run inside tmux, "
            "or set DISPLAY/WAYLAND and install wl-copy/xclip/xsel."
        )

    raise RuntimeError(
        "No clipboard tool available. Install one of: wl-copy (wl-clipboard), xclip, or xsel."
    )


def try_copy_to_clipboard(text: str) -> str | None:
    """Best-effort clipboard copy.

    Returns backend name when copied, else returns None without raising backend errors.
    """
    return _copy_to_clipboard_backend(text)

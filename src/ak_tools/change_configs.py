"""Utilities to copy a section from one INI file into sibling config files."""

from __future__ import annotations

from pathlib import Path


def _is_section_header(line: str) -> bool:
    stripped = line.strip()
    return stripped.startswith("[") and stripped.endswith("]") and len(stripped) > 2


def _find_section_bounds(lines: list[str], section_name: str) -> tuple[int, int] | None:
    target_header = f"[{section_name}]"
    start_index: int | None = None

    for index, line in enumerate(lines):
        if line.strip() == target_header:
            start_index = index
            break

    if start_index is None:
        return None

    end_index = len(lines)
    for index in range(start_index + 1, len(lines)):
        if _is_section_header(lines[index]):
            end_index = index
            break

    return start_index, end_index


def extract_section_block(config_path: str | Path, section_name: str) -> str:
    """Return the full text block for a section, including its header."""
    path = Path(config_path)
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    bounds = _find_section_bounds(lines, section_name)
    if bounds is None:
        raise ValueError(f"Section [{section_name}] not found in {path}")

    start_index, end_index = bounds
    return "".join(lines[start_index:end_index])


def replace_or_append_section(config_path: str | Path, section_name: str, section_block: str) -> bool:
    """Replace section if present, otherwise append it. Return True when file changes."""
    path = Path(config_path)
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    bounds = _find_section_bounds(lines, section_name)

    if bounds is None:
        existing = "".join(lines)
        normalized_existing = existing.rstrip("\n")
        new_content = f"{normalized_existing}\n\n{section_block}" if normalized_existing else section_block
    else:
        start_index, end_index = bounds
        new_lines = lines[:start_index] + [section_block] + lines[end_index:]
        new_content = "".join(new_lines)

    old_content = "".join(lines)
    if new_content == old_content:
        return False

    path.write_text(new_content, encoding="utf-8")
    return True


def copy_section_to_other_configs(source_config_path: str | Path, section_name: str) -> tuple[int, int]:
    """Copy section from source config into all sibling nd_config_*.ini files.

    Returns a tuple of (updated_count, scanned_count).
    """
    source_path = Path(source_config_path).expanduser().resolve()
    if not source_path.exists():
        raise FileNotFoundError(f"Source config does not exist: {source_path}")

    section_block = extract_section_block(source_path, section_name)

    candidate_files = sorted(source_path.parent.glob("nd_config_*.ini"))
    target_files = [path for path in candidate_files if path.resolve() != source_path]

    updated_count = 0
    for target_path in target_files:
        changed = replace_or_append_section(target_path, section_name, section_block)
        if changed:
            updated_count += 1

    return updated_count, len(target_files)



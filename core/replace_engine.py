"""Pure functions for parsing and validating AI replace blocks.

Format:
    <<<< 文件: path/to/file.py      (optional — defaults to current tab)
    <<<< 查找
    [old code]
    ====
    [new code]
    >>>> 替换
"""
import json
from dataclasses import dataclass, field
from typing import Optional, List, Dict


@dataclass
class ReplaceBlock:
    target_file: Optional[str] = None
    old_code: str = ""
    new_code: str = ""


def normalize_replace_block_text(text):
    if text is None:
        return ""
    return (text
            .replace("\r\n", "\n")
            .replace("\r", "\n")
            .replace(" ", " ")
            .replace("　", " "))


def extract_replace_blocks(text):
    """Parse AI-returned find/replace blocks, now with optional file targets.

    Supports: markdown code fences, explanatory text between blocks,
    empty replacements (deletion), and the new `<<<< 文件: path` directive.
    """
    text = normalize_replace_block_text(text)
    if not text or not text.strip():
        return []

    lines = text.split("\n")
    blocks = []
    i = 0
    total = len(lines)
    current_file = None

    while i < total:
        line_stripped = lines[i].strip()

        if line_stripped.startswith("<<<< 文件:") or line_stripped.startswith("<<<< 文件："):
            target = line_stripped.split(":", 1)[-1].split("：", 1)[-1].strip()
            current_file = target if target else None
            i += 1
            continue

        if line_stripped != "<<<< 查找":
            i += 1
            continue

        i += 1
        old_lines = []
        while i < total and lines[i].strip() != "====":
            old_lines.append(lines[i])
            i += 1

        if i >= total or lines[i].strip() != "====":
            break

        i += 1
        new_lines = []
        while i < total and lines[i].strip() != ">>>> 替换":
            new_lines.append(lines[i])
            i += 1

        if i >= total or lines[i].strip() != ">>>> 替换":
            break

        blocks.append(ReplaceBlock(
            target_file=current_file,
            old_code="\n".join(old_lines),
            new_code="\n".join(new_lines),
        ))
        current_file = None
        i += 1

    return blocks


def is_valid_replace_block(text):
    return bool(extract_replace_blocks(text))


def build_replace_blocks_signature(text):
    """Generate a stable signature from parsed replace blocks.

    Includes target_file so multi-file blocks produce different signatures
    than single-file blocks with the same code.
    """
    blocks = extract_replace_blocks(text)
    if not blocks:
        return ""

    normalized_blocks = []
    for block in blocks:
        normalized_blocks.append({
            "target_file": block.target_file or "",
            "old": normalize_replace_block_text(block.old_code).strip("\n"),
            "new": normalize_replace_block_text(block.new_code).strip("\n"),
        })

    try:
        return json.dumps(normalized_blocks, ensure_ascii=False, sort_keys=True)
    except Exception:
        return ""


def apply_replace_blocks(code, blocks, require_unique_match=False):
    """Apply replace blocks to a single code string, returning (new_code, result_dict)."""
    success_count = 0
    fail_count = 0
    failed_blocks = []
    diagnostics = []
    unique_match_failed = False
    total_replaced_occurrences = 0
    multi_match_failed = False
    zero_match_failed = False
    current_code = code

    for i, block in enumerate(blocks):
        old_code = block.old_code
        new_code = block.new_code
        match_count = current_code.count(old_code)

        if require_unique_match and match_count != 1:
            unique_match_failed = True
            if match_count == 0:
                zero_match_failed = True
                failure_type = "zero_match"
                suggestion = "查找代码没有命中当前文件。请基于当前完整代码重新生成替换块，确保 <<<< 查找 下的旧代码逐字符一致。"
            elif match_count > 1:
                multi_match_failed = True
                failure_type = "multi_match"
                suggestion = "查找代码命中了多处。请加入更多上下文，例如函数头、相邻代码或完整代码块，确保只命中一处。"
            else:
                failure_type = "unique_match_failed"
                suggestion = "唯一命中校验未通过。请重新生成更精确的查找块。"

            fail_count += 1
            preview = old_code.strip()[:80].replace('\n', ' ↵ ')
            failed_blocks.append(
                f"第 {i+1} 块失败 -> 唯一命中校验未通过({match_count} 次) -> {preview}...")
            diagnostics.append({
                "block_index": i + 1,
                "type": failure_type,
                "match_count": match_count,
                "old_preview": preview,
                "suggestion": suggestion,
            })
            continue

        if match_count >= 1:
            if require_unique_match:
                current_code = current_code.replace(old_code, new_code, 1)
                success_count += 1
                total_replaced_occurrences += 1
            else:
                current_code = current_code.replace(old_code, new_code)
                success_count += 1
                total_replaced_occurrences += match_count
        else:
            zero_match_failed = True
            fail_count += 1
            preview = old_code.strip()[:80].replace('\n', ' ↵ ')
            failed_blocks.append(f"第 {i+1} 块失败 -> 未命中 -> {preview}...")
            diagnostics.append({
                "block_index": i + 1,
                "type": "zero_match",
                "match_count": 0,
                "old_preview": preview,
                "suggestion": "查找代码没有在当前文件中命中。请以当前完整代码为准重新生成替换块，不要复用过期代码。",
            })

    return current_code, {
        "success": fail_count == 0 and success_count > 0,
        "success_count": success_count,
        "fail_count": fail_count,
        "total_replaced_occurrences": total_replaced_occurrences,
        "failed_blocks": failed_blocks,
        "diagnostics": diagnostics,
        "multi_match_failed": multi_match_failed,
        "zero_match_failed": zero_match_failed,
        "unique_match_failed": unique_match_failed,
    }


def group_blocks_by_file(blocks, current_file, project_roots=None):
    """Group blocks by their target_file.

    Blocks with target_file=None are assigned to current_file.
    Relative paths are resolved by trying each project_root directory
    (falling back to current_file's parent dir, then as-is).
    Returns dict keyed by normalized absolute file path.
    """
    import os as _os

    if project_roots is None:
        project_roots = []

    groups: Dict[str, List[ReplaceBlock]] = {}

    for block in blocks:
        target = block.target_file
        if target is None:
            key = _os.path.normpath(current_file) if current_file else ""
        elif _os.path.isabs(target):
            key = _os.path.normpath(target)
        else:
            resolved = None
            # Try each project root
            for root in project_roots:
                candidate = _os.path.normpath(_os.path.join(root, target))
                if _os.path.exists(candidate):
                    resolved = candidate
                    break
            # Fall back to current_file's directory
            if resolved is None and current_file:
                candidate = _os.path.normpath(
                    _os.path.join(_os.path.dirname(current_file), target))
                if _os.path.exists(candidate):
                    resolved = candidate
            # Fall back to any project root (even if file doesn't exist yet)
            if resolved is None and project_roots:
                resolved = _os.path.normpath(_os.path.join(project_roots[0], target))
            elif resolved is None:
                resolved = target
            key = resolved

        groups.setdefault(key, []).append(block)

    return groups

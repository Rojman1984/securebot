#!/usr/bin/env python3
"""
tool_validate_yaml.py — Validate a SKILL.md file's YAML frontmatter.

Checks that the frontmatter contains exactly:
  - name         (str, matches naming regex)
  - description  (str, non-empty)
  - triggers     (list of strings, at least one)
  - execution_mode  ("bash" or "python")
  - timeout      (int, > 0)

Usage:
    python3 tool_validate_yaml.py /path/to/SKILL.md
    # OR pipe content via stdin:
    cat SKILL.md | python3 tool_validate_yaml.py

Exit 0 = valid, non-zero = validation failed.
Prints "ok" on success or an error message on failure.
"""

import re
import sys

import yaml

_SKILL_NAME_RE = re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9_-]{1,48}[a-zA-Z0-9]$')
REQUIRED_FIELDS = {"name", "description", "triggers", "execution_mode", "timeout"}
VALID_EXECUTION_MODES = {"bash", "python"}


def parse_frontmatter(content: str) -> dict:
    """Extract YAML frontmatter from a SKILL.md string."""
    match = re.match(r'^---\n(.*?)\n---', content, re.DOTALL)
    if not match:
        raise ValueError("No YAML frontmatter found (expected --- ... --- block at top of file)")
    try:
        data = yaml.safe_load(match.group(1))
    except yaml.YAMLError as e:
        raise ValueError(f"YAML parse error: {e}")
    if not isinstance(data, dict):
        raise ValueError("Frontmatter did not parse as a YAML mapping")
    return data


def validate_skill_md(content: str) -> list[str]:
    """
    Return a list of error strings. Empty list = valid.
    """
    errors = []
    try:
        fm = parse_frontmatter(content)
    except ValueError as e:
        return [str(e)]

    # Check for missing required fields
    missing = REQUIRED_FIELDS - fm.keys()
    if missing:
        errors.append(f"Missing required fields: {sorted(missing)}")

    # name validation
    name = fm.get("name", "")
    if not isinstance(name, str) or not name:
        errors.append("'name' must be a non-empty string")
    elif not _SKILL_NAME_RE.match(name):
        errors.append(
            f"'name' value '{name}' is invalid — must match "
            r"^[a-zA-Z0-9][a-zA-Z0-9_-]{1,48}[a-zA-Z0-9]$"
        )

    # description validation
    desc = fm.get("description", "")
    if not isinstance(desc, str) or not desc.strip():
        errors.append("'description' must be a non-empty string")

    # triggers validation
    triggers = fm.get("triggers", None)
    if not isinstance(triggers, list) or len(triggers) == 0:
        errors.append("'triggers' must be a non-empty list of strings")
    elif not all(isinstance(t, str) and t.strip() for t in triggers):
        errors.append("All 'triggers' entries must be non-empty strings")

    # execution_mode validation
    mode = fm.get("execution_mode", "")
    if mode not in VALID_EXECUTION_MODES:
        errors.append(
            f"'execution_mode' must be one of {sorted(VALID_EXECUTION_MODES)}, got '{mode}'"
        )

    # timeout validation
    timeout = fm.get("timeout", None)
    if not isinstance(timeout, int) or timeout <= 0:
        errors.append("'timeout' must be a positive integer (seconds)")

    # bash skills must have a ## Script section with a ```bash block
    if mode == "bash":
        if "```bash" not in content:
            errors.append(
                "execution_mode 'bash' requires a ```bash ... ``` code block in the ## Script section"
            )

    return errors


def main():
    if len(sys.argv) == 2 and sys.argv[1] != "-":
        path = sys.argv[1]
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
        except FileNotFoundError:
            print(f"ERROR: File not found: {path}")
            sys.exit(1)
    else:
        content = sys.stdin.read()

    errors = validate_skill_md(content)
    if errors:
        print("VALIDATION FAILED:")
        for err in errors:
            print(f"  - {err}")
        sys.exit(1)
    else:
        print("ok")
        sys.exit(0)


if __name__ == "__main__":
    main()

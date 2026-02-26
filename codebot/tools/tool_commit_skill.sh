#!/usr/bin/env bash
# tool_commit_skill.sh — Save a vetted SKILL.md to /workspace/skills/<skill-name>/
#
# Usage: tool_commit_skill.sh <skill_name> <skill_md_path>
#
#   skill_name    — The 'name' value from the SKILL.md frontmatter (used as directory name)
#   skill_md_path — Path to the temp SKILL.md file to be committed
#
# Outputs "committed: <full_path>" on success.
# The gateway's skill_registry will pick it up on the next /skills/reload call.

set -euo pipefail

SKILL_NAME="${1:-}"
SKILL_MD_PATH="${2:-}"
SKILLS_DIR="${SKILLS_DIR:-/workspace/skills}"

if [[ -z "$SKILL_NAME" || -z "$SKILL_MD_PATH" ]]; then
    echo "ERROR: Usage: tool_commit_skill.sh <skill_name> <skill_md_path>" >&2
    exit 1
fi

# Validate skill_name — must match naming convention (no path traversal)
if ! echo "$SKILL_NAME" | grep -qE '^[a-zA-Z0-9][a-zA-Z0-9_-]{1,48}[a-zA-Z0-9]$'; then
    echo "ERROR: Invalid skill name: '$SKILL_NAME'" >&2
    exit 1
fi

if [[ ! -f "$SKILL_MD_PATH" ]]; then
    echo "ERROR: SKILL.md not found at: $SKILL_MD_PATH" >&2
    exit 1
fi

# Resolve the target directory and check for path traversal
TARGET_DIR="$(realpath -m "${SKILLS_DIR}/${SKILL_NAME}")"
SKILLS_REALDIR="$(realpath "${SKILLS_DIR}")"

if [[ "$TARGET_DIR" != "${SKILLS_REALDIR}/"* && "$TARGET_DIR" != "$SKILLS_REALDIR" ]]; then
    echo "ERROR: Path traversal detected for skill name: '$SKILL_NAME'" >&2
    exit 1
fi

# Create skill directory and copy SKILL.md
mkdir -p "$TARGET_DIR"
cp "$SKILL_MD_PATH" "${TARGET_DIR}/SKILL.md"

echo "committed: ${TARGET_DIR}/SKILL.md"

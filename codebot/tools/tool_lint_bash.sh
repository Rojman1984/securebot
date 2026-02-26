#!/usr/bin/env bash
# tool_lint_bash.sh — Run shellcheck against a generated .sh script.
# Usage: tool_lint_bash.sh <file_path>
# Exit 0 = clean, non-zero = lint errors found.

set -euo pipefail

FILE_PATH="${1:-}"

if [[ -z "$FILE_PATH" ]]; then
    echo "ERROR: No file path provided." >&2
    exit 1
fi

if [[ ! -f "$FILE_PATH" ]]; then
    echo "ERROR: File not found: $FILE_PATH" >&2
    exit 1
fi

# Run shellcheck with recommended severity
shellcheck --severity=warning --format=gcc "$FILE_PATH"
EXIT_CODE=$?

if [[ $EXIT_CODE -eq 0 ]]; then
    echo "shellcheck: OK — no warnings in $FILE_PATH"
fi

exit $EXIT_CODE

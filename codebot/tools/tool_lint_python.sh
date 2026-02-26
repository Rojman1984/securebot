#!/usr/bin/env bash
# tool_lint_python.sh — Run flake8 against a generated .py script.
# Usage: tool_lint_python.sh <file_path>
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

# Run flake8: max line length 100, ignore E501 for generated code
flake8 --max-line-length=100 --statistics "$FILE_PATH"
EXIT_CODE=$?

if [[ $EXIT_CODE -eq 0 ]]; then
    echo "flake8: OK — no errors in $FILE_PATH"
fi

exit $EXIT_CODE

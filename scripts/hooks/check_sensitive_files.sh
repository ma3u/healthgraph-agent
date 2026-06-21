#!/usr/bin/env bash
# Block accidentally committing sensitive files.
# Mirrors the TwoBreath-app pre-commit "sensitive file detection" step.
# pre-commit passes the staged file paths as arguments.
set -euo pipefail

bad=()
for f in "$@"; do
  case "$(basename "$f")" in
    .env|*.env|*.pem|*.key|*.p12|*.p8|*.cer|*.mobileprovision) bad+=("$f") ;;
  esac
  case "$f" in
    *credentials*|*secret*.json) bad+=("$f") ;;
  esac
done

if [ "${#bad[@]}" -gt 0 ]; then
  echo "❌ Refusing to commit potentially sensitive files:"
  printf '   - %s\n' "${bad[@]}"
  echo "   Unstage with: git reset HEAD <file>"
  echo "   If truly intentional: git commit --no-verify"
  exit 1
fi

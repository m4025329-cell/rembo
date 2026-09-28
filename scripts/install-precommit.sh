#!/usr/bin/env bash
# Ставит pre-commit + gitleaks-хуки для проекта.
set -euo pipefail

command -v pre-commit >/dev/null 2>&1 || pip install --user pre-commit
pre-commit install
pre-commit install --hook-type commit-msg || true

# Baseline для detect-secrets (нужен один раз)
if [[ ! -f .secrets.baseline ]]; then
    pip install --user detect-secrets
    detect-secrets scan > .secrets.baseline
    echo ".secrets.baseline создан. Проверь его перед коммитом."
fi

echo "✅ pre-commit установлен. Тест:  pre-commit run --all-files"

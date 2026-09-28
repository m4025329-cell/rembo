#!/usr/bin/env bash
# =====================================================================
#  BlackLotusVPN — обфускация критичных модулей для боевой сборки.
#
#  Python: pyarmor для файлов, где живёт биллинг и генерация ключей.
#  JS:     terser (минификация) + javascript-obfuscator.
#
#  Использует локальные npm-пакеты (без глобальной установки),
#  всё артефакты кладёт в dist_obf/.
# =====================================================================
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"

command -v pyarmor >/dev/null 2>&1 || pip install --user pyarmor
command -v npx     >/dev/null 2>&1 || { echo "Нужен Node.js/npx"; exit 1; }

DIST="$PROJECT_DIR/dist_obf"
rm -rf "$DIST" && mkdir -p "$DIST/py" "$DIST/js"

# ── Python (pyarmor) ──────────────────────────────────────────────
# Критичные модули: биллинг, генерация ключей, крипто.
PY_TARGETS=(
    "db/repo.py"
    "security/crypto.py"
    "security/passwords.py"
    "webapp/tg_auth.py"
)
echo "== PyArmor obfuscation =="
pyarmor gen --output "$DIST/py" "${PY_TARGETS[@]}"

# ── JavaScript ────────────────────────────────────────────────────
echo "== JS minify + obfuscate =="
npx --yes terser webapp/static/js/app.js \
    --compress \
    --mangle \
    --output "$DIST/js/app.min.js"

npx --yes javascript-obfuscator "$DIST/js/app.min.js" \
    --output "$DIST/js/app.obf.js" \
    --compact true \
    --control-flow-flattening true \
    --dead-code-injection true \
    --string-array true \
    --string-array-encoding rc4 \
    --self-defending true

echo
echo "✅ Готово. Файлы в $DIST"
echo "   Замени webapp/static/js/app.js на $DIST/js/app.obf.js в проде."

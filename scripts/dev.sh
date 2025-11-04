#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")"/.. && pwd)"

BACKEND_PORT="${BACKEND_PORT:-5001}"
DOCS_PORT="${DOCS_PORT:-8010}"
DASHBOARD_PORT="${DASHBOARD_PORT:-8000}"

# 准备虚拟环境
if [[ ! -d "$ROOT/.venv" ]]; then
  python3 -m venv "$ROOT/.venv"
fi
source "$ROOT/.venv/bin/activate"
python3 -m pip install -q --upgrade pip
python3 -m pip install -q flask flask-cors

# 数据迁移到 SQLite，并统一同义指标
python3 "$ROOT/scripts/migrate_to_db.py" || true
python3 "$ROOT/scripts/normalize_db_indicators.py" || true

# 配置前端 API 基址（指向本地后端）
cat > "$ROOT/docs/api_base.js" <<EOF
// 自动生成：开发态使用本地后端
window.__API_BASE__ = 'http://127.0.0.1:${BACKEND_PORT}';
EOF
cat > "$ROOT/dashboard/api_base.js" <<EOF
// 自动生成：开发态使用本地后端
window.__API_BASE__ = 'http://127.0.0.1:${BACKEND_PORT}';
EOF

# 启动后端
python3 "$ROOT/scripts/server.py" &
PID_BACKEND=$!

# 启动前端静态服务器
python3 -m http.server "${DOCS_PORT}" --directory "$ROOT/docs" &
PID_DOCS=$!

python3 -m http.server "${DASHBOARD_PORT}" --directory "$ROOT" &
PID_DASHBOARD=$!

cleanup() {
  echo "Stopping servers..."
  kill "${PID_BACKEND}" "${PID_DOCS}" "${PID_DASHBOARD}" 2>/dev/null || true
}
trap cleanup EXIT INT

echo "Backend API: http://127.0.0.1:${BACKEND_PORT}/api/data"
echo "Docs site:   http://localhost:${DOCS_PORT}/"
echo "Dashboard:   http://localhost:${DASHBOARD_PORT}/dashboard/"
# 自动打开浏览器（macOS）
if command -v open >/dev/null 2>&1; then
  open "http://localhost:${DOCS_PORT}/"
  open "http://localhost:${DASHBOARD_PORT}/dashboard/"
fi

echo "Press Ctrl+C to stop all servers."
wait
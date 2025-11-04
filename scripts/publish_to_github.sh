#!/usr/bin/env bash
set -o pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")"/.. && pwd)"
CSV="$ROOT/.github/workflows/github_PAT.csv"
LOG_DIR="$ROOT/dist"
LOG_FILE="$LOG_DIR/publish.log"

if [[ ! -f "$CSV" ]]; then
  echo "缺少 PAT 文件: $CSV" >&2
  exit 2
fi

# 读取第一行：username,PAT
IFS=',' read -r GITHUB_USER_RAW GITHUB_PAT < <(head -n1 "$CSV")
GITHUB_USER="$(echo "${GITHUB_USER_RAW%%@*}" | tr -d '[:space:]')"
OWNER="${GITHUB_OWNER:-EricZhou-math}"
REPO="${GITHUB_REPO:-ZHL}"
BRANCH="${GITHUB_BRANCH:-main}"

cd "$ROOT"

mkdir -p "$LOG_DIR"
echo "[INFO] Start publish at $(date)" > "$LOG_FILE"
echo "开始发布到 https://github.com/$OWNER/$REPO (分支: $BRANCH)"

# 初始化 git（如未初始化）
if [[ ! -d "$ROOT/.git" ]]; then
  git init
fi

# 确保不会提交 PAT 文件
git rm -q --cached ".github/workflows/github_PAT.csv" || true
if [[ -f "$ROOT/.gitignore" ]]; then
  if ! grep -q '^\.github/workflows/github_PAT\.csv$' "$ROOT/.gitignore"; then
    printf "\n.github/workflows/github_PAT.csv\n" >> "$ROOT/.gitignore"
  fi
else
  printf ".github/workflows/github_PAT.csv\n" > "$ROOT/.gitignore"
fi

# 设置提交身份（避免新仓库没有 user.name / user.email 导致 commit 失败）
if ! git config user.name >/dev/null; then
  git config user.name "$OWNER"
fi
if ! git config user.email >/dev/null; then
  git config user.email "$OWNER@users.noreply.github.com"
fi

# 提交（如有变更）
git add -A || true
if ! git diff --cached --quiet; then
  git commit -m "Publish to GitHub"
fi
git checkout -B "$BRANCH"

# 创建 GitHub 仓库（若已存在会返回 422，忽略错误）
create_payload=$(cat <<JSON
{"name":"$REPO","private":false}
JSON
)
echo "确保仓库存在: https://github.com/$OWNER/$REPO"
echo "[INFO] Ensure repo: https://github.com/$OWNER/$REPO" >> "$LOG_FILE"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
  -H "Authorization: token $GITHUB_PAT" \
  -H "Accept: application/vnd.github+json" \
  -d "$create_payload" \
  "https://api.github.com/user/repos" || true)
if [[ "$HTTP_CODE" == "201" ]]; then
  echo "仓库已创建"
  echo "[INFO] Repo created" >> "$LOG_FILE"
elif [[ "$HTTP_CODE" == "422" ]]; then
  echo "仓库已存在"
  echo "[INFO] Repo exists" >> "$LOG_FILE"
else
  echo "创建仓库返回代码: $HTTP_CODE（忽略继续）"
  echo "[WARN] Create repo HTTP: $HTTP_CODE" >> "$LOG_FILE"
fi

# 使用一次性 URL 推送（不持久化 PAT 到配置中）
echo "推送到 $BRANCH 分支..."
echo "[INFO] Pushing branch: $BRANCH" >> "$LOG_FILE"
set +e
ENC_PAT=$(python3 -c "import urllib.parse,sys; print(urllib.parse.quote(sys.argv[1], safe=''))" "$GITHUB_PAT")
git push -u "https://$GITHUB_USER:$ENC_PAT@github.com/$OWNER/$REPO.git" "$BRANCH" >/dev/null 2>&1
PUSH_CODE=$?
set -o pipefail
if [[ "$PUSH_CODE" -eq 0 ]]; then
  echo "推送成功: https://github.com/$OWNER/$REPO/tree/$BRANCH"
  echo "[INFO] Push OK" >> "$LOG_FILE"
else
  echo "推送失败（代码 $PUSH_CODE）。可能原因：PAT 权限不足、仓库名/所有者不匹配或网络问题。"
  echo "[ERROR] Push failed code=$PUSH_CODE" >> "$LOG_FILE"
fi

# Pages 提示
if [[ "$BRANCH" == "main" ]]; then
  echo "GitHub Pages 将自动部署 docs/。站点地址（预计）: https://$OWNER.github.io/$REPO/"
  echo "稍等 1-3 分钟后在仓库的 Actions 查看 Deploy GitHub Pages 状态。"
  echo "[INFO] Pages expected: https://$OWNER.github.io/$REPO/" >> "$LOG_FILE"
fi
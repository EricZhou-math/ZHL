#!/usr/bin/env python3
import json
import os
from pathlib import Path
from urllib import request, error

ROOT = Path(__file__).resolve().parent.parent
CSV = ROOT / '.github' / 'workflows' / 'github_PAT.csv'

OWNER = os.environ.get('GITHUB_OWNER', 'EricZhou-math')
REPO = os.environ.get('GITHUB_REPO', 'ZHL')
REF = os.environ.get('GITHUB_BRANCH', 'main')
WORKFLOW_FILE = os.environ.get('GITHUB_WORKFLOW', 'deploy-pages.yml')

def read_token(csv_path: Path):
    with open(csv_path, 'r', encoding='utf-8') as f:
        line = f.readline().strip()
    user, token = line.split(',', 1)
    return user.strip(), token.strip()

def api(method, url, token, data=None):
    headers = {
        'Accept': 'application/vnd.github+json',
        'Authorization': f'token {token}',
        'Content-Type': 'application/json'
    }
    body = None
    if data is not None:
        body = json.dumps(data).encode('utf-8')
    req = request.Request(url, data=body, headers=headers, method=method)
    try:
        with request.urlopen(req) as resp:
            return resp.status, resp.read().decode('utf-8')
    except error.HTTPError as e:
        try:
            return e.code, e.read().decode('utf-8')
        except Exception:
            return e.code, str(e)
    except Exception as e:
        return 0, str(e)

def main():
    if not CSV.exists():
        print('PAT 文件缺失: .github/workflows/github_PAT.csv')
        return
    user, token = read_token(CSV)
    url = f'https://api.github.com/repos/{OWNER}/{REPO}/actions/workflows/{WORKFLOW_FILE}/dispatches'
    status, content = api('POST', url, token, {'ref': REF})
    print(f'dispatch status: {status}')
    print(content)
    if status == 204:
        print('已触发 Pages 工作流，请到 Actions 查看运行情况。')
    elif status in (403, 404):
        print('触发失败：可能是 PAT 缺少 workflow 权限，或仓库未启用 Actions。请在仓库 Settings > Actions 启用，并在 Actions 页点击 Run workflow。')
    elif status == 0:
        print('网络或请求错误，请稍后重试。')

if __name__ == '__main__':
    main()
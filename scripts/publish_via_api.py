#!/usr/bin/env python3
import base64
import json
import os
import sys
from pathlib import Path
from urllib import request, parse, error

ROOT = Path(__file__).resolve().parent.parent
CSV = ROOT / '.github' / 'workflows' / 'github_PAT.csv'
OWNER = os.environ.get('GITHUB_OWNER', 'EricZhou-math')
REPO = os.environ.get('GITHUB_REPO', 'ZHL')
BRANCH = os.environ.get('GITHUB_BRANCH', 'main')

EXCLUDES = {
    '.git', '.venv', '__pycache__', 'node_modules', 'db/zhl.sqlite3',
    '.DS_Store', '*.pyc', 'origin_ocr_csv_files', 'dist/scf.zip',
    '.github/workflows/github_PAT.csv'
}

def should_exclude(p: Path) -> bool:
    rel = p.relative_to(ROOT).as_posix()
    parts = rel.split('/')
    for part in parts:
        if part in EXCLUDES:
            return True
    # glob-like simple endings
    for pat in EXCLUDES:
        if pat.startswith('*.') and rel.endswith(pat[1:]):
            return True
    return False

def read_csv_first_line(csv_path: Path):
    with open(csv_path, 'r', encoding='utf-8') as f:
        line = f.readline().strip()
    if not line:
        raise RuntimeError('github_PAT.csv is empty')
    if ',' not in line:
        raise RuntimeError('github_PAT.csv first line must be "username,PAT"')
    user, pat = line.split(',', 1)
    user = user.strip()
    pat = pat.strip()
    if not user or not pat:
        raise RuntimeError('Invalid username or PAT in github_PAT.csv')
    return user, pat

def api_request(method, url, token, data=None):
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
            return resp.status, resp.read()
    except error.HTTPError as e:
        return e.code, e.read()
    except Exception as e:
        return 0, str(e).encode('utf-8')

def ensure_repo(token):
    url = 'https://api.github.com/user/repos'
    status, content = api_request('POST', url, token, {
        'name': REPO,
        'private': False
    })
    if status == 201:
        print('仓库已创建')
    elif status == 422:
        print('仓库已存在')
    else:
        print(f'创建仓库返回代码: {status}')

def get_file_sha(token, path):
    url = f'https://api.github.com/repos/{OWNER}/{REPO}/contents/{parse.quote(path)}?ref={BRANCH}'
    status, content = api_request('GET', url, token)
    if status == 200:
        data = json.loads(content)
        return data.get('sha')
    return None

def upload_file(token, rel_path, message):
    abs_path = ROOT / rel_path
    with open(abs_path, 'rb') as f:
        b64 = base64.b64encode(f.read()).decode('utf-8')
    sha = get_file_sha(token, rel_path.as_posix())
    data = {
        'message': message,
        'content': b64,
        'branch': BRANCH,
    }
    if sha:
        data['sha'] = sha
    url = f'https://api.github.com/repos/{OWNER}/{REPO}/contents/{parse.quote(rel_path.as_posix())}'
    status, content = api_request('PUT', url, token, data)
    if status in (200, 201):
        print(f'上传: {rel_path}')
        return True
    else:
        print(f'失败({status}): {rel_path}')
        return False

def main():
    if not CSV.exists():
        print('缺少 PAT 文件: .github/workflows/github_PAT.csv', file=sys.stderr)
        sys.exit(2)
    user, token = read_csv_first_line(CSV)
    print(f'发布到 https://github.com/{OWNER}/{REPO} 分支 {BRANCH}')
    ensure_repo(token)
    uploaded = 0
    for p in ROOT.rglob('*'):
        if p.is_file() and not should_exclude(p):
            rel = p.relative_to(ROOT)
            msg = f'Publish {rel.as_posix()} (via API)'
            ok = upload_file(token, rel, msg)
            if ok:
                uploaded += 1
    print(f'完成上传 {uploaded} 个文件')
    print('如已推送到 main，GitHub Pages 将自动部署 docs/')

if __name__ == '__main__':
    main()
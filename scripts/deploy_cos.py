"""
Upload static site in docs/ to Tencent COS and enable static website hosting.

Prerequisites:
- pip install cos-python-sdk-v5
- Set env vars: COS_SECRET_ID, COS_SECRET_KEY, COS_REGION, COS_BUCKET
- Optional: COS_PREFIX (e.g., "zhl/")

This script will:
1) Create the bucket if it does not exist (best-effort);
2) Enable static website (index.html, error.html);
3) Upload all files under docs/ recursively with public-read ACL.
"""
import os
import sys
import mimetypes
from pathlib import Path

try:
    from qcloud_cos import CosConfig, CosS3Client
except Exception:
    print("Please install SDK: pip install cos-python-sdk-v5", file=sys.stderr)
    sys.exit(1)

BASE = Path(__file__).resolve().parent.parent
DOCS_DIR = BASE / 'docs'

# 尝试读取本地机密文件 .secrets/cos.env 并注入环境变量
try:
    import sys as _sys
    _sys.path.insert(0, str(Path(__file__).resolve().parent))
    import cos_secrets as _cos
    _cfg = _cos.load_cos_env()
    _cos.export_to_environ(_cfg, overwrite=False)
except Exception:
    pass

SID = os.environ.get('COS_SECRET_ID')
SKEY = os.environ.get('COS_SECRET_KEY')
REGION = os.environ.get('COS_REGION')
BUCKET = os.environ.get('COS_BUCKET')
PREFIX = os.environ.get('COS_PREFIX', '').strip()
if PREFIX and not PREFIX.endswith('/'):
    PREFIX = PREFIX + '/'

if not (SID and SKEY and REGION and BUCKET):
    print('Missing env: COS_SECRET_ID/COS_SECRET_KEY/COS_REGION/COS_BUCKET', file=sys.stderr)
    sys.exit(2)

config = CosConfig(Region=REGION, SecretId=SID, SecretKey=SKEY)
client = CosS3Client(config)

def ensure_bucket():
    try:
        client.head_bucket(Bucket=BUCKET)
        return True
    except Exception:
        try:
            client.create_bucket(Bucket=BUCKET)
            return True
        except Exception as e:
            print('Create bucket failed:', e, file=sys.stderr)
            return False

def enable_static_website():
    try:
        client.put_bucket_website(
            Bucket=BUCKET,
            WebsiteConfiguration={
                'IndexDocument': {'Suffix': 'index.html'},
                'ErrorDocument': {'Key': 'index.html'}
            }
        )
        return True
    except Exception as e:
        print('Enable website failed:', e, file=sys.stderr)
        return False

def upload_file(local: Path):
    rel = local.relative_to(DOCS_DIR).as_posix()
    key = PREFIX + rel
    # 优先使用显式的类型映射，避免浏览器将文件下载而不是渲染
    ext = local.suffix.lower()
    explicit_map = {
        '.html': 'text/html; charset=utf-8',
        '.htm': 'text/html; charset=utf-8',
        '.css': 'text/css; charset=utf-8',
        '.js': 'application/javascript; charset=utf-8',
        '.json': 'application/json; charset=utf-8',
        '.svg': 'image/svg+xml',
        '.png': 'image/png',
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.gif': 'image/gif',
        '.webp': 'image/webp'
    }
    ct = explicit_map.get(ext) or mimetypes.guess_type(local.name)[0] or 'application/octet-stream'
    with open(local, 'rb') as f:
        data = f.read()
    # 为避免被网站端强制下载，显式设置为 inline
    client.put_object(
        Bucket=BUCKET,
        Body=data,
        Key=key,
        ACL='public-read',
        ContentType=ct,
        CacheControl='no-cache',
        ContentDisposition='inline'
    )
    print('Uploaded:', key)

def main():
    if not DOCS_DIR.exists():
        print('docs/ not found', file=sys.stderr)
        sys.exit(3)
    if not ensure_bucket():
        sys.exit(4)
    enable_static_website()
    for p in DOCS_DIR.rglob('*'):
        if p.is_file():
            upload_file(p)
    print('All files uploaded to COS bucket:', BUCKET)

if __name__ == '__main__':
    main()
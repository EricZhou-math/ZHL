"""
Deploy/update Tencent Cloud SCF function with the built zip.

Prerequisites:
- pip install tencentcloud-sdk-python
- Build zip via: python scripts/build_scf_zip.py (outputs dist/scf.zip)
- Set env vars:
  TENCENT_SECRET_ID, TENCENT_SECRET_KEY, TENCENT_REGION (e.g., ap-shanghai)
  SCF_FUNCTION_NAME (e.g., zhl-dashboard-api)
  SCF_NAMESPACE (default: default)

This script will try UpdateFunctionCode, and fallback to CreateFunction if not exists.
You still need to configure API Gateway trigger to expose /api/data.
"""
import os
import sys
import base64
from pathlib import Path

try:
    from tencentcloud.scf.v20180416 import scf_client, models
    from tencentcloud.common import credential
    from tencentcloud.common.profile.client_profile import ClientProfile
    from tencentcloud.common.profile.http_profile import HttpProfile
except Exception:
    print('Please install SDK: pip install tencentcloud-sdk-python', file=sys.stderr)
    sys.exit(1)

BASE = Path(__file__).resolve().parent.parent
ZIP_PATH = BASE / 'dist' / 'scf.zip'

SID = os.environ.get('TENCENT_SECRET_ID')
SKEY = os.environ.get('TENCENT_SECRET_KEY')
REGION = os.environ.get('TENCENT_REGION', 'ap-shanghai')
FN = os.environ.get('SCF_FUNCTION_NAME')
NS = os.environ.get('SCF_NAMESPACE', 'default')

if not (SID and SKEY and FN):
    print('Missing env: TENCENT_SECRET_ID/TENCENT_SECRET_KEY/SCF_FUNCTION_NAME', file=sys.stderr)
    sys.exit(2)
if not ZIP_PATH.exists():
    print('Zip not found, run: python scripts/build_scf_zip.py', file=sys.stderr)
    sys.exit(3)

cred = credential.Credential(SID, SKEY)
httpProfile = HttpProfile()
clientProfile = ClientProfile(httpProfile=httpProfile)
client = scf_client.ScfClient(cred, REGION, clientProfile)

with open(ZIP_PATH, 'rb') as f:
    zip_b64 = base64.b64encode(f.read()).decode('utf-8')

def update_code():
    req = models.UpdateFunctionCodeRequest()
    req.FunctionName = FN
    req.Namespace = NS
    req.ZipFile = zip_b64
    req.Handler = 'server_scf.main_handler'
    req.InstallDependency = False
    return client.UpdateFunctionCode(req)

def create_func():
    req = models.CreateFunctionRequest()
    req.FunctionName = FN
    req.Namespace = NS
    req.Runtime = 'Python3.7'
    req.Handler = 'server_scf.main_handler'
    req.Code = models.Code()
    req.Code.ZipFile = zip_b64
    req.Description = 'ZHL Dashboard API (SCF)'
    req.Timeout = 10
    req.MemorySize = 256
    return client.CreateFunction(req)

def main():
    try:
        rsp = update_code()
        print('Updated function:', rsp)
    except Exception as e:
        print('Update failed, try create:', e)
        rsp = create_func()
        print('Created function:', rsp)
    print('Done. Please configure API Gateway trigger for /api/data')

if __name__ == '__main__':
    main()
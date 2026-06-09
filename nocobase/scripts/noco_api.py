#!/usr/bin/env python3
import os
import sys
import json
import uuid
import time
import urllib.request
import urllib.parse
import urllib.error

_BASE_URL = ''
_EMAIL = ''
_PASSWORD = ''
_API_KEY = ''
_TOKEN = None
_TOKEN_FILE = '/tmp/.noco_token'

def init_api(base_url=None, email=None, password=None):
    global _BASE_URL, _EMAIL, _PASSWORD, _API_KEY
    _BASE_URL = (base_url or os.environ.get('NOCO_BASE_URL', '')).rstrip('/') + '/api'
    _EMAIL = email or os.environ.get('NOCO_EMAIL', '')
    _PASSWORD = password or os.environ.get('NOCO_PASSWORD', '')
    _API_KEY = os.environ.get('NOCO_API_KEY', '')

def _load_token():
    global _TOKEN
    if _TOKEN:
        return _TOKEN
    try:
        with open(_TOKEN_FILE, 'r') as f:
            data = json.load(f)
            if data.get('url') == _BASE_URL and data.get('ts', 0) > time.time() - 3500:
                _TOKEN = data['token']
                return _TOKEN
    except Exception:
        pass
    return None

def _save_token(token):
    try:
        with open(_TOKEN_FILE, 'w') as f:
            json.dump({'token': token, 'url': _BASE_URL, 'ts': time.time()}, f)
    except Exception:
        pass

def login():
    global _TOKEN
    if not _BASE_URL or not _EMAIL or not _PASSWORD:
        print(json.dumps({"error": True, "message": "NOCO_BASE_URL, NOCO_EMAIL, NOCO_PASSWORD not configured"}), file=sys.stderr)
        sys.exit(1)
    url = f"{_BASE_URL}/auth:signIn"
    body = json.dumps({"email": _EMAIL, "password": _PASSWORD}).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read())
            _TOKEN = data.get('data', {}).get('token')
            if not _TOKEN:
                raise Exception(f"No token in login response: {json.dumps(data)}")
            _save_token(_TOKEN)
            return _TOKEN
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        raise Exception(f"Login failed ({e.code}): {body}")
    except Exception as e:
        raise Exception(f"Login error: {e}")

def ensure_token():
    global _TOKEN
    if _API_KEY:
        _TOKEN = _API_KEY
        return _TOKEN
    if _load_token():
        return _TOKEN
    return login()

def api(path, method="GET", body=None, query=None):
    ensure_token()
    url = f"{_BASE_URL}{path}"
    if query:
        url += f"?{query}"
    headers = {"Authorization": f"Bearer {_TOKEN}"}
    data = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            text = resp.read().decode()
            try:
                return json.loads(text)
            except Exception:
                return {"raw": text}
    except urllib.error.HTTPError as e:
        if e.code == 401:
            login()
            headers["Authorization"] = f"Bearer {_TOKEN}"
            req = urllib.request.Request(url, data=data, headers=headers, method=method)
            try:
                with urllib.request.urlopen(req) as resp:
                    text = resp.read().decode()
                    try:
                        return json.loads(text)
                    except Exception:
                        return {"raw": text}
            except urllib.error.HTTPError as e2:
                text = e2.read().decode()
                try:
                    jd = json.loads(text)
                except Exception:
                    jd = {"raw": text}
                return {"error": True, "status": e2.code, "data": jd}
        text = e.read().decode()
        try:
            jd = json.loads(text)
        except Exception:
            jd = {"raw": text}
        return {"error": True, "status": e.code, "data": jd}

def uid():
    return uuid.uuid4().hex[:16]

def create_and_attach(model_uid, use, parent_id, sub_key, sub_type, sort_index=None, step_params=None):
    create_body = {"uid": model_uid, "use": use}
    if sort_index is not None:
        create_body["sortIndex"] = sort_index
    if step_params:
        create_body["stepParams"] = step_params
    create_res = api("/flowModels:create", method="POST", body=create_body)
    if create_res.get("error"):
        return create_res
    if parent_id and sub_key:
        qp = urllib.parse.urlencode({"uid": model_uid, "parentId": parent_id, "subKey": sub_key})
        if sub_type:
            qp += f"&subType={sub_type}"
        api("/flowModels:attach", method="POST", query=qp)
    return create_res

def save_step_params(model_uid, step_params):
    return api("/flowModels:save", method="POST", body={"uid": model_uid, "stepParams": step_params})

def output(result, is_error=False):
    if isinstance(result, dict) and result.get("error"):
        print(json.dumps({"error": True, "data": result.get("data", result)}, ensure_ascii=False))
        sys.exit(1)
    if isinstance(result, str):
        print(result)
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))

def read_args():
    if len(sys.argv) > 1:
        try:
            return json.loads(sys.argv[1])
        except Exception:
            pass
    if not sys.stdin.isatty():
        try:
            return json.loads(sys.stdin.read())
        except Exception:
            pass
    return {}

def run_main(dispatch_fn):
    init_api()
    args = read_args()
    try:
        dispatch_fn(args)
    except SystemExit:
        raise
    except Exception as e:
        print(json.dumps({"error": True, "message": str(e)}, ensure_ascii=False))
        sys.exit(1)

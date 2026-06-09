import requests
import time

NOCO_BASE_URL = "http://144.168.59.25:13000"
NOCO_EMAIL = "admin@nocobase.com"
NOCO_PASSWORD = "admin123"

s = requests.Session()

# Step 1: Login
print("=== Step 1: 登录 ===")
r = s.post(f'{NOCO_BASE_URL}/api/auth:signIn', json={'email': NOCO_EMAIL, 'password': NOCO_PASSWORD})
if r.status_code != 200:
    print(f"登录失败: {r.text}")
    exit(1)
token = r.json()['data']['token']
s.headers['Authorization'] = f'Bearer {token}'
print(f"登录成功，token: {token[:20]}...")

# Step 2: 设置系统语言为中文
print("\n=== Step 2: 设置系统语言为中文 ===")
r = s.put(f'{NOCO_BASE_URL}/api/systemSettings/1', json={
    'enabledLanguages': ['zh-CN', 'en-US'],
    'appLang': 'zh-CN'
})
if r.status_code == 200:
    print("系统语言已设置为中文")
else:
    print(f"设置语言失败: {r.text}")

# Step 3: 启用所有插件
print("\n=== Step 3: 启用所有插件 ===")
r = s.get(f'{NOCO_BASE_URL}/api/pm:list')
if r.status_code != 200:
    print(f"获取插件列表失败: {r.text}")
    exit(1)

plugins = r.json().get('data', [])
disabled = [p for p in plugins if not p.get('enabled')]
enabled = [p for p in plugins if p.get('enabled')]
print(f"总插件数: {len(plugins)}, 已启用: {len(enabled)}, 未启用: {len(disabled)}")

for p in disabled:
    name = p['name']
    for attempt in range(3):
        r2 = s.post(f'{NOCO_BASE_URL}/api/pm:enable?filterByTk={name}')
        if r2.status_code == 200:
            print(f"  ✓ 已启用: {name}")
            break
        print(f"  ✗ 启用失败 ({attempt+1}/3): {name}")
        time.sleep(2)
    else:
        print(f"  ✗ 启用失败: {name}")

# 验证插件状态
r = s.get(f'{NOCO_BASE_URL}/api/pm:list')
total = len(r.json().get('data', []))
enabled_count = sum(1 for p in r.json().get('data', []) if p.get('enabled'))
print(f"\n插件启用完成: {enabled_count}/{total}")

# Step 4: 创建 API Key
print("\n=== Step 4: 创建 API Key ===")
r = s.post(f'{NOCO_BASE_URL}/api/apiKeys:create', json={
    'name': 'nocobase-skill',
    'role': {'name': 'root'},
    'expiresIn': 315360000
})
if r.status_code == 200:
    api_token = r.json()['data']['token']
    print(f"API Key 创建成功:")
    print(f"NOCO_BASE_URL={NOCO_BASE_URL}")
    print(f"NOCO_API_KEY={api_token}")
else:
    print(f"创建 API Key 失败: {r.text}")

print("\n=== 初始化完成 ===")

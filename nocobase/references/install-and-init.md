# NocoBase 安装与初始化

使用 NocoBase 前需先完成实例部署。以下为 Docker Compose + 外部 PostgreSQL 部署方案。

## 前置条件

| 组件 | 最低版本 | 说明 |
|------|---------|------|
| Docker | 20.10+ | 需 `docker compose` 插件 |
| PostgreSQL | 14+ | 外部数据库，需提前准备 |

## 选择版本

推荐使用稳定版 `X.Y-full` 镜像（如 `2.1-full`），锁定版本避免自动升级：

```bash
# 查询最新稳定版
curl -s "https://hub.docker.com/v2/repositories/nocobase/nocobase/tags?page_size=20&ordering=last_updated" \
  | python3 -c "
import json,sys
data=json.load(sys.stdin)
for t in data.get('results',[]):
    name=t['name']
    if '-full' in name and 'beta' not in name and 'alpha' not in name:
        print(name, t.get('last_updated',''))
" | head -10
```

## PostgreSQL 建库

数据库名称按 NocoBase 版本号命名，格式为 `nocobase_v<主版本号><次版本号>`，例如：
- 版本 `2.1.0` → 数据库名 `nocobase_v21`
- 版本 `2.0.36` → 数据库名 `nocobase_v2036`

在外部 PostgreSQL 中创建专用数据库：

```sql
CREATE DATABASE nocobase_v21 ENCODING 'UTF8';
```

> 使用已有的 postgres 用户即可，不需要单独创建用户。

## Docker Compose 部署

`docker-compose.yml` 内容：

```yaml
services:
  app:
    image: nocobase/nocobase:2.1-full          # 锁定版本
    restart: always
    environment:
      - APP_KEY=<openssl rand -hex 32 生成>     # 必须修改
      - DB_DIALECT=postgres
      - DB_HOST=192.168.1.31                    # 外部 PostgreSQL 地址
      - DB_PORT=5432
      - DB_DATABASE=nocobase_v21                # 按版本号命名
      - DB_USER=postgres
      - DB_PASSWORD=your_db_password
      - TZ=Asia/Shanghai
      - APP_LOCALE=zh-CN                        # 默认语言（仅影响登录页，不影响系统语言）
    volumes:
      - ./storage:/app/nocobase/storage
    ports:
      - '13000:80'
```

> **注意**：`APP_LOCALE` 环境变量仅控制登录页面语言，系统语言需部署后通过 API 额外设置。

## 启动服务

```bash
docker compose pull          # 拉取镜像
docker compose up -d         # 后台启动
```

首次启动需 1-3 分钟进行数据库初始化，`docker compose logs -f app` 查看进度。看到 `"app has been started"` 即启动完成。

## 验证安装

```bash
curl -s -o /dev/null -w "%{http_code}" http://<服务器IP>:13000/
# 输出 200 表示成功
```

浏览器访问 `http://<服务器IP>:13000`，初始账号：

- 账号：`admin@nocobase.com`
- 密码：`admin123`

## 初始配置（脚本自动化）

部署完成后需执行以下初始化步骤。NocoBase v2.1 首次启动后，仅内置核心插件自动激活，约 22 个可选插件需手动启用。

### Step 1: 设置环境变量

```bash
export NOCO_BASE_URL="http://<服务器IP>:13000"
export NOCO_EMAIL="admin@nocobase.com"
export NOCO_PASSWORD="admin123"
```

### Step 2: 切换系统语言为中文

`APP_LOCALE=zh-CN` 环境变量仅影响登录页面，系统语言仍需通过 API 设置：

```bash
python3 -c "
import requests
s = requests.Session()
r = s.post('${NOCO_BASE_URL}/api/auth:signIn', json={'email':'${NOCO_EMAIL}','password':'${NOCO_PASSWORD}'})
token = r.json()['data']['token']
s.headers['Authorization'] = f'Bearer {token}'
s.put('${NOCO_BASE_URL}/api/systemSettings/1', json={
    'enabledLanguages': ['zh-CN', 'en-US'],
    'appLang': 'zh-CN'
})
"
```

### Step 3: 启用全部可选插件

v2.1 首次部署后约 22 个非核心插件未激活，通过 `pm:enable` API 批量启用：

```bash
python3 -c "
import requests, time
s = requests.Session()
r = s.post('${NOCO_BASE_URL}/api/auth:signIn', json={'email':'${NOCO_EMAIL}','password':'${NOCO_PASSWORD}'})
token = r.json()['data']['token']
s.headers['Authorization'] = f'Bearer {token}'

r = s.get('${NOCO_BASE_URL}/api/pm:list')
disabled = [p['name'] for p in r.json().get('data', []) if not p.get('enabled')]
print(f'Found {len(disabled)} disabled plugins')

for name in disabled:
    for attempt in range(3):
        r2 = s.post(f'${NOCO_BASE_URL}/api/pm:enable?filterByTk={name}')
        if r2.status_code == 200:
            print(f'  OK: {name}')
            break
        time.sleep(5)
    else:
        print(f'  FAILED: {name}')

r = s.get('${NOCO_BASE_URL}/api/pm:list')
total = len(r.json().get('data', []))
enabled = sum(1 for p in r.json().get('data', []) if p.get('enabled'))
print(f'Final: {enabled}/{total} plugins enabled')
"
```

### Step 4: 创建 API Key

v2.1 中 API Key 与 JWT 集成，创建后生成 JWT Token 直接作为 Bearer Token 使用：

```bash
python3 -c "
import requests
s = requests.Session()
r = s.post('${NOCO_BASE_URL}/api/auth:signIn', json={'email':'${NOCO_EMAIL}','password':'${NOCO_PASSWORD}'})
token = r.json()['data']['token']
s.headers['Authorization'] = f'Bearer {token}'
s.headers['Content-Type'] = 'application/json'

r2 = s.post('${NOCO_BASE_URL}/api/apiKeys:create', json={
    'name': 'nocobase-skill',
    'role': {'name': 'root'},
    'expiresIn': 315360000
})
api_token = r2.json()['data']['token']
print(f'API Key token: {api_token}')
"
```

### Step 4: 设置 API Key 环境变量

```bash
# NOCO_API_KEY 直接填 JWT Token（不需要 "nocobase-skill:" 前缀）
export NOCO_API_KEY="eyJhbGciOiJIUzI1NiIs..."
unset NOCO_EMAIL NOCO_PASSWORD     # 清空密码变量
```

### Step 5: 验证脚本可用

```bash
python3 scripts/noco_collections.py '{"action":"list"}'
# 输出 [] 表示 API 认证正常
```

## API 环境变量参考

运行本 Skill 脚本前，设置以下环境变量（两种认证方式任选其一）：

**方式一：API Key（推荐）**
```bash
export NOCO_BASE_URL="http://<服务器IP>:13000"
export NOCO_API_KEY="<JWT Token>"              # v2.1: 纯 JWT Token，无前缀
```

**方式二：邮箱密码**
```bash
export NOCO_BASE_URL="http://<服务器IP>:13000"
export NOCO_EMAIL="admin@nocobase.com"
export NOCO_PASSWORD="your-password"
```

## v2.0 → v2.1 变更要点

| 项目 | v2.0 | v2.1 |
|------|------|------|
| 登录 API | `/api/auth:login` | `/api/auth:signIn` |
| API Key 格式 | `nocobase-skill:<token>` | 纯 JWT Bearer Token |
| API Key 创建参数 | `{"name":"x"}` | `{"name":"x","role":{"name":"root"},"expiresIn":315360000}` |
| API Key 创建端点 | `POST /api/apiKeys` | `POST /api/apiKeys:create` |
| 系统语言设置 | 仅 APP_LOCALE 环境变量 | 需额外调用 systemSettings API |
| 插件启用 API | `applicationPlugins:update` | `pm:enable?filterByTk=<name>` |
| 插件列表 API | `applicationPlugins:list` | `pm:list`（含运行时状态） |
| 首次启动后插件状态 | 部分需手动启用 | 核心插件自动激活，~22 个可选插件需 `pm:enable` |
| 数据库命名 | `nocobase_v2036` | `nocobase_v21`（按主次版本号） |

## 检查当前状态

```bash
# 检查语言
curl -s "${NOCO_BASE_URL}/api/systemSettings/1" \
  -H "Authorization: Bearer ${NOCO_API_KEY}" | python3 -c "
import json,sys; d=json.load(sys.stdin)['data'];
print('appLang:', d['appLang'], 'enabled:', d['enabledLanguages'])"

# 检查插件
python3 scripts/noco_plugins.py '{"action":"list","status":"disabled"}'

# 检查 API Key
curl -s "${NOCO_BASE_URL}/api/apiKeys?pageSize=10" \
  -H "Authorization: Bearer ${NOCO_API_KEY}"
```

---
name: pshell
description: 跨平台命令编码与转义工具，用于多层 Shell 链式调用场景。支持任意 Shell-Transport-Shell 组合（PS、Bash、cmd、ssh、qm_exec）。当 AI 需要通过 SSH 或 Proxmox qm guest exec 执行远程命令时触发。核心能力：PowerShell EncodedCommand 编码与链式转义分析。
---

# PSHELL — 跨平台 Shell 链式命令工具

## 定位

安全地将命令穿过任意多层 Shell 链，避免引号截断、变量提前展开、特殊字符损坏等问题。

## 链式模型

命令沿 **Shell 节点**与 **传输节点**交替组成的链路传递：

```
bash,ssh,ps                  # 本地 Bash → SSH → 远程 PS
ps,ssh,bash,qm_exec,ps       # PS → SSH → PVE Bash → qm guest exec → Windows PS
bash,ssh,ps,ssh,bash         # Bash → PS → Bash（来回切换）
ps,ssh,ps                    # PS → SSH → PS（直连 Windows SSH）
```

节点类型：
- **Shell 节点**：`ps`、`bash`、`cmd` — 命令实际执行的环境
- **传输节点**：`ssh`、`qm_exec`、`direct`、`pipe` — Shell 之间的传递方式

## 文本编码规范（关键）

所有文本文件（.md .json .js .ps1）统一使用 **UTF-8 无 BOM**，确保 Linux/Windows 兼容：

```powershell
$utf8 = New-Object System.Text.UTF8Encoding $false
[System.IO.File]::WriteAllText($path, $content, $utf8)
```

## 策略速查

| 条件 | 策略 | 可靠性 |
|------|------|--------|
| 含特殊字符（引号、$、管道等） | **B: EncodedCommand** | 最高 |
| 目标为 PS 且传输层 ≥ 2 | **B: EncodedCommand** | 最高 |
| 目标为 Bash 且命令简单 | **A: 单引号包裹** | 中 |
| Windows 系统命令（mkdir/icacls） | **C: cmd 直传** | 中 |
| 长脚本（>1000 字符） | **D: HTTP 传输** | 高 |

**黄金法则：拿不准就用 EncodedCommand，永远不会因转义出错。**

## 策略 B：EncodedCommand（首选）

```powershell
# 通过 Node.js 脚本编码（推荐）
$script | Out-File "$env:TEMP\s.ps1" -Encoding UTF8
$b64 = (& node scripts/encode-ps.js "$env:TEMP\s.ps1") -replace '\s+',''
ssh root@pve "qm guest exec 122 -- powershell -EncodedCommand $b64"

# 一键生成 qm 命令
node scripts/encode-ps.js --qm 122 < script.ps1
```

## 工具脚本

| 脚本 | 用途 | 示例 |
|------|------|------|
| `scripts/encode-ps.js` | PS 脚本 → EncodedCommand 编码器 | `node ... < s.ps1` / `--decode` / `--qm <vmid>` |
| `scripts/escape.js` | 链式转义分析器 | `--chain ps,ssh,bash --cmd "..." --analyze` |
| `scripts/test-runner.mjs` | 测试套件 | `--unit` / `--all` |

## PVE Guest Agent 常用命令

```bash
qm agent <vmid> ping                                    # 连通性检查
qm guest exec <vmid> -- powershell -EncodedCommand <b64> # PS（安全）
qm guest exec <vmid> -- cmd.exe /c <cmd>                # cmd（简单命令）
```

## 编码速查表

| 场景 | 正确做法 | 常见错误 |
|------|----------|----------|
| PS → EncodedCommand | UTF-16LE → base64 | UTF-8 → base64 |
| Bash → base64 | UTF-8 → base64 | UTF-16LE |
| 跨平台文件 | **UTF-8 无 BOM** | GBK / UTF-8 BOM |
| 写入 VM 文件 | `Set-Content -Encoding UTF8` | 缺少 `-Encoding` |
| 读取 VM 文件 | `Get-Content -Encoding UTF8` | 缺少 `-Encoding` |

## 完整示例：Windows SSH 密钥部署（4 跳链路）

```powershell
# 1. 生成密钥
ssh-keygen -t rsa -b 4096 -f ~/.ssh/id_rsa -N '""' -q

# 2. 编码部署脚本
$key = [IO.File]::ReadAllText("$env:USERPROFILE\.ssh\id_rsa.pub").Trim()
$script = @"
New-Item 'C:\ProgramData\ssh' -ItemType Dir -Force
Set-Content 'C:\ProgramData\ssh\administrators_authorized_keys' -Value '$key' -Encoding UTF8
"@
$b64 = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($script))
ssh root@pve "qm guest exec 122 -- powershell -EncodedCommand $b64"

# 3. 设置权限（策略 C）
ssh root@pve "qm guest exec 122 -- cmd.exe /c icacls C:\ProgramData\ssh\administrators_authorized_keys /inheritance:r /grant:r Administrators:R /grant:r SYSTEM:R"

# 4. 验证
ssh -o StrictHostKeyChecking=no -i ~/.ssh/id_rsa user@192.168.1.176 whoami
```

## 参考文档

- 策略模板 → `references/encoding-guide.md`
- 常见陷阱 → `references/pitfalls.md`
- 测试用例 → `tests/cases/`

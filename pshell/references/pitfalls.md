# 常见陷阱与解决方案

| 陷阱 | 症状 | 根因 | 解决 |
|------|------|------|------|
| 引号被中间层截断 | `TerminatorExpectedAtEndOfString` | 外层 Shell 消费了引号 | 用 EncodedCommand (策略B) |
| 反斜杠问题 | 路径截断或错误 | `\` 在 Bash 中是转义字符 | PS: 用单引号; Bash: 用正斜杠或双反斜杠 |
| `$var` 提前展开 | 变量为空或错误值 | PS 在双引号中展开 `$` | 用单引号或 EncodedCommand |
| cmd `echo > file` 失败 | 文件未创建 | `>` 被外层 Shell 消费 | 用 PS `Set-Content` 代替 |
| `Get-Content` 被 Linter 拦截 | Craft 拒绝执行 | 缺少 `-Encoding` 参数 | 始终加 `-Encoding UTF8` |
| plink 主机密钥拒绝 | `Cannot confirm host key in batch mode` | 首次连接需确认密钥 | 先交互执行一次，后续用 `-batch` |
| icacls 远程执行失败 | `file not found` | 路径反斜杠被转义丢失 | 用 EncodedCommand 执行 PS 版本 |
| 长命令被截断 | 部分执行 | 超出 Shell 命令行限制 (~8192) | 用 HTTP 文件传输 (策略D) |
| PS 管道到 Node.js 产生乱码 | base64 前后有 CLIXML/BOM | PS 管道添加了 XML 包装和 BOM | 写脚本到文件，用文件输入 |

## 混合 Shell 跳转陷阱（链式模型特有）

### Bash → PS 方向性陷阱
```
Bash 本地 → SSH → Windows PS:
  - Bash 的 $ 和 PS 的 $ 语义不同
  - 从 Bash 发出 PS 命令时，$var 会被 Bash 先展开
  - 解决：单引号包裹整个命令，或直接用 EncodedCommand
```

### PS → Bash → PS 反斜杠陷阱
```
"Write-Output 'C:\temp\file'"  经 PS → SSH → Bash → SSH → PS:
  - PS 层：\ 是字面量（单引号中）
  - SSH 层：剥离单引号，传递字面串
  - Bash 层：不做二次解析（在 SSH 的 cmd 中作为参数字面量）
  - SSH 层2：传递到远程 PS
  - VS PS → SSH → Bash (目标): \ 可能被 Bash 解析为转义
注意：不同目标 Shell 对反斜杠处理不同
```

### 传输层计数陷阱
```
普通脚本中，qm_exec 不算转义层（CreateProcess 直接传参）。
但在 --chain 模型中仍需列出，因为它影响目的Shell的判断。
"ps,ssh,bash,qm_exec,ps" 正确
"ps,ssh,bash,ps" 错误（缺少传输定义，会丢失一层跳转语义）
```

### 编码陷阱细节

#### PowerShell 管道 BOM 问题
```powershell
# 错误: PS 管道会添加 CLIXML/BOM
echo "Write-Output 'hello'" | node encode-ps.js

# 正确: 写文件再输入
"Write-Output 'hello'" | Out-File temp.ps1 -Encoding UTF8
node encode-ps.js temp.ps1
```

#### SSH 层转义递减
每一次 SSH 跳转消耗一层引号：
- PS → `ssh host "command"` → Bash 收到 `command`（无外层引号）
- PS → `ssh host "echo 'hello'"` → Bash 执行 `echo 'hello'` → 输出 `hello`

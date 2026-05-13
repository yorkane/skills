# 编码参考与代码模板

## 链式模型基础

每个跳转链由 Shell 类型和传输方式交替构成：

| 元素 | 含义 |
|------|------|
| `ps` / `bash` / `cmd` | 执行 Shell |
| `ssh` / `qm_exec` / `direct` / `pipe` | 传输层 |

命令从链首 Shell 发出，经传输层传递，在链尾 Shell 执行。

---

## 策略 A：单引号/简单包裹（适用：Bash目标、无特殊字符、短链）

```powershell
# PS → SSH → Bash
ssh root@192.168.1.21 "echo 'hello'"
```

**分析**：`node escape.js --chain ps,ssh,bash --cmd "echo hello" --analyze`

**限制**: 含 `'` `"` `$` 的命令会断裂。

---

## 策略 B：EncodedCommand（适用：PS目标、含特殊字符、多跳）★主推

```powershell
# 编码脚本（UTF-16LE → base64）
$script = "Write-Output 'multi-hop test'"
$b64 = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($script))

# 任意链路执行
ssh root@pve "qm guest exec 122 -- powershell -EncodedCommand $b64"
```

**分析**：`node escape.js --chain ps,ssh,bash,qm_exec,ps --cmd "..." --analyze`

**关键保障**: base64 仅含 `[A-Za-z0-9+/=]`，在所有层都是纯文本。

---

## 策略 C：cmd.exe 透传（适用：Windows系统命令）

```powershell
ssh root@pve "qm guest exec 122 -- cmd.exe /c 'mkdir C:\temp'"
```

**分析**：`node escape.js --chain ps,ssh,bash,qm_exec,cmd --cmd "mkdir C:\temp" --analyze`

---

## 策略 D：HTTP文件传输（适用：超大脚本/多文件）

```powershell
$script | ssh root@pve "cat > /tmp/s.ps1"
ssh root@pve "cd /tmp && python3 -m http.server 8000 &"
ssh root@pve "qm guest exec 122 -- powershell -Command 'iwr http://10.0.0.1:8000/s.ps1 -OutFile C:\s.ps1; C:\s.ps1'"
ssh root@pve "pkill -f 'http.server 8000'"
```

---

## 链式场景速查

| 场景 | --chain 参数 | 推荐策略 |
|------|-------------|---------|
| 本机PS → SSH → 远程Bash | `ps,ssh,bash` | A (简单) / B (复杂) |
| 本机Bash → SSH → 远程PS | `bash,ssh,ps` | **B** (Persistent) |
| PS → SSH → Bash → qm → PS | `ps,ssh,bash,qm_exec,ps` | **B** |
| Bash → SSH → PS → SSH → Bash | `bash,ssh,ps,ssh,bash` | A / B |
| PS → SSH → PS (direct Win SSH) | `ps,ssh,ps` | A / B |
| Bash → SSH → Bash → qm → PS | `bash,ssh,bash,qm_exec,ps` | **B** |

---

## 编码器对照表

| 场景 | 正确编码 | 错误做法 |
|------|----------|----------|
| PS脚本→EncodedCommand | UTF-16LE→base64 | UTF-8→base64 |
| Bash字符串→base64 | UTF-8→base64 | UTF-16LE |
| 文件路径 (PS内) | `'C:\Path\file'` (单引号=字面量) | `"C:\Path\$var"` (变量展开) |
| PS→SSH→Bash: 含变量的命令 | 单引号: `ssh host 'echo $HOME'` | 双引号: PS展开 `$` |

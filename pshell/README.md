# PSHELL — 跨平台命令转义 SKILL

## 核心问题

通过多层 Shell 链传递命令（PS→SSH→Bash→qm→PS 或任意组合），避免字符损坏。

## 快速使用

```bash
# 编码 PowerShell 脚本为安全格式
node scripts/encode-ps.js < script.ps1

# 分析链式命令转义需求（新 --chain 语法）
node scripts/escape.js --chain ps,ssh,bash,qm_exec,ps --cmd "whoami" --analyze
node scripts/escape.js --chain bash,ssh,ps --cmd "Get-Date" --analyze

# 运行测试
node scripts/test-runner.mjs --unit
```

## 链式模型

不再固定5层。任意 Shell + 传输组合：

| 真实场景 | --chain 参数 |
|----------|-------------|
| 本机 Bash → 远程 PS | `bash,ssh,ps` |
| 本机 PS → 远程 Bash | `ps,ssh,bash` |
| PS → PVE → qm → Win PS | `ps,ssh,bash,qm_exec,ps` |
| Bash → PS → Bash (ping-pong) | `bash,ssh,ps,ssh,bash` |

## 策略速选

| 命令特征 | 策略 |
|----------|------|
| 含引号/`$`/特殊字符 | **B: EncodedCommand** (base64) |
| PS 目标 + 多跳 | **B: EncodedCommand** |
| Bash 目标 + 简单命令 | A: 单引号包裹 |
| Windows 系统命令 | C: cmd.exe 透传 |
| 超长/多文件 | D: HTTP 传输 |

## 黄金规则

> 不确定时，用 EncodedCommand。永不会因转义失败。

## 文件结构

```
pshell/
├── SKILL.md                  # 核心文档（链式模型说明）
├── README.md                 # 速查
├── scripts/
│   ├── encode-ps.js          # PS→EncodedCommand 编码器
│   ├── escape.js             # 链式转义分析器（支持 --chain）
│   └── test-runner.mjs       # 测试套件
├── references/
│   ├── encoding-guide.md     # 编码参考与模板
│   └── pitfalls.md           # 常见陷阱
└── tests/cases/              # 测试用例定义
```

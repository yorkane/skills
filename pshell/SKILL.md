---
name: pshell
description: Cross-platform command escaping and encoding tool for multi-layer shell chains. Supports arbitrary Shell-Transport-Shell combinations (PS Bash cmd ssh qm_exec). Triggers when AI executes remote commands via SSH or Proxmox qm guest exec. Core: PowerShell EncodedCommand encoding and chain-based escape analysis.
---

# PSHELL -- Cross-Platform Shell Chain Tool

## Purpose

Safely pass commands through arbitrary multi-layer Shell chains. Avoid quote truncation, premature variable expansion, special character corruption.

## Chain Model (NOT fixed 5-layer)

Commands traverse **chains** of alternating Shell executions and Transport hops:

```
bash,ssh,ps                  # Local Bash -> SSH -> Remote PS
ps,ssh,bash,qm_exec,ps       # PS -> SSH -> PVE Bash -> qm guest exec -> Win PS
bash,ssh,ps,ssh,bash          # Bash -> PS -> Bash (ping-pong)
ps,ssh,ps                     # PS -> SSH -> PS (direct Win SSH)
```

Each element:
- Shell: `ps`, `bash`, `cmd` -- where commands execute
- Transport: `ssh`, `qm_exec`, `direct`, `pipe` -- how they pass between shells

## Encoding Rule (CRITICAL)

All text files (.md .json .js) MUST use **UTF-8 without BOM** for Linux/Windows compatibility.

```powershell
$utf8 = New-Object System.Text.UTF8Encoding $false
[System.IO.File]::WriteAllText($path, $content, $utf8)
```

## Strategy Quick Reference

| Condition | Strategy | Reliability |
|-----------|----------|-------------|
| Special chars (quotes $ pipes etc) | **B: EncodedCommand** | Highest |
| PS target + 2+ transports | **B: EncodedCommand** | Highest |
| Bash target + simple | A: Single-Quote Wrap | Medium |
| Windows system cmd (mkdir/icacls) | C: cmd Passthrough | Medium |
| Long script (>1000 chars) | D: HTTP Transfer | High |

**Golden rule: When unsure, use EncodedCommand. Never fails from escaping.**

## Strategy B Usage (Primary)

```powershell
# Encode via Node.js script (recommended)
$script | Out-File "$env:TEMP\s.ps1" -Encoding UTF8
$b64 = (& node scripts/encode-ps.js "$env:TEMP\s.ps1") -replace '\s+',''
ssh root@pve "qm guest exec 122 -- powershell -EncodedCommand $b64"

# One-liner qm command
node scripts/encode-ps.js --qm 122 < script.ps1
```

## Tool Scripts

| Script | Purpose | Example |
|--------|---------|---------|
| scripts/encode-ps.js | PS -> EncodedCommand encoder | `node ... < s.ps1` / `--decode` / `--qm <vmid>` |
| scripts/escape.js | Chain escape analyzer | `--chain ps,ssh,bash --cmd "..." --analyze` |
| scripts/test-runner.mjs | Test suite | `--unit` / `--all` |

## PVE Guest Agent Quick Ref

```bash
qm agent <vmid> ping                                   # connectivity check
qm guest exec <vmid> -- powershell -EncodedCommand <b64> # PS (safe)
qm guest exec <vmid> -- cmd.exe /c <cmd>                # cmd (simple)
```

## Text Encoding Reference

| Scenario | Correct | Wrong |
|----------|---------|-------|
| PS -> EncodedCommand | UTF-16LE -> base64 | UTF-8 -> base64 |
| Bash -> base64 | UTF-8 -> base64 | UTF-16LE |
| Cross-platform files | **UTF-8 without BOM** | GBK / UTF-8 BOM |
| Write VM file | Set-Content -Encoding UTF8 | No -Encoding |
| Read VM file | Get-Content -Encoding UTF8 | No -Encoding |

## Full Example: Windows SSH Key Deploy (4-hop chain)

```powershell
# 1. Generate key
ssh-keygen -t rsa -b 4096 -f ~/.ssh/id_rsa -N '""' -q

# 2. Encode deploy script
$key = [IO.File]::ReadAllText("$env:USERPROFILE\.ssh\id_rsa.pub").Trim()
$script = @"
New-Item 'C:\ProgramData\ssh' -ItemType Dir -Force
Set-Content 'C:\ProgramData\ssh\administrators_authorized_keys' -Value '$key' -Encoding UTF8
"@
$b64 = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($script))
ssh root@pve "qm guest exec 122 -- powershell -EncodedCommand $b64"

# 3. Set permissions (Strategy C)
ssh root@pve "qm guest exec 122 -- cmd.exe /c icacls C:\ProgramData\ssh\administrators_authorized_keys /inheritance:r /grant:r Administrators:R /grant:r SYSTEM:R"

# 4. Verify
ssh -o StrictHostKeyChecking=no -i ~/.ssh/id_rsa user@192.168.1.176 whoami
```

## References

- Strategy templates -> references/encoding-guide.md
- Pitfalls -> references/pitfalls.md
- Test cases -> tests/cases/
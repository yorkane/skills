#!/usr/bin/env node
/**
 * escape.js — Multi-Layer Shell Escape Calculator (Chain Model)
 * 
 * Computes optimal escaping strategy for commands that traverse arbitrary
 * Shell → Transport → Shell chains. No longer assumes fixed 5-layer linear path.
 * 
 * Usage (new --chain syntax):
 *   node escape.js --chain ps,ssh,bash              --cmd "ls -la" --analyze
 *   node escape.js --chain bash,ssh,ps              --cmd "Get-Date" --analyze
 *   node escape.js --chain ps,ssh,bash,qm_exec,ps   --cmd "whoami" --analyze
 *   node escape.js --chain bash,ssh,ps,ssh,bash     --cmd "echo hello" --analyze
 * 
 * Legacy (deprecated, still works):
 *   node escape.js --source ps --target ps --layers 4 --cmd "..." --analyze
 */

const fs = require('fs');

const args = process.argv.slice(2);
const options = {
    chain: null,
    source: null,
    target: null,
    layers: 0,
    cmd: null,
    file: null,
    analyze: false,
};

for (let i = 0; i < args.length; i++) {
    switch (args[i]) {
        case '--chain':    options.chain = args[++i]; break;
        case '--source':   options.source = args[++i]; break;
        case '--target':   options.target = args[++i]; break;
        case '--layers':   options.layers = parseInt(args[++i]); break;
        case '--cmd':      options.cmd = args[++i]; break;
        case '--file':     options.file = args[++i]; break;
        case '--analyze':  options.analyze = true; break;
        case '--help':
        case '-h':
            showHelp();
            process.exit(0);
    }
}

// ============================================================
// Shell & Transport Definitions
// ============================================================

const SHELLS = {
    ps: {
        name: 'PowerShell',
        singleQuote: "'",
        doubleQuote: '"',
        escapeChar: '`',
        pathSep: '\\',
        encodedCmd: true,        // supports -EncodedCommand
    },
    bash: {
        name: 'Bash',
        singleQuote: "'",
        doubleQuote: '"',
        escapeChar: '\\',
        pathSep: '/',
        encodedCmd: false,
    },
    cmd: {
        name: 'cmd.exe',
        singleQuote: null,
        doubleQuote: '"',
        escapeChar: '^',
        pathSep: '\\',
        encodedCmd: false,
    },
};

const TRANSPORTS = {
    ssh: {
        name: 'SSH Transport',
        stripsQuotes: true,       // SSH consumes one layer of outer quotes
        addsLayer: true,
    },
    qm_exec: {
        name: 'QEMU Guest Exec',
        stripsQuotes: false,      // CreateProcess passes args as-is
        addsLayer: true,
    },
    direct: {
        name: 'Direct (same machine)',
        stripsQuotes: false,
        addsLayer: false,
    },
    pipe: {
        name: 'Pipe / Subshell',
        stripsQuotes: true,
        addsLayer: true,
    },
};

// ============================================================
// Chain Parsing
// ============================================================

/**
 * Parse a chain string like "ps,ssh,bash,qm_exec,ps" into a structured array.
 * Returns { elements: [{type, isShell, info}], source, target, hopCount }
 */
function parseChain(chainStr) {
    const elements = [];
    const tokens = chainStr.split(',').map(t => t.trim()).filter(Boolean);

    let shellCount = 0;
    for (const token of tokens) {
        if (SHELLS[token]) {
            shellCount++;
            elements.push({ type: token, isShell: true, info: SHELLS[token] });
        } else if (TRANSPORTS[token]) {
            elements.push({ type: token, isShell: false, info: TRANSPORTS[token] });
        } else {
            // Unknown token — treat as transport (user-defined)
            elements.push({ type: token, isShell: false, info: { name: token, stripsQuotes: true, addsLayer: true } });
        }
    }

    if (shellCount < 2) {
        throw new Error(`Chain must contain at least 2 shell elements. Got ${shellCount} shell(s) in: ${chainStr}`);
    }

    // First shell = source, last shell = target
    const shells = elements.filter(e => e.isShell);
    const source = shells[0].type;
    const target = shells[shells.length - 1].type;

    // Count transport hops (elements between first and last shell)
    let hopCount = 0;
    let betweenFirstLast = false;
    let firstShellSeen = false;
    for (const e of elements) {
        if (e.isShell) {
            if (!firstShellSeen) { firstShellSeen = true; continue; }
            if (e === shells[shells.length - 1]) break; // stop at last shell
        }
        if (firstShellSeen && !e.isShell && e.info.addsLayer) hopCount++;
    }
    // Also count transports after last shell? No — target is last shell
    // But count all transports between first and last shell (including those between intermediate shells)
    // Simpler: count all non-shell elements with addsLayer=true
    hopCount = elements.filter(e => !e.isShell && e.info.addsLayer).length;

    return { elements, source, target, hopCount };
}

/**
 * Build default chain from legacy --source/--target/--layers
 */
function buildLegacyChain(source, target, layers) {
    if (layers <= 0) layers = 1;
    const parts = [source];
    for (let i = 1; i < layers; i++) {
        parts.push('ssh');
        // Assume intermediate shells are bash (Linux servers) unless target is ps and we're at penultimate
        if (i < layers - 1) {
            parts.push('bash');
        } else {
            // Last hop: go to target's shell type
            parts.push(target);
        }
    }
    // If only 1 layer, just add target
    if (layers === 1) parts.push(target);
    return parts.join(',');
}

// ============================================================
// Special Character Detection
// ============================================================

function hasSpecialChars(cmd, target) {
    if (!cmd) return false;
    if (target === 'ps') {
        return /["'`$|&;@]/.test(cmd);
    } else if (target === 'bash') {
        return /["'`$|&;<>(){}[\]!#~*?\\]/.test(cmd);
    } else if (target === 'cmd') {
        return /["|&<>^%]/.test(cmd);
    }
    return /["'`$|&;<>]/.test(cmd);
}

// ============================================================
// Strategy Calculation (Chain-based)
// ============================================================

function calculateStrategy(chainData, command) {
    const { elements, source, target, hopCount } = chainData;

    // Build layer hierarchy for display
    const layerStack = [];
    let shellCount = 0;
    for (const e of elements) {
        const label = e.isShell ? e.info.name : `[${e.info.name}]`;
        layerStack.push(label);
    }

    // Decision logic based on actual chain
    let recommendation;

    if (target === 'ps') {
        // PowerShell target: prefer EncodedCommand if risky
        if (hasSpecialChars(command, 'ps')) {
            recommendation = {
                strategy: 'EncodedCommand',
                reason: `Command contains PS-special characters. EncodedCommand (UTF-16LE→base64) bypasses all escaping.`,
                template: buildEncodedCommandTemplate(command, source),
            };
        } else if (hopCount >= 2) {
            recommendation = {
                strategy: 'EncodedCommand',
                reason: `${hopCount}-hop chain is complex. EncodedCommand is safest even for simple commands.`,
                template: buildEncodedCommandTemplate(command, source),
            };
        } else if (source === 'bash' && command.includes("'")) {
            recommendation = {
                strategy: 'EncodedCommand',
                reason: 'Command contains single quotes from Bash source — quoting would be fragile.',
                template: buildEncodedCommandTemplate(command, source),
            };
        } else {
            recommendation = {
                strategy: 'Simple Wrap',
                reason: 'No special characters, short chain. Simple quoting works.',
                template: buildSimpleWrapTemplate(command, source, target, hopCount),
            };
        }
    } else if (target === 'cmd') {
        recommendation = {
            strategy: 'cmd.exe Pass-through',
            reason: 'Use cmd.exe /c for simple Windows commands. Avoid |, >, <, &, ^.',
            template: `cmd.exe /c ${escapeCmdCommand(command)}`,
        };
    } else if (target === 'bash') {
        if (hasSpecialChars(command, 'bash') && hopCount >= 2) {
            recommendation = {
                strategy: 'Base64 Encode',
                reason: 'Bash target with special chars + multi-hop. Use base64 encoding (UTF-8).',
                template: buildBashBase64Template(command),
            };
        } else {
            recommendation = {
                strategy: 'Single-Quote Wrap',
                reason: 'Bash single quotes prevent all expansion. Safe for simple commands.',
                template: `'${command.replace(/'/g, "'\\''")}'`,
            };
        }
    }

    return { layerStack, recommendation, source, target, hopCount };
}

// ============================================================
// Template Builders
// ============================================================

function buildEncodedCommandTemplate(command, source) {
    let encodeHint;
    if (source === 'ps') {
        encodeHint = `$b64 = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($script))`;
    } else if (source === 'bash') {
        encodeHint = `B64=$(echo "$script" | iconv -t UTF-16LE | base64 -w0)`;
    } else {
        encodeHint = `# Generate EncodedCommand from your source shell:\n# PS: $b64 = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($script))\n# Bash: B64=$(echo "$script" | iconv -t UTF-16LE | base64 -w0)`;
    }
    return `
# EncodedCommand Template (UTF-16LE → base64):
${encodeHint}

# Script to encode:
${command}

# Execute via any layer:
# powershell -EncodedCommand <b64>
# ssh user@host "powershell -EncodedCommand <b64>"
# qm guest exec <vmid> -- powershell -EncodedCommand <b64>`;
}

function buildBashBase64Template(command) {
    return `
# Bash base64 Template (UTF-8):
echo '${command.replace(/'/g, "'\\''")}' | base64 -w0

# Execute:
# echo <b64> | base64 -d | bash
# ssh host "echo <b64> | base64 -d | bash"`;
}

function buildSimpleWrapTemplate(command, source, target, hops) {
    let wrapped = command;
    // Wrap based on target shell
    if (target === 'bash' || (target === 'ps' && source === 'bash')) {
        wrapped = `'${wrapped.replace(/'/g, "'\\''")}'`;
    } else if (target === 'ps') {
        wrapped = `'${wrapped}'`; // PS single-quote = literal
    }
    // Add SSH-level quoting for each hop
    for (let i = 0; i < hops; i++) {
        wrapped = `"${wrapped.replace(/"/g, '\\"')}"`;
    }
    return wrapped;
}

function escapeCmdCommand(cmd) {
    return cmd
        .replace(/\^/g, '^^')
        .replace(/&/g, '^&')
        .replace(/</g, '^<')
        .replace(/>/g, '^>')
        .replace(/\|/g, '^|');
}

// ============================================================
// Analyze & Report
// ============================================================

function analyzeChain(chainData, command) {
    const { elements, source, target, hopCount } = chainData;

    console.log('='.repeat(70));
    console.log('  PSHELL ESCAPE CALCULATOR — Chain Analysis');
    console.log('='.repeat(70));
    console.log();
    console.log(`Chain:       ${elements.map(e => e.isShell ? e.info.name : '[' + e.info.name + ']').join(' → ')}`);
    console.log(`Source:      ${SHELLS[source]?.name || source}`);
    console.log(`Target:      ${SHELLS[target]?.name || target}`);
    console.log(`Transports:  ${hopCount} hop(s)`);
    console.log(`Command:     ${command.substring(0, 80)}${command.length > 80 ? '...' : ''}`);
    console.log();

    const { recommendation } = calculateStrategy(chainData, command);

    console.log('Recommendation:');
    console.log(`  Strategy:  ${recommendation.strategy}`);
    console.log(`  Reason:    ${recommendation.reason}`);
    console.log(`  Template:`);
    console.log(recommendation.template);
    console.log();

    // Encoding reference
    console.log('Encoding Reference:');
    console.log('  PS EncodedCommand : UTF-16LE → base64');
    console.log('  Bash base64       : UTF-8 → base64');
    console.log('  cmd echo          : NOT safe for special chars');
    console.log();

    // Pitfalls based on actual chain
    const pitfalls = [];
    if (command.includes('$') && source === 'ps') {
        pitfalls.push('WARNING: $ detected — PS will expand in double-quoted strings');
    }
    if (command.includes('\\') && target === 'bash') {
        pitfalls.push('WARNING: Backslash in bash path — may be interpreted as escape char');
    }
    if (hopCount >= 3) {
        pitfalls.push('WARNING: 3+ transports — strongly recommend EncodedCommand');
    }
    if (source === 'bash' && target === 'ps' && !command.includes('EncodedCommand')) {
        pitfalls.push('TIP: Bash→PS often easiest via EncodedCommand (no quote wrestling)');
    }
    // Check for shell-type mismatch in simpleness
    if (source !== 'bash' && target === 'bash' && command.includes('\\')) {
        pitfalls.push('WARNING: Windows path separators (\\\\) in Bash target — use / or escape');
    }

    if (pitfalls.length > 0) {
        console.log('Pitfalls to Watch:');
        pitfalls.forEach(p => console.log(`  ${p}`));
    }
    console.log('='.repeat(70));
}

// ============================================================
// Main
// ============================================================

function main() {
    let command = options.cmd;
    if (options.file) {
        command = fs.readFileSync(options.file, 'utf8').trim();
    }

    // Resolve chain: prefer --chain, fallback to legacy --source/--target/--layers
    let chainData;
    if (options.chain) {
        chainData = parseChain(options.chain);
    } else if (options.source && options.target && options.layers > 0) {
        const legacyChain = buildLegacyChain(options.source, options.target, options.layers);
        console.error('NOTE: --source/--target/--layers is deprecated. Use --chain instead.');
        console.error(`      Equivalent: --chain ${legacyChain}`);
        console.error();
        chainData = parseChain(legacyChain);
    } else if (!options.chain && !command) {
        showHelp();
        return;
    } else {
        console.error('Error: Specify either --chain or --source/--target/--layers');
        showHelp();
        process.exit(1);
    }

    if (!command) {
        console.error('Error: --cmd or --file required');
        process.exit(1);
    }

    if (options.analyze) {
        analyzeChain(chainData, command);
    } else {
        const { recommendation } = calculateStrategy(chainData, command);
        console.log(recommendation.template);
    }
}

function showHelp() {
    console.log(`
escape.js — Multi-Layer Shell Escape Calculator (Chain Model)

USAGE (new --chain syntax):
  node escape.js --chain <elements> --cmd "<command>" [--analyze]

  elements: comma-separated list of shell types and transports.
    Shells:  ps, bash, cmd
    Transports: ssh, qm_exec, direct, pipe

EXAMPLES:
  # Bash local → SSH → PowerShell remote
  node escape.js --chain bash,ssh,ps --cmd "Get-Date" --analyze

  # PS local → SSH → Bash → QM exec → PS in VM
  node escape.js --chain ps,ssh,bash,qm_exec,ps --cmd "whoami" --analyze

  # Bash → SSH → Bash → SSH → Bash (multi-hop)
  node escape.js --chain bash,ssh,bash,ssh,bash --cmd "ls -la" --analyze

  # PS → SSH → PS (direct SSH to Windows)
  node escape.js --chain ps,ssh,ps --cmd "Get-Service sshd" --analyze

  # Bash → SSH → PS → SSH → Bash (ping-pong)
  node escape.js --chain bash,ssh,ps,ssh,bash --cmd "echo \$HOME" --analyze

LEGACY (deprecated, auto-converted):
  node escape.js --source ps --target ps --layers 4 --cmd "..." --analyze

OPTIONS:
  --chain <el1,el2,...>  Shell + transport chain (RECOMMENDED)
  --source <shell>       Legacy: origin shell type
  --target <shell>       Legacy: target shell type
  --layers <n>           Legacy: number of hops
  --cmd <command>        Command to analyze
  --file <path>          Read command from file
  --analyze              Detailed analysis with pitfalls
  --help, -h             This help

CHAIN ELEMENTS REFERENCE:
  ps       PowerShell shell
  bash     Bash shell
  cmd      Windows cmd.exe
  ssh      SSH transport (strips one quote level)
  qm_exec  QEMU Guest Agent exec (passes args as-is)
  direct   Same-machine direct execution
  pipe     Pipe or subshell transport
`);
}

main();

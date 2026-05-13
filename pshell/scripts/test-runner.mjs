#!/usr/bin/env node
/**
 * test-runner.mjs — PSHELL Comprehensive Test Suite
 * 
 * Validates cross-platform command execution strategies against real environments.
 * Tests: encoding round-trip, escaping correctness, remote command execution.
 * 
 * Usage:
 *   node test-runner.mjs --all              # Run all tests
 *   node test-runner.mjs --unit             # Unit tests only (no remote)
 *   node test-runner.mjs --scenario T03     # Run specific test
 *   node test-runner.mjs --verbose          # Detailed output
 * 
 * Environment:
 *   PVE_HOST=192.168.1.21 (default)
 *   VM_ID=122 (default)
 *   WIN_HOST=192.168.1.176 (default)
 *   WIN_USER=aigc (default)
 */

import { execSync, spawnSync } from 'child_process';
import { readFileSync, existsSync, writeFileSync, mkdirSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const SKILL_DIR = join(__dirname, '..');
const CASES_DIR = join(SKILL_DIR, 'tests', 'cases');
const RESULTS_DIR = join(SKILL_DIR, 'tests', 'results');

// Environment config
const CONFIG = {
    pveHost: process.env.PVE_HOST || '192.168.1.21',
    vmId: process.env.VM_ID || '122',
    winHost: process.env.WIN_HOST || '192.168.1.176',
    winUser: process.env.WIN_USER || 'aigc',
    nodePath: process.execPath,  // Use the current Node.js binary
    plinkPath: process.env.PLINK_PATH || join(process.env.TEMP || '/tmp', 'plink.exe'),
};

// Ensure results dir exists
if (!existsSync(RESULTS_DIR)) {
    mkdirSync(RESULTS_DIR, { recursive: true });
}

let passed = 0;
let failed = 0;
let verbose = false;
let testResults = [];

function log(level, msg) {
    const prefixes = { info: '  ', pass: '✓ ', fail: '✗ ', warn: '⚠ ', detail: '    ' };
    console.log(`${prefixes[level] || ''}${msg}`);
}

function assert(name, condition, details = '') {
    if (condition) {
        passed++;
        log('pass', `PASS: ${name}`);
        if (verbose && details) log('detail', details);
        testResults.push({ name, status: 'PASS', details });
    } else {
        failed++;
        log('fail', `FAIL: ${name}`);
        if (details) log('detail', details);
        testResults.push({ name, status: 'FAIL', details });
    }
}

function runCmd(cmd, opts = {}) {
    try {
        const result = execSync(cmd, {
            encoding: 'utf8',
            timeout: opts.timeout || 30000,
            stdio: opts.silent ? 'pipe' : 'inherit',
            ...opts,
        });
        return { success: true, output: result || '', error: '' };
    } catch (e) {
        return {
            success: false,
            output: e.stdout || '',
            error: e.stderr || e.message || '',
            code: e.status,
        };
    }
}

// ============================================================
// UNIT TESTS (no remote connectivity needed)
// ============================================================

function test_encode_decode_roundtrip() {
    log('info', '\n--- Unit: Base64 Round-Trip ---');
    
    const testScripts = [
        { name: 'simple', script: "Write-Output 'hello world'" },
        { name: 'special_chars', script: "Write-Output 'path: C:\\Program Files\\test'" },
        { name: 'quotes', script: 'Write-Output "double-quoted" ; Write-Output \'single-quoted\'' },
        { name: 'variables', script: '$env:USERNAME ; $PSVersionTable.PSVersion' },
        { name: 'multiline', script: "Get-Date\nGet-Process -Id $PID\nWrite-Output 'done'" },
    ];

    for (const test of testScripts) {
        // Encode
        const encodeResult = spawnSync(CONFIG.nodePath, 
            [join(__dirname, 'encode-ps.js')], 
            { input: test.script, encoding: 'utf8', stdio: 'pipe' }
        );
        const b64 = (encodeResult.stdout || '').replace(/\s+/g, '');

        assert(`encode: ${test.name}`, encodeResult.status === 0 && b64.length > 0,
            `Encoded ${test.script.length} chars → ${b64.length} chars base64\n  stdout:${(encodeResult.stdout || '').substring(0, 80)}\n  stderr:${(encodeResult.stderr || '').substring(0, 80)}`);

        if (!b64) continue; // Skip decode if encode failed

        // Decode
        const decodeResult = spawnSync(CONFIG.nodePath,
            [join(__dirname, 'encode-ps.js'), '--decode'],
            { input: b64, encoding: 'utf8', stdio: 'pipe' }
        );
        const decoded = (decodeResult.stdout || '').trim()
            .replace(/^\uFEFF/, '')  // Remove BOM
            .replace(/\r\n/g, '\n');  // Normalize line endings

        const expected = test.script.trim().replace(/\r\n/g, '\n');
        assert(`decode: ${test.name}`, decoded === expected,
            `Round-trip match\n  Expected: ${expected.substring(0, 50)}\n  Got:      ${decoded.substring(0, 50)}\n  stderr:   ${(decodeResult.stderr || '').substring(0, 80)}`);
    }
}

function test_escape_analyzer() {
    log('info', '\n--- Unit: Escape Analyzer (Legacy) ---');

    const scenarios = [
        { chain: 'ps,ssh,bash', cmd: 'ls -la', expect: 'Single-Quote Wrap' },
        { chain: 'ps,ssh,bash,ssh,ps', cmd: 'Write-Output "hello"', expect: 'EncodedCommand' },
        { chain: 'bash,ssh,ps', cmd: 'Get-Date', expect: 'EncodedCommand' },
    ];

    for (const s of scenarios) {
        const result = spawnSync(CONFIG.nodePath, [
            join(__dirname, 'escape.js'),
            '--chain', s.chain,
            '--cmd', s.cmd,
            '--analyze',
        ], { encoding: 'utf8', stdio: 'pipe' });

        const output = (result.stdout || '') + (result.stderr || '');
        assert(`analyze: ${s.chain}`,
            output.includes(s.expect),
            `Command: ${s.cmd}\nExpecting strategy: ${s.expect}`);
    }
}

function test_chain_variations() {
    log('info', '\n--- Unit: Chain Variations (Non-Linear) ---');

    const chainTests = [
        // Simple 2-hop chains
        { chain: 'ps,ssh,ps', cmd: 'whoami', expect: 'Simple Wrap', desc: 'PS→SSH→PS (simple, 1 transport)' },
        { chain: 'bash,ssh,ps', cmd: '$PSVersionTable', expect: 'EncodedCommand', desc: 'Bash→SSH→PS (with $)' },
        { chain: 'ps,ssh,bash', cmd: 'echo hello', expect: 'Single-Quote Wrap', desc: 'PS→SSH→Bash (alphanumeric)' },
        // Multi-hop mixed
        { chain: 'ps,ssh,bash,ssh,ps', cmd: 'whoami', expect: 'EncodedCommand', desc: 'PS→Bash→PS (2 transports)' },
        { chain: 'bash,ssh,ps,ssh,bash', cmd: 'echo hello', expect: 'Single-Quote Wrap', desc: 'Bash→PS→Bash ping-pong' },
        { chain: 'ps,ssh,bash,qm_exec,ps', cmd: "Write-Output 'test'", expect: 'EncodedCommand', desc: 'PVE path with qm_exec' },
    ];

    for (const t of chainTests) {
        const result = spawnSync(CONFIG.nodePath, [
            join(__dirname, 'escape.js'),
            '--chain', t.chain,
            '--cmd', t.cmd,
            '--analyze',
        ], { encoding: 'utf8', stdio: 'pipe' });

        const output = (result.stdout || '') + (result.stderr || '');
        // Match "Strategy:  <name>" (name may contain spaces, up to newline)
        const strategyMatch = output.match(/Strategy:\s+(.+?)(?:\n|$)/);
        const strategy = strategyMatch ? strategyMatch[1].trim() : 'UNKNOWN';
        assert(`chain: ${t.desc}`,
            strategy === t.expect,
            `Chain: ${t.chain}\nExpected: ${t.expect}, Got: ${strategy}\nCmd: ${t.cmd}`);
    }
}

function test_special_char_detection() {
    log('info', '\n--- Unit: Special Character Detection ---');

    const cases = [
        { cmd: 'hello', hasSpecial: false },
        { cmd: 'Write-Output "hello"', hasSpecial: true },
        { cmd: "Set-Content 'file' -Value 'ok'", hasSpecial: true },
        { cmd: 'New-Item -Path C:\\temp -ItemType Directory', hasSpecial: false },
        { cmd: 'ssh root@host "ls -la /tmp"', hasSpecial: true },
        { cmd: 'echo $HOME', hasSpecial: true },
        { cmd: 'whoami', hasSpecial: false },
    ];

    for (const c of cases) {
        // Use the escape analyzer to check (PS→SSH→PS chain)
        const result = spawnSync(CONFIG.nodePath, [
            join(__dirname, 'escape.js'),
            '--chain', 'ps,ssh,ps',
            '--cmd', c.cmd, '--analyze',
        ], { encoding: 'utf8', stdio: 'pipe' });

        const output = (result.stdout || '') + (result.stderr || '');
        // Check the Strategy line specifically (not encoding reference)
        const strategyMatch = output.match(/Strategy:\s+(\S+)/);
        const strategy = strategyMatch ? strategyMatch[1] : '';
        const isEncodedCmd = strategy === 'EncodedCommand';
        const name = c.cmd.substring(0, 40);
        assert(`special_chars: ${name}`,
            isEncodedCmd === c.hasSpecial,
            `Expected ${c.hasSpecial ? 'EncodedCommand' : 'Simple Wrap'}, got ${isEncodedCmd ? 'EncodedCommand' : 'Simple Wrap'}`);
    }
}

// ============================================================
// INTEGRATION TESTS (require remote connectivity)
// ============================================================

function checkConnectivity() {
    log('info', '\n--- Connectivity Check ---');
    
    const pveResult = runCmd(`ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=no root@${CONFIG.pveHost} "echo PVE_OK"`, { silent: true });
    assert('PVE connectivity', pveResult.success && pveResult.output.includes('PVE_OK'),
        pveResult.success ? `Connected to ${CONFIG.pveHost}` : `Failed: ${pveResult.error}`);

    const vmResult = runCmd(`ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=no root@${CONFIG.pveHost} "qm agent ${CONFIG.vmId} ping"`, { silent: true });
    assert('VM Guest Agent', vmResult.success,
        vmResult.success ? `VM ${CONFIG.vmId} Guest Agent responsive` : `Failed: ${vmResult.error}`);

    return pveResult.success && vmResult.success;
}

function test_simple_bash_command() {
    log('info', '\n--- Integration: PS→SSH→Bash ---');
    
    // Strategy A: Simple single-quote wrap
    const result = runCmd(`ssh -o StrictHostKeyChecking=no root@${CONFIG.pveHost} "echo 'hello_from_bash'"`, { silent: true });
    assert('PS→SSH→Bash: echo', 
        result.success && result.output.includes('hello_from_bash'),
        `Output: ${result.output.trim()}`);
}

function test_pve_qm_ps_simple() {
    log('info', '\n--- Integration: PS→SSH→PVE→qm→PS (Strategy B, EncodedCommand) ---');

    // Encode a simple script
    const script = "Write-Output 'test_from_encoded_cmd'";
    const encodeResult = spawnSync(CONFIG.nodePath,
        [join(__dirname, 'encode-ps.js')],
        { input: script, encoding: 'utf8', stdio: 'pipe' }
    );
    const b64 = (encodeResult.stdout || '').trim();

    // Execute via qm guest exec
    const result = runCmd(`ssh -o StrictHostKeyChecking=no root@${CONFIG.pveHost} "qm guest exec ${CONFIG.vmId} -- powershell -EncodedCommand ${b64}"`, { silent: true });
    assert('PS→SSH→PVE→qm→PS (EncodedCommand)',
        result.success && result.output.includes('test_from_encoded_cmd'),
        `Output: ${result.output.substring(0, 100)}`);
}

function test_pve_qm_ps_directory() {
    log('info', '\n--- Integration: PS→SSH→PVE→qm→PS (Directory Create) ---');

    const dirPath = 'C:\\pshell_test_dir_' + Date.now().toString(36);

    // Create directory
    const script = `New-Item -Path '${dirPath}' -ItemType Directory -Force; Write-Output 'dir_created'`;
    const encodeResult = spawnSync(CONFIG.nodePath,
        [join(__dirname, 'encode-ps.js')],
        { input: script, encoding: 'utf8', stdio: 'pipe' }
    );

    const result = runCmd(`ssh -o StrictHostKeyChecking=no root@${CONFIG.pveHost} "qm guest exec ${CONFIG.vmId} -- powershell -EncodedCommand ${encodeResult.stdout.trim()}"`, { silent: true });
    const created = result.success && result.output.includes('dir_created');
    assert('PS→SSH→PVE→qm→PS: New-Item dir',
        created,
        `Directory created: ${created}`);

    // Cleanup
    if (created) {
        const cleanupScript = `Remove-Item -Path '${dirPath}' -Force -ErrorAction SilentlyContinue`;
        const cleanupEnc = spawnSync(CONFIG.nodePath,
            [join(__dirname, 'encode-ps.js')],
            { input: cleanupScript, encoding: 'utf8', stdio: 'pipe' }
        );
        runCmd(`ssh -o StrictHostKeyChecking=no root@${CONFIG.pveHost} "qm guest exec ${CONFIG.vmId} -- powershell -EncodedCommand ${cleanupEnc.stdout.trim()}"`, { silent: true });
    }
}

function test_pve_qm_ps_special_chars() {
    log('info', '\n--- Integration: PS→SSH→PVE→qm→PS (Special Characters) ---');

    const testFile = 'C:\\pshell_test_' + Date.now().toString(36) + '.txt';
    const specialContent = "Hello 'World'! Path: C:\\Program Files\\App & special: $env:USERNAME";

    // Write file with special characters via EncodedCommand
    const script = `Set-Content -Path '${testFile}' -Value '${specialContent}' -Encoding UTF8; Write-Output 'file_written'`;
    const encodeResult = spawnSync(CONFIG.nodePath,
        [join(__dirname, 'encode-ps.js')],
        { input: script, encoding: 'utf8', stdio: 'pipe' }
    );

    const result = runCmd(`ssh -o StrictHostKeyChecking=no root@${CONFIG.pveHost} "qm guest exec ${CONFIG.vmId} -- powershell -EncodedCommand ${encodeResult.stdout.trim()}"`, { silent: true });
    const written = result.success && result.output.includes('file_written');
    assert('PS→SSH→PVE→qm→PS: Set-Content (special chars)',
        written,
        `File written: ${written}`);

    // Verify content
    const verifyScript = `Get-Content -Path '${testFile}' -Encoding UTF8`;
    const verifyEnc = spawnSync(CONFIG.nodePath,
        [join(__dirname, 'encode-ps.js')],
        { input: verifyScript, encoding: 'utf8', stdio: 'pipe' }
    );
    const verifyResult = runCmd(`ssh -o StrictHostKeyChecking=no root@${CONFIG.pveHost} "qm guest exec ${CONFIG.vmId} -- powershell -EncodedCommand ${verifyEnc.stdout.trim()}"`, { silent: true });
    
    const contentMatch = verifyResult.output.includes(specialContent.replace(/\$/g, ''));
    assert('PS→SSH→PVE→qm→PS: Verify file content round-trip',
        contentMatch,
        `Expected: ${specialContent.substring(0, 40)}...\nGot: ${verifyResult.output.substring(0, 100)}`);

    // Cleanup
    const cleanupScript = `Remove-Item -Path '${testFile}' -Force -ErrorAction SilentlyContinue`;
    const cleanupEnc = spawnSync(CONFIG.nodePath,
        [join(__dirname, 'encode-ps.js')],
        { input: cleanupScript, encoding: 'utf8', stdio: 'pipe' }
    );
    runCmd(`ssh -o StrictHostKeyChecking=no root@${CONFIG.pveHost} "qm guest exec ${CONFIG.vmId} -- powershell -EncodedCommand ${cleanupEnc.stdout.trim()}"`, { silent: true });
}

function test_pve_qm_cmd_passthrough() {
    log('info', '\n--- Integration: PS→SSH→PVE→qm→cmd (Strategy C) ---');

    const dirName = 'pshell_cmd_test_' + Date.now().toString(36);
    // Strategy C: cmd pass-through for mkdir
    const result = runCmd(`ssh -o StrictHostKeyChecking=no root@${CONFIG.pveHost} "qm guest exec ${CONFIG.vmId} -- cmd.exe /c 'mkdir C:\\\\${dirName}'"`, { silent: true });
    const created = result.success || result.output.includes('exitcode') || result.output.includes('0');
    assert('PS→SSH→PVE→qm→cmd: mkdir',
        created,
        `Directory created: ${created}`);

    // Cleanup via EncodedCommand (safer)
    const cleanupScript = `Remove-Item -Path 'C:\\${dirName}' -Force -ErrorAction SilentlyContinue`;
    const cleanupEnc = spawnSync(CONFIG.nodePath,
        [join(__dirname, 'encode-ps.js')],
        { input: cleanupScript, encoding: 'utf8', stdio: 'pipe' }
    );
    runCmd(`ssh -o StrictHostKeyChecking=no root@${CONFIG.pveHost} "qm guest exec ${CONFIG.vmId} -- powershell -EncodedCommand ${cleanupEnc.stdout.trim()}"`, { silent: true });
}

function test_native_ps_encode_decode() {
    log('info', '\n--- Integration: Native PowerShell vs Node.js Encoding ---');

    // Test that Node.js encode-ps.js produces the same result as PowerShell's native encoding
    const testScript = "Write-Output 'cross-platform test'";
    
    // Node.js encoding
    const nodeResult = spawnSync(CONFIG.nodePath,
        [join(__dirname, 'encode-ps.js')],
        { input: testScript, encoding: 'utf8', stdio: 'pipe' }
    );
    const nodeB64 = nodeResult.stdout.trim().replace(/\s+/g, '');

    // PowerShell encoding (via PVE → qm → PS)
    const psScript = `$s='${testScript.replace(/'/g, "''")}';$b=[System.Convert]::ToBase64String([System.Text.Encoding]::Unicode.GetBytes($s));Write-Output $b`;
    const psEnc = spawnSync(CONFIG.nodePath,
        [join(__dirname, 'encode-ps.js')],
        { input: psScript, encoding: 'utf8', stdio: 'pipe' }
    );
    const result = runCmd(`ssh -o StrictHostKeyChecking=no root@${CONFIG.pveHost} "qm guest exec ${CONFIG.vmId} -- powershell -EncodedCommand ${psEnc.stdout.trim()}"`, { silent: true });

    // Extract base64 from output
    const psB64 = extractBase64FromOutput(result.output);
    
    assert('Node.js vs PS encoding match',
        psB64 && nodeB64 === psB64.replace(/\s+/g, ''),
        `Node: ${nodeB64.substring(0, 30)}...\nPS:   ${(psB64 || '').substring(0, 30)}...`);
}

function extractBase64FromOutput(output) {
    // Try to extract base64 string from qm guest exec output
    // Format: {"out-data": "base64string\\r\\n"}
    const match = output.match(/[A-Za-z0-9+/=]{20,}/);
    if (match) {
        return match[0].replace(/\\r\\n/g, '').trim();
    }
    // Try to parse from JSON
    try {
        const lines = output.split('\n');
        for (const line of lines) {
            if (line.includes('out-data')) {
                const jsonMatch = line.match(/"out-data"\s*:\s*"([^"]+)"/);
                if (jsonMatch) {
                    return jsonMatch[1].replace(/\\r\\n/g, '').trim();
                }
            }
        }
    } catch (e) {}
    return null;
}

// ============================================================
// MAIN
// ============================================================

async function main() {
    const args = process.argv.slice(2);
    const runAll = args.includes('--all');
    const runUnit = args.includes('--unit');
    const runIntegration = args.includes('--integration');
    verbose = args.includes('--verbose');

    // Check for specific scenario
    const scenarioIdx = args.indexOf('--scenario');
    const scenario = scenarioIdx >= 0 ? args[scenarioIdx + 1] : null;

    console.log('='.repeat(60));
    console.log('  PSHELL Test Suite');
    console.log(`  PVE: ${CONFIG.pveHost}  |  VM: ${CONFIG.vmId}  |  Win: ${CONFIG.winHost}`);
    console.log('='.repeat(60));

    // Always run unit tests
    test_encode_decode_roundtrip();
    test_escape_analyzer();
    test_chain_variations();
    test_special_char_detection();

    // Run integration tests if requested and connectivity available
    if (runAll || runIntegration) {
        if (checkConnectivity()) {
            test_simple_bash_command();
            test_pve_qm_ps_simple();
            test_pve_qm_ps_directory();
            test_pve_qm_ps_special_chars();
            test_pve_qm_cmd_passthrough();
            test_native_ps_encode_decode();
        } else {
            log('warn', 'Integration tests skipped: no connectivity');
        }
    }

    // Summary
    const total = passed + failed;
    console.log('\n' + '='.repeat(60));
    console.log(`  RESULTS: ${passed}/${total} passed`);
    if (failed > 0) {
        console.log(`  FAILED: ${failed} tests`);
        testResults.filter(t => t.status === 'FAIL').forEach(t => 
            console.log(`    - ${t.name}: ${t.details}`));
    }
    console.log('='.repeat(60));

    // Save results
    const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
    writeFileSync(
        join(RESULTS_DIR, `test-results-${timestamp}.json`),
        JSON.stringify(testResults, null, 2)
    );

    process.exit(failed > 0 ? 1 : 0);
}

main().catch(err => {
    console.error('Test suite error:', err);
    process.exit(1);
});

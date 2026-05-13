#!/usr/bin/env node
/**
 * encode-ps.js — PowerShell EncodedCommand Generator
 * 
 * Encodes PowerShell scripts to base64 (UTF-16LE) for use with:
 *   powershell -EncodedCommand <output>
 * 
 * Usage:
 *   node encode-ps.js < script.ps1                    # Read from stdin
 *   node encode-ps.js script.ps1                      # Read from file
 *   node encode-ps.js --decode <base64>               # Decode for verification
 *   node encode-ps.js --wrap < script.ps1             # Output full command
 *   node encode-ps.js --qm 122 < script.ps1           # Wrap as qm guest exec
 *   echo "Write-Output 'hello'" | node encode-ps.js   # Pipe input
 */

const fs = require('fs');
const path = require('path');

// Parse arguments
const args = process.argv.slice(2);
let options = {
    decode: false,
    wrap: false,
    qm: null,
    file: null,
};

for (let i = 0; i < args.length; i++) {
    switch (args[i]) {
        case '--decode':
            options.decode = true;
            break;
        case '--wrap':
            options.wrap = true;
            break;
        case '--qm':
            options.qm = args[++i];
            break;
        case '--help':
        case '-h':
            showHelp();
            process.exit(0);
        default:
            if (!args[i].startsWith('--') && !options.file) {
                options.file = args[i];
            }
    }
}

/**
 * Encode a PowerShell script string to base64 (UTF-16LE)
 */
function encodeToBase64(script) {
    // PowerShell -EncodedCommand expects UTF-16LE (Unicode) encoding
    const buffer = Buffer.from(script, 'utf16le');
    return buffer.toString('base64');
}

/**
 * Decode base64 back to script for verification
 */
function decodeFromBase64(b64) {
    const buffer = Buffer.from(b64, 'base64');
    return buffer.toString('utf16le');
}

/**
 * Build the powershell -EncodedCommand invocation
 */
function wrapCommand(b64, qmVmid = null) {
    const psCmd = `powershell -EncodedCommand ${b64}`;
    if (qmVmid) {
        return `qm guest exec ${qmVmid} -- ${psCmd}`;
    }
    return psCmd;
}

// Main execution
async function main() {
    if (options.decode) {
        // Decode mode
        const b64 = options.file 
            ? fs.readFileSync(options.file, 'utf8').trim()
            : (await readStdin()).trim();
        const script = decodeFromBase64(b64);
        process.stdout.write(script);
        return;
    }

    // Encode mode
    const script = options.file
        ? fs.readFileSync(options.file, 'utf8')
        : await readStdin();

    if (!script || script.trim().length === 0) {
        console.error('Error: No script content provided');
        process.exit(1);
    }

    const b64 = encodeToBase64(script.trim());

    if (options.wrap || options.qm) {
        const cmd = wrapCommand(b64, options.qm);
        process.stdout.write(cmd);
    } else {
        process.stdout.write(b64);
    }
}

function readStdin() {
    return new Promise((resolve, reject) => {
        let data = '';
        process.stdin.setEncoding('utf8');
        process.stdin.on('data', chunk => data += chunk);
        process.stdin.on('end', () => resolve(data));
        process.stdin.on('error', reject);
    });
}

function showHelp() {
    console.log(`
encode-ps.js — PowerShell EncodedCommand Generator (UTF-16LE → base64)

USAGE:
  node encode-ps.js [options] [file]

OPTIONS:
  --decode        Decode base64 back to script (for round-trip verification)
  --wrap          Output complete command: powershell -EncodedCommand <b64>
  --qm <vmid>     Wrap as Proxmox qm guest exec command
  --help, -h      Show this help

EXAMPLES:
  # Encode from file
  node encode-ps.js myscript.ps1

  # Encode from pipe (PowerShell)
  echo "Write-Output 'hello'" | node encode-ps.js

  # Encode from pipe (bash)
  echo "Write-Output 'hello'" | node encode-ps.js

  # Output full powershell command
  node encode-ps.js --wrap myscript.ps1

  # Output qm guest exec command for VM 122
  node encode-ps.js --qm 122 myscript.ps1

  # Verify round-trip: encode then decode
  node encode-ps.js myscript.ps1 | node encode-ps.js --decode

NOTES:
  - Uses UTF-16LE encoding as required by PowerShell -EncodedCommand
  - Input must be valid PowerShell script (not arbitrary text)
  - For cmd.exe commands, use 'cmd.exe /c' pattern instead
`);
}

main().catch(err => {
    console.error('Error:', err.message);
    process.exit(1);
});

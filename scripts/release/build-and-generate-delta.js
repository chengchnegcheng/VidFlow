const path = require('path');
const readline = require('readline');
const { spawn } = require('child_process');

const rootDir = path.join(__dirname, '..', '..');
const isWin = process.platform === 'win32';
const nodeCommand = process.execPath;
const npmCommand = isWin ? 'npm.cmd' : 'npm';

function normalizeVersion(value) {
  return String(value || '').trim().replace(/^v/i, '');
}

function printHeader() {
  console.log('');
  console.log('========================================');
  console.log('VidFlow Build And Delta');
  console.log('========================================');
  console.log('');
}

function printUsage() {
  console.log('Usage:');
  console.log('  node scripts/release/build-and-generate-delta.js --source=1.0.2');
  console.log('  npm run delta:build -- --source=1.0.2');
  console.log('');
  console.log('Options:');
  console.log('  --source=<version>    Source version for the delta package');
  console.log('  --target=<version>    Target version (defaults to package.json version)');
  console.log('  --platform=<name>     Platform (defaults to current platform)');
  console.log('  --arch=<name>         Architecture (defaults to current arch)');
  console.log('  --skip-build          Reuse existing build outputs instead of rebuilding');
}

function parseArgs(argv) {
  const options = {
    sourceVersion: '',
    targetVersion: '',
    platform: isWin ? 'win32' : process.platform,
    arch: process.arch,
    skipBuild: false
  };

  for (const arg of argv) {
    if (!arg) {
      continue;
    }

    if (arg === '--help' || arg === '-h') {
      printUsage();
      process.exit(0);
    }

    if (arg === '--skip-build') {
      options.skipBuild = true;
      continue;
    }

    if (arg.startsWith('--source=')) {
      options.sourceVersion = normalizeVersion(arg.slice('--source='.length));
      continue;
    }

    if (arg.startsWith('--target=')) {
      options.targetVersion = normalizeVersion(arg.slice('--target='.length));
      continue;
    }

    if (arg.startsWith('--platform=')) {
      options.platform = String(arg.slice('--platform='.length)).trim();
      continue;
    }

    if (arg.startsWith('--arch=')) {
      options.arch = String(arg.slice('--arch='.length)).trim();
      continue;
    }

    if (!arg.startsWith('-') && !options.sourceVersion) {
      options.sourceVersion = normalizeVersion(arg);
      continue;
    }

    throw new Error(`Unknown argument: ${arg}`);
  }

  return options;
}

function promptSourceVersion() {
  return new Promise((resolve) => {
    const rl = readline.createInterface({
      input: process.stdin,
      output: process.stdout
    });

    rl.question('Enter source version: ', (answer) => {
      rl.close();
      resolve(normalizeVersion(answer));
    });
  });
}

function runCommand(command, args, description) {
  return new Promise((resolve, reject) => {
    console.log(`>>> ${description}`);
    const proc = spawn(command, args, {
      cwd: rootDir,
      stdio: 'inherit',
      shell: false
    });

    proc.on('error', reject);
    proc.on('close', (code) => {
      if (code !== 0) {
        reject(new Error(`${description} failed with exit code ${code}`));
        return;
      }

      resolve();
    });
  });
}

async function main() {
  printHeader();
  const options = parseArgs(process.argv.slice(2));

  let sourceVersion = normalizeVersion(options.sourceVersion);
  if (!sourceVersion) {
    if (!process.stdin.isTTY) {
      throw new Error('Missing source version. Run "npm run delta:build -- --source=<version>".');
    }

    sourceVersion = await promptSourceVersion();
  }

  if (!sourceVersion) {
    throw new Error('Source version is required.');
  }

  if (!options.skipBuild) {
    await runCommand(npmCommand, ['run', 'build'], 'Build current release');
  } else {
    console.log('>>> Skip build and reuse existing artifacts');
  }

  const archiveArgs = ['scripts/release/archive-release.js'];
  if (options.targetVersion) {
    archiveArgs.push(`--version=${options.targetVersion}`);
  }
  await runCommand(nodeCommand, archiveArgs, 'Archive current release artifacts');

  const deltaArgs = ['scripts/release/generate-delta.js', `--source=${sourceVersion}`];
  if (options.targetVersion) {
    deltaArgs.push(`--target=${options.targetVersion}`);
  }
  if (options.platform) {
    deltaArgs.push(`--platform=${options.platform}`);
  }
  if (options.arch) {
    deltaArgs.push(`--arch=${options.arch}`);
  }
  await runCommand(nodeCommand, deltaArgs, 'Generate delta package');
}

main().catch((error) => {
  console.error('');
  console.error(`[ERROR] ${error.message}`);
  process.exit(1);
});

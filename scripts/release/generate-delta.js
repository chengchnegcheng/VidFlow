const fs = require('fs');
const path = require('path');
const readline = require('readline');
const { spawn } = require('child_process');

const rootDir = path.join(__dirname, '..');
const backendDir = path.join(rootDir, 'backend');
const releasesDir = path.join(rootDir, 'releases');
const packageJsonPath = path.join(rootDir, 'package.json');

const isWin = process.platform === 'win32';
const pythonPath = isWin
  ? path.join(backendDir, 'venv', 'Scripts', 'python.exe')
  : path.join(backendDir, 'venv', 'bin', 'python');

function readPackageVersion() {
  const packageJson = JSON.parse(fs.readFileSync(packageJsonPath, 'utf8'));
  return String(packageJson.version || '').trim();
}

function normalizeVersion(value) {
  return String(value || '').trim().replace(/^v/i, '');
}

function compareVersions(a, b) {
  return a.localeCompare(b, undefined, { numeric: true, sensitivity: 'base' });
}

function getAvailableVersions(targetVersion) {
  if (!fs.existsSync(releasesDir)) {
    return [];
  }

  return fs
    .readdirSync(releasesDir, { withFileTypes: true })
    .filter((entry) => entry.isDirectory() && /^v/i.test(entry.name))
    .map((entry) => normalizeVersion(entry.name))
    .filter((version) => version && version !== targetVersion)
    .sort(compareVersions);
}

function printHeader(targetVersion) {
  console.log('');
  console.log('========================================');
  console.log('VidFlow Delta Package Generator');
  console.log('========================================');
  console.log(`Target version: ${targetVersion}`);
  console.log('');
}

function printUsage() {
  console.log('Usage:');
  console.log('  node scripts/generate-delta.js <sourceVersion>');
  console.log('  npm run delta -- <sourceVersion>');
  console.log('  npm run delta:list');
  console.log('');
  console.log('Options:');
  console.log('  --source=<version>    Source version');
  console.log('  --target=<version>    Target version (defaults to package.json version)');
  console.log('  --platform=<name>     Platform (defaults to current platform)');
  console.log('  --arch=<name>         Architecture (defaults to current arch)');
  console.log('  --list                List available source versions');
}

function printAvailableVersions(versions) {
  console.log('Available source versions:');
  if (versions.length === 0) {
    console.log('  (none found under releases/)');
    return;
  }

  versions.forEach((version) => {
    console.log(`  - ${version}`);
  });
}

function parseArgs(argv) {
  const options = {
    sourceVersion: '',
    targetVersion: readPackageVersion(),
    platform: isWin ? 'win32' : process.platform,
    arch: process.arch,
    listOnly: false
  };

  for (const arg of argv) {
    if (!arg) {
      continue;
    }

    if (arg === '--list') {
      options.listOnly = true;
      continue;
    }

    if (arg === '--help' || arg === '-h') {
      printUsage();
      process.exit(0);
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

function assertFileExists(filePath, description) {
  if (!fs.existsSync(filePath)) {
    throw new Error(`${description} not found: ${filePath}`);
  }
}

function promptSourceVersion(versions) {
  return new Promise((resolve) => {
    const rl = readline.createInterface({
      input: process.stdin,
      output: process.stdout
    });

    rl.question('Enter source version: ', (answer) => {
      rl.close();
      const normalized = normalizeVersion(answer);
      if (!normalized) {
        resolve('');
        return;
      }

      if (versions.length > 0 && !versions.includes(normalized)) {
        console.warn(`Warning: ${normalized} was not found in releases/, continuing anyway.`);
      }

      resolve(normalized);
    });
  });
}

function runGenerator({ sourceVersion, targetVersion, platform, arch }) {
  const sourceDir = path.join(releasesDir, `v${sourceVersion}`);
  const targetDir = path.join(releasesDir, `v${targetVersion}`);
  const deltasDir = path.join(releasesDir, 'deltas');

  assertFileExists(pythonPath, 'Python virtual environment');
  assertFileExists(sourceDir, 'Source release directory');
  assertFileExists(targetDir, 'Target release directory');

  fs.mkdirSync(deltasDir, { recursive: true });

  const env = {
    ...process.env,
    PYTHONPATH: [backendDir, process.env.PYTHONPATH].filter(Boolean).join(path.delimiter)
  };

  const args = [
    '-m',
    'src.core.delta_generator',
    sourceVersion,
    targetVersion,
    sourceDir,
    targetDir,
    platform,
    arch
  ];

  return new Promise((resolve, reject) => {
    const proc = spawn(pythonPath, args, {
      cwd: rootDir,
      env,
      stdio: 'inherit'
    });

    proc.on('error', reject);
    proc.on('close', (code) => {
      if (code !== 0) {
        reject(new Error(`Delta generator exited with code ${code}`));
        return;
      }

      resolve(path.join(deltasDir, `delta-${sourceVersion}-to-${targetVersion}-${platform}-${arch}.zip`));
    });
  });
}

async function main() {
  const options = parseArgs(process.argv.slice(2));
  const targetVersion = normalizeVersion(options.targetVersion);
  const versions = getAvailableVersions(targetVersion);

  printHeader(targetVersion);

  if (options.listOnly) {
    printAvailableVersions(versions);
    return;
  }

  let sourceVersion = normalizeVersion(options.sourceVersion);
  if (!sourceVersion) {
    printAvailableVersions(versions);
    console.log('');

    if (!process.stdin.isTTY) {
      throw new Error('Missing source version. Run "npm run delta -- <sourceVersion>".');
    }

    sourceVersion = await promptSourceVersion(versions);
  }

  if (!sourceVersion) {
    throw new Error('Source version is required.');
  }

  if (sourceVersion === targetVersion) {
    throw new Error('Source version and target version must be different.');
  }

  console.log(`Source version: ${sourceVersion}`);
  console.log(`Platform: ${options.platform}`);
  console.log(`Architecture: ${options.arch}`);
  console.log('');

  const deltaPath = await runGenerator({
    sourceVersion,
    targetVersion,
    platform: options.platform,
    arch: options.arch
  });

  console.log('');
  console.log('[OK] Delta package generated successfully');
  console.log(`Path: ${deltaPath}`);
}

main().catch((error) => {
  console.error('');
  console.error(`[ERROR] ${error.message}`);
  process.exit(1);
});

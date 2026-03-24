const fs = require('fs');
const path = require('path');

const rootDir = path.join(__dirname, '..');
const packageJsonPath = path.join(rootDir, 'package.json');
const distOutputDir = path.join(rootDir, 'dist-output');
const backendOutputDir = path.join(rootDir, 'backend', 'dist', 'VidFlow-Backend');
const frontendOutputDir = path.join(rootDir, 'frontend', 'dist');
const releasesDir = path.join(rootDir, 'releases');

function readPackageVersion() {
  const packageJson = JSON.parse(fs.readFileSync(packageJsonPath, 'utf8'));
  return String(packageJson.version || '').trim();
}

function normalizeVersion(value) {
  return String(value || '').trim().replace(/^v/i, '');
}

function printUsage() {
  console.log('Usage:');
  console.log('  node scripts/archive-release.js');
  console.log('  node scripts/archive-release.js --version=1.0.0');
}

function parseArgs(argv) {
  const options = {
    version: readPackageVersion()
  };

  for (const arg of argv) {
    if (!arg) {
      continue;
    }

    if (arg === '--help' || arg === '-h') {
      printUsage();
      process.exit(0);
    }

    if (arg.startsWith('--version=')) {
      options.version = normalizeVersion(arg.slice('--version='.length));
      continue;
    }

    if (!arg.startsWith('-') && !options.version) {
      options.version = normalizeVersion(arg);
      continue;
    }

    throw new Error(`Unknown argument: ${arg}`);
  }

  return options;
}

function assertPathExists(targetPath, description) {
  if (!fs.existsSync(targetPath)) {
    throw new Error(`${description} not found: ${targetPath}`);
  }
}

function findInstaller(version) {
  const candidates = [
    path.join(distOutputDir, `VidFlow Setup ${version}.exe`),
    path.join(distOutputDir, `VidFlow-Setup-${version}.exe`)
  ];

  for (const candidate of candidates) {
    if (fs.existsSync(candidate)) {
      return candidate;
    }
  }

  if (!fs.existsSync(distOutputDir)) {
    throw new Error(`Installer output directory not found: ${distOutputDir}`);
  }

  const installers = fs
    .readdirSync(distOutputDir)
    .filter((fileName) => fileName.toLowerCase().endsWith('.exe') && fileName.includes(version));

  if (installers.length === 1) {
    return path.join(distOutputDir, installers[0]);
  }

  throw new Error(`Installer for version ${version} not found in ${distOutputDir}`);
}

function copyDirectory(sourceDir, targetDir) {
  fs.mkdirSync(path.dirname(targetDir), { recursive: true });
  fs.cpSync(sourceDir, targetDir, { recursive: true, force: true });
}

function formatBytes(bytes) {
  return `${(bytes / 1024 / 1024).toFixed(2)} MB`;
}

function getDirectorySize(directory) {
  let size = 0;

  for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
    const entryPath = path.join(directory, entry.name);
    if (entry.isDirectory()) {
      size += getDirectorySize(entryPath);
    } else if (entry.isFile()) {
      size += fs.statSync(entryPath).size;
    }
  }

  return size;
}

function main() {
  const options = parseArgs(process.argv.slice(2));
  const version = normalizeVersion(options.version);

  if (!version) {
    throw new Error('Version is required.');
  }

  const installerPath = findInstaller(version);
  assertPathExists(backendOutputDir, 'Backend output directory');
  assertPathExists(frontendOutputDir, 'Frontend output directory');

  const releaseDir = path.join(releasesDir, `v${version}`);
  const targetBackendDir = path.join(releaseDir, 'VidFlow-Backend');
  const targetFrontendDir = path.join(releaseDir, 'frontend', 'dist');

  console.log('');
  console.log('========================================');
  console.log('VidFlow Release Archive');
  console.log('========================================');
  console.log(`Version: ${version}`);
  console.log(`Target directory: ${releaseDir}`);
  console.log('');

  // Always rebuild the release snapshot from scratch to avoid stale files.
  fs.rmSync(releaseDir, { recursive: true, force: true });
  fs.mkdirSync(releaseDir, { recursive: true });

  const installerFileName = path.basename(installerPath);
  const targetInstallerPath = path.join(releaseDir, installerFileName);

  fs.copyFileSync(installerPath, targetInstallerPath);
  copyDirectory(backendOutputDir, targetBackendDir);
  copyDirectory(frontendOutputDir, targetFrontendDir);

  console.log(`[OK] Installer: ${targetInstallerPath}`);
  console.log(`[OK] Backend: ${targetBackendDir}`);
  console.log(`[OK] Frontend: ${targetFrontendDir}`);
  console.log('');
  console.log(`Installer size: ${formatBytes(fs.statSync(targetInstallerPath).size)}`);
  console.log(`Backend size: ${formatBytes(getDirectorySize(targetBackendDir))}`);
  console.log(`Frontend size: ${formatBytes(getDirectorySize(targetFrontendDir))}`);
}

try {
  main();
} catch (error) {
  console.error('');
  console.error(`[ERROR] ${error.message}`);
  process.exit(1);
}

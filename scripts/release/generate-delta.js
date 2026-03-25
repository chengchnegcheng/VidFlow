const fs = require('fs');
const path = require('path');
const readline = require('readline');
const { spawn } = require('child_process');

const rootDir = path.join(__dirname, '..', '..');
const backendDir = path.join(rootDir, 'backend');
const releasesDir = path.join(rootDir, 'releases');
const distOutputDir = path.join(rootDir, 'dist-output');
const packageJsonPath = path.join(rootDir, 'package.json');

const isWin = process.platform === 'win32';
const nodeCommand = process.execPath;
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
  console.log('VidFlow 增量更新包生成工具');
  console.log('========================================');
  console.log(`目标版本: ${targetVersion}`);
  console.log('');
}

function printUsage() {
  console.log('用法:');
  console.log('  node scripts/release/generate-delta.js <sourceVersion>');
  console.log('  npm run delta -- <sourceVersion>');
  console.log('  npm run delta:list');
  console.log('');
  console.log('参数:');
  console.log('  --source=<version>    源版本号');
  console.log('  --target=<version>    目标版本号，默认使用 package.json 中的版本');
  console.log('  --platform=<name>     平台，默认使用当前平台');
  console.log('  --arch=<name>         架构，默认自动识别目标安装包架构');
  console.log('  --list                列出可用的源版本');
}

function printAvailableVersions(versions) {
  console.log('可用的源版本:');
  if (versions.length === 0) {
    console.log('  （在 releases/ 下未找到可用版本）');
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
    arch: '',
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

    throw new Error(`未知参数: ${arg}`);
  }

  return options;
}

function assertFileExists(filePath, description) {
  if (!fs.existsSync(filePath)) {
    throw new Error(`${description}不存在: ${filePath}`);
  }
}

function normalizeDetectedArch(value) {
  const normalized = String(value || '').trim().toLowerCase();
  if (!normalized) return '';

  if (['x64', 'x86_64', 'amd64'].includes(normalized)) return 'x64';
  if (['arm64', 'aarch64'].includes(normalized)) return 'arm64';
  if (['x32', 'x86', 'ia32', 'i386', 'i686'].includes(normalized)) return 'x32';
  return '';
}

function detectArchFromFilename(fileName) {
  const normalized = String(fileName || '').trim().toLowerCase();
  if (!normalized) return '';

  const patterns = [
    ['arm64', /(?:^|[^a-z0-9])(arm64|aarch64)(?=[^a-z0-9]|$)/i],
    ['x64', /(?:^|[^a-z0-9])(x64|x86_64|amd64)(?=[^a-z0-9]|$)/i],
    ['x32', /(?:^|[^a-z0-9])(x32|x86|ia32|i386|i686)(?=[^a-z0-9]|$)/i]
  ];

  for (const [arch, pattern] of patterns) {
    if (pattern.test(normalized)) {
      return arch;
    }
  }

  return '';
}

function detectArchFromWindowsExecutable(filePath) {
  const fd = fs.openSync(filePath, 'r');
  try {
    const header = Buffer.alloc(4096);
    const bytesRead = fs.readSync(fd, header, 0, header.length, 0);
    if (bytesRead < 64 || header.readUInt16LE(0) !== 0x5a4d) {
      return '';
    }

    const peOffset = header.readUInt32LE(0x3c);
    if (peOffset + 6 > bytesRead || header.readUInt32LE(peOffset) !== 0x00004550) {
      return '';
    }

    const machine = header.readUInt16LE(peOffset + 4);
    if (machine === 0x8664) return 'x64';
    if (machine === 0xaa64) return 'arm64';
    if (machine === 0x014c) return 'x32';
    return '';
  } finally {
    fs.closeSync(fd);
  }
}

function findInstallerCandidates(version, platform) {
  const releaseDir = path.join(releasesDir, `v${version}`);
  const searchDirs = [releaseDir, distOutputDir].filter((dirPath) => fs.existsSync(dirPath));
  const extensions = {
    win32: ['.exe', '.msi'],
    darwin: ['.dmg', '.pkg'],
    linux: ['.deb', '.rpm', '.appimage']
  };
  const allowedExts = extensions[platform] || [];
  const versionToken = normalizeVersion(version).toLowerCase();
  const matches = [];

  for (const dirPath of searchDirs) {
    for (const entry of fs.readdirSync(dirPath, { withFileTypes: true })) {
      if (!entry.isFile()) {
        continue;
      }

      const ext = path.extname(entry.name).toLowerCase();
      if (allowedExts.length > 0 && !allowedExts.includes(ext)) {
        continue;
      }

      if (!entry.name.toLowerCase().includes(versionToken)) {
        continue;
      }

      matches.push(path.join(dirPath, entry.name));
    }
  }

  return matches;
}

function resolveArch(targetVersion, platform, requestedArch) {
  const normalizedRequestedArch = normalizeDetectedArch(requestedArch);
  if (normalizedRequestedArch) {
    return normalizedRequestedArch;
  }

  const candidates = findInstallerCandidates(targetVersion, platform);
  for (const candidate of candidates) {
    let detectedArch = '';

    if (platform === 'win32') {
      detectedArch = detectArchFromWindowsExecutable(candidate);
    }

    if (!detectedArch) {
      detectedArch = detectArchFromFilename(path.basename(candidate));
    }

    if (detectedArch) {
      console.log(`[信息] 自动识别架构: ${detectedArch} (${path.basename(candidate)})`);
      return detectedArch;
    }
  }

  const fallbackArch = normalizeDetectedArch(process.arch) || process.arch;
  console.log(`[信息] 无法从安装包识别架构，回退到当前环境架构: ${fallbackArch}`);
  return fallbackArch;
}

function runNodeScript(args, description) {
  return new Promise((resolve, reject) => {
    console.log(`[信息] ${description}`);
    const proc = spawn(nodeCommand, args, {
      cwd: rootDir,
      stdio: 'inherit'
    });

    proc.on('error', reject);
    proc.on('close', (code) => {
      if (code !== 0) {
        reject(new Error(`${description}失败，退出码: ${code}`));
        return;
      }

      resolve();
    });
  });
}

async function ensureTargetReleaseSnapshot(targetVersion) {
  const targetDir = path.join(releasesDir, `v${targetVersion}`);
  if (fs.existsSync(targetDir)) {
    return;
  }

  console.log(`[信息] 未找到目标版本快照，正在自动归档 v${targetVersion} ...`);
  await runNodeScript(['scripts/release/archive-release.js', `--version=${targetVersion}`], '归档当前版本产物');
}

function promptSourceVersion(versions) {
  return new Promise((resolve) => {
    const rl = readline.createInterface({
      input: process.stdin,
      output: process.stdout
    });

    rl.question('请输入源版本号: ', (answer) => {
      rl.close();
      const normalized = normalizeVersion(answer);
      if (!normalized) {
        resolve('');
        return;
      }

      if (versions.length > 0 && !versions.includes(normalized)) {
        console.warn(`警告: 在 releases/ 中未找到 ${normalized}，仍将继续执行。`);
      }

      resolve(normalized);
    });
  });
}

function runGenerator({ sourceVersion, targetVersion, platform, arch }) {
  const sourceDir = path.join(releasesDir, `v${sourceVersion}`);
  const targetDir = path.join(releasesDir, `v${targetVersion}`);
  const deltasDir = path.join(releasesDir, 'deltas');

  assertFileExists(pythonPath, 'Python 虚拟环境');
  assertFileExists(sourceDir, '源版本目录');
  assertFileExists(targetDir, '目标版本目录');

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
        reject(new Error(`增量包生成器退出，返回码: ${code}`));
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
      throw new Error('缺少源版本号。请运行 "npm run delta -- <sourceVersion>"。');
    }

    sourceVersion = await promptSourceVersion(versions);
  }

  if (!sourceVersion) {
    throw new Error('必须提供源版本号。');
  }

  if (sourceVersion === targetVersion) {
    throw new Error('源版本号和目标版本号不能相同。');
  }

  await ensureTargetReleaseSnapshot(targetVersion);

  const effectiveArch = resolveArch(targetVersion, options.platform, options.arch);

  console.log(`源版本: ${sourceVersion}`);
  console.log(`平台: ${options.platform}`);
  console.log(`架构: ${effectiveArch}`);
  console.log('');

  const deltaPath = await runGenerator({
    sourceVersion,
    targetVersion,
    platform: options.platform,
    arch: effectiveArch
  });

  console.log('');
  console.log('[完成] 增量更新包生成成功。');
  console.log(`路径: ${deltaPath}`);
}

main().catch((error) => {
  console.error('');
  console.error(`[错误] ${error.message}`);
  process.exit(1);
});
const fs = require('fs');
const path = require('path');
const readline = require('readline');
const { spawn } = require('child_process');

const rootDir = path.join(__dirname, '..', '..');
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
  console.log('  --arch=<name>         架构，默认使用当前架构');
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

    throw new Error(`未知参数: ${arg}`);
  }

  return options;
}

function assertFileExists(filePath, description) {
  if (!fs.existsSync(filePath)) {
    throw new Error(`${description}不存在: ${filePath}`);
  }
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

  console.log(`源版本: ${sourceVersion}`);
  console.log(`平台: ${options.platform}`);
  console.log(`架构: ${options.arch}`);
  console.log('');

  const deltaPath = await runGenerator({
    sourceVersion,
    targetVersion,
    platform: options.platform,
    arch: options.arch
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
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
  console.log('VidFlow 构建并生成增量包');
  console.log('========================================');
  console.log('');
}

function printUsage() {
  console.log('用法:');
  console.log('  node scripts/release/build-and-generate-delta.js --source=1.0.2');
  console.log('  npm run delta:build -- --source=1.0.2');
  console.log('');
  console.log('参数:');
  console.log('  --source=<version>    增量包的源版本号');
  console.log('  --target=<version>    目标版本号，默认使用 package.json 中的版本');
  console.log('  --platform=<name>     平台，默认使用当前平台');
  console.log('  --arch=<name>         架构，默认使用当前架构');
  console.log('  --skip-build          跳过重新构建，直接复用现有产物');
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

    throw new Error(`未知参数: ${arg}`);
  }

  return options;
}

function promptSourceVersion() {
  return new Promise((resolve) => {
    const rl = readline.createInterface({
      input: process.stdin,
      output: process.stdout
    });

    rl.question('请输入源版本号: ', (answer) => {
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
        reject(new Error(`${description}失败，退出码: ${code}`));
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
      throw new Error('缺少源版本号。请运行 "npm run delta:build -- --source=<version>"。');
    }

    sourceVersion = await promptSourceVersion();
  }

  if (!sourceVersion) {
    throw new Error('必须提供源版本号。');
  }

  if (!options.skipBuild) {
    await runCommand(npmCommand, ['run', 'build'], '构建当前版本');
  } else {
    console.log('>>> 跳过构建，直接复用现有产物');
  }

  const archiveArgs = ['scripts/release/archive-release.js'];
  if (options.targetVersion) {
    archiveArgs.push(`--version=${options.targetVersion}`);
  }
  await runCommand(nodeCommand, archiveArgs, '归档当前版本产物');

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
  await runCommand(nodeCommand, deltaArgs, '生成增量更新包');
}

main().catch((error) => {
  console.error('');
  console.error(`[错误] ${error.message}`);
  process.exit(1);
});
/**
 * 开发模式启动脚本
 * 自动启动 Python 后端和前端开发服务器
 */
const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');

const rootDir = path.join(__dirname, '..');
const backendDir = path.join(rootDir, 'backend');
const frontendDir = path.join(rootDir, 'frontend');

console.log('🚀 Starting VidFlow Development Mode...\n');

// 检查 Python 虚拟环境
const venvPath = path.join(backendDir, 'venv');
if (!fs.existsSync(venvPath)) {
  console.log('⚠️  Python virtual environment not found!');
  console.log('📝 Please run the following commands first:');
  console.log('   cd backend');
  console.log('   python -m venv venv');
  console.log('   source venv/bin/activate  # Windows: venv\\Scripts\\activate');
  console.log('   pip install -r requirements.txt');
  process.exit(1);
}

// 启动 Python 后端
console.log('🐍 Starting Python backend...');
const pythonPath = process.platform === 'win32' 
  ? path.join(venvPath, 'Scripts', 'python.exe')
  : path.join(venvPath, 'bin', 'python');

const pythonProcess = spawn(pythonPath, ['src/main.py'], {
  cwd: backendDir,
  stdio: 'inherit'
});

// 等待 2 秒让后端启动
setTimeout(() => {
  console.log('\n⚛️  Starting React frontend...');
  
  // 启动前端开发服务器
  const frontendProcess = spawn('npm', ['run', 'dev'], {
    cwd: frontendDir,
    stdio: 'inherit',
    shell: true
  });

  // 等待 3 秒后启动 Electron
  setTimeout(() => {
    console.log('\n🖥️  Starting Electron...');
    
    const electronProcess = spawn('npm', ['run', 'electron:dev'], {
      cwd: rootDir,
      stdio: 'inherit',
      shell: true
    });

    // 处理进程退出
    electronProcess.on('exit', () => {
      console.log('\n👋 Stopping all processes...');
      pythonProcess.kill();
      frontendProcess.kill();
      process.exit(0);
    });
  }, 3000);
}, 2000);

// 处理 Ctrl+C
process.on('SIGINT', () => {
  console.log('\n👋 Stopping all processes...');
  process.exit(0);
});

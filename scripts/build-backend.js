const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');

const rootDir = path.join(__dirname, '..');
const backendDir = path.join(rootDir, 'backend');

const isWin = process.platform === 'win32';
const pythonPath = isWin
  ? path.join(backendDir, 'venv', 'Scripts', 'python.exe')
  : path.join(backendDir, 'venv', 'bin', 'python');

if (!fs.existsSync(pythonPath)) {
  console.error(`[ERROR] Python virtual environment not found: ${pythonPath}`);
  console.error('Create it in backend/ and install dependencies first.');
  process.exit(1);
}

const args = ['-m', 'PyInstaller', 'backend.spec', '--clean', '--noconfirm'];

console.log(`Building backend using: ${pythonPath}`);
console.log(`Working directory: ${backendDir}`);

const proc = spawn(pythonPath, args, {
  cwd: backendDir,
  stdio: 'inherit'
});

proc.on('error', (err) => {
  console.error('[ERROR] Failed to start backend build process:', err);
  process.exit(1);
});

proc.on('close', (code) => {
  if (code !== 0) {
    console.error(`[ERROR] Backend build failed with exit code ${code}`);
    process.exit(code);
  }
  console.log('Backend build completed successfully');
});

"""
下载 Python 3.11 嵌入式版本并配置 pip
"""
import urllib.request
import zipfile
import os
from pathlib import Path
import subprocess

PYTHON_VERSION = "3.11.9"
PYTHON_URL = f"https://www.python.org/ftp/python/{PYTHON_VERSION}/python-{PYTHON_VERSION}-embed-amd64.zip"
PYTHON_DIR = Path(__file__).parent / "python_embedded"
GET_PIP_URL = "https://bootstrap.pypa.io/get-pip.py"

def download_file(url, dest):
    print(f"Downloading {url}...")
    urllib.request.urlretrieve(url, dest)
    print(f"Downloaded to {dest}")

def main():
    # 创建目录
    PYTHON_DIR.mkdir(exist_ok=True)

    # 下载 Python 嵌入式版本
    zip_path = PYTHON_DIR / "python.zip"
    if not zip_path.exists():
        download_file(PYTHON_URL, zip_path)

    # 解压
    print("Extracting Python...")
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(PYTHON_DIR)

    # 删除 zip 文件
    zip_path.unlink()

    # 修改 python311._pth 以启用 site-packages
    pth_file = PYTHON_DIR / f"python{PYTHON_VERSION.replace('.', '')[:3]}._pth"
    if pth_file.exists():
        content = pth_file.read_text()
        if "#import site" in content:
            content = content.replace("#import site", "import site")
            pth_file.write_text(content)
            print("Enabled site-packages")

    # 下载 get-pip.py
    get_pip_path = PYTHON_DIR / "get-pip.py"
    download_file(GET_PIP_URL, get_pip_path)

    # 安装 pip
    python_exe = PYTHON_DIR / "python.exe"
    print("Installing pip...")
    subprocess.run([str(python_exe), str(get_pip_path)], check=True)

    # 清理
    get_pip_path.unlink()

    print(f"\n✅ Python 3.11 嵌入式版本已安装到: {PYTHON_DIR}")
    print(f"Python 可执行文件: {python_exe}")

if __name__ == "__main__":
    main()

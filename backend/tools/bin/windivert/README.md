# WinDivert Driver Files

此目录用于存放 WinDivert 驱动文件，用于 Windows 透明流量捕获功能。

## 所需文件

请从 [WinDivert 官方发布页](https://github.com/basil00/WinDivert/releases) 下载最新版本，并将以下文件放置到此目录：

- `WinDivert.dll` - WinDivert 动态链接库
- `WinDivert64.sys` - 64位 WinDivert 内核驱动
- `WinDivert32.sys` - 32位 WinDivert 内核驱动（可选，仅 32 位系统需要）

## 版本要求

- WinDivert >= 2.2.0
- 支持 Windows 10/11

## 注意事项

1. 使用透明捕获功能需要管理员权限
2. 首次使用时系统可能提示安装驱动
3. 部分杀毒软件可能误报，请添加信任

## 下载链接

- GitHub: https://github.com/basil00/WinDivert/releases
- 推荐版本: WinDivert-2.2.2-A.zip

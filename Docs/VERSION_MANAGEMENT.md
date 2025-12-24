# VidFlow Desktop 版本号管理

## 📦 版本号管理工具

提供了 3 种方式来管理版本号：

### 1. 交互式脚本（推荐）

**`scripts\VERSION.bat`** - 功能最全面的版本管理工具

```bash
scripts\VERSION.bat
```

**功能：**
- ✅ 修改版本号
- ✅ 快速升级（主版本/次版本/修订版）
- ✅ 查看详细信息
- ✅ 生成更新日志模板

### 2. 快速命令行脚本

**`scripts\SET_VERSION.bat`** - 命令行快速设置

```bash
# 设置为指定版本
scripts\SET_VERSION.bat 1.1.0

# 不带参数时显示当前版本和用法
scripts\SET_VERSION.bat
```

### 3. PowerShell 脚本（跨平台）

**`scripts\set-version.ps1`** - PowerShell 版本

```powershell
# 指定版本
.\scripts\set-version.ps1 -Version "1.1.0"

# 快速升级
.\scripts\set-version.ps1 -Bump major   # 主版本
.\scripts\set-version.ps1 -Bump minor   # 次版本
.\scripts\set-version.ps1 -Bump patch   # 修订版

# 交互模式
.\scripts\set-version.ps1
```

---

## 📋 使用场景

### 场景 1：准备发布新版本

```bash
# 1. 运行交互式脚本
scripts\VERSION.bat

# 2. 选择 [1] 修改版本号
# 3. 输入新版本：1.1.0
# 4. 确认修改
```

### 场景 2：修复 bug 发布

```bash
# 快速升级修订版 (1.0.0 → 1.0.1)
scripts\SET_VERSION.bat 1.0.1

# 或使用 PowerShell
powershell -File scripts\set-version.ps1 -Bump patch
```

### 场景 3：新功能发布

```bash
# 快速升级次版本 (1.0.0 → 1.1.0)
powershell -File scripts\set-version.ps1 -Bump minor
```

### 场景 4：重大更新

```bash
# 快速升级主版本 (1.0.0 → 2.0.0)
powershell -File scripts\set-version.ps1 -Bump major
```

---

## 🎯 版本号规则（语义化版本）

格式：`主版本.次版本.修订版` (例如：`1.2.3`)

### 主版本（Major）
- **何时升级**：重大更新、破坏性变更
- **示例**：1.0.0 → 2.0.0
- **场景**：
  - 重写核心功能
  - API 不兼容
  - 架构重构

### 次版本（Minor）
- **何时升级**：新增功能、向后兼容
- **示例**：1.0.0 → 1.1.0
- **场景**：
  - 添加新功能
  - 性能优化
  - UI 改进

### 修订版（Patch）
- **何时升级**：bug 修复
- **示例**：1.0.0 → 1.0.1
- **场景**：
  - 修复 bug
  - 小问题改进
  - 文档更新

---

## 📝 版本发布流程

### 完整流程

1. **确定版本号**
   ```bash
   scripts\VERSION.bat
   # 选择 [2] 快速升级
   ```

2. **生成更新日志**
   ```bash
   scripts\VERSION.bat
   # 选择 [4] 生成更新日志模板
   # 编辑生成的 CHANGELOG_x.x.x.md
   ```

3. **提交代码**
   ```bash
   git add package.json frontend/package.json
   git commit -m "chore: bump version to 1.1.0"
   git tag v1.1.0
   ```

4. **构建发布**
   ```bash
   scripts\BUILD_RELEASE.bat
   # 选择 [1] 完整构建
   ```

5. **测试安装包**
   - 运行生成的 .exe
   - 测试所有功能
   - 验证版本号显示

6. **上传到服务器**
   ```bash
   # 计算 SHA-512
   scripts\BUILD_RELEASE.bat
   # 选择 [6] 计算安装包 SHA-512
   
   # 上传文件到更新服务器
   # 配置更新服务器 API
   ```

7. **推送 Git**
   ```bash
   git push origin main
   git push origin v1.1.0
   ```

---

## 🔄 版本修改影响的文件

脚本会自动修改以下文件：

- ✅ `package.json` - Electron 应用版本
- ✅ `frontend/package.json` - 前端应用版本

**验证修改**：
```bash
# 查看修改
git diff

# 确认版本号
findstr "version" package.json
findstr "version" frontend\package.json
```

---

## 💡 提示和技巧

### 1. 版本号验证

所有脚本都会验证版本号格式：
```
✅ 正确：1.0.0, 2.5.3, 10.20.30
❌ 错误：v1.0.0, 1.0, 1.0.0-beta
```

### 2. 回滚版本

如果需要回滚：
```bash
git checkout HEAD -- package.json frontend/package.json
```

### 3. 批量操作

在 CI/CD 中使用：
```bash
# 自动升级修订版
scripts\SET_VERSION.bat 1.0.1

# 构建
scripts\BUILD_RELEASE.bat
```

### 4. 查看历史版本

```bash
git log --oneline --decorate --tags
```

---

## 🎨 版本号示例

### 开发阶段
```
0.1.0 - 初始开发版本
0.2.0 - 添加基础功能
0.9.0 - 测试版本
0.9.1 - 修复测试问题
```

### 正式发布
```
1.0.0 - 首次正式发布
1.0.1 - 修复 bug
1.1.0 - 添加新功能
2.0.0 - 重大更新
```

---

## 🛠️ 高级用法

### 与 Git 标签结合

```bash
# 设置版本号
scripts\SET_VERSION.bat 1.1.0

# 创建 Git 标签
git tag -a v1.1.0 -m "Release version 1.1.0"

# 推送标签
git push origin v1.1.0
```

### 自动化脚本示例

```batch
@echo off
REM 自动发布脚本

echo [1/5] 设置版本号...
call scripts\SET_VERSION.bat %1

echo [2/5] 构建应用...
call scripts\BUILD_RELEASE.bat

echo [3/5] 创建 Git 标签...
git tag v%1

echo [4/5] 提交更改...
git add .
git commit -m "Release v%1"

echo [5/5] 推送到远程...
git push origin main
git push origin v%1

echo 完成！
```

---

## 📚 相关文档

- [UPDATE_TESTING_GUIDE.md](UPDATE_TESTING_GUIDE.md) - 更新测试指南
- [UPDATE_IMPLEMENTATION_SUMMARY.md](UPDATE_IMPLEMENTATION_SUMMARY.md) - 更新实施总结

---

## 🤔 常见问题

### Q: 修改版本号后需要重新安装依赖吗？

A: 不需要，版本号只影响显示和打包。

### Q: 可以使用带 beta 的版本号吗？

A: 目前脚本只支持标准的 x.y.z 格式。如需 beta 版本，需手动修改。

### Q: 前端和后端版本号必须一致吗？

A: 推荐保持一致，脚本会同步修改两个文件。

### Q: 版本号会影响更新检测吗？

A: 会！更新器会比较版本号，较低版本会提示更新。

---

**最后更新**: 2025-11-04  
**维护者**: VidFlow Team


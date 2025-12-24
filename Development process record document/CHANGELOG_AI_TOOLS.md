# AI 工具按需安装 - 实施总结

**实施日期**：2025-10-31  
**版本**：VidFlow 3.1.0

---

## 🎯 实施目标

将 **faster-whisper AI 字幕生成功能** 从打包体积中移除，改为**按需安装的可选工具**，像 FFmpeg 和 yt-dlp 一样通过应用内工具管理安装。

---

## ✅ 已完成的修改

### 1. 后端工具管理器扩展

**文件**：`backend/src/core/tool_manager.py`

**新增方法**：
- `check_ai_tools_status()` - 检查 AI 工具状态（faster-whisper + PyTorch）
- `install_ai_tools(version, progress_callback)` - 安装 AI 工具（支持 CPU/CUDA 版本）
- `uninstall_ai_tools()` - 卸载 AI 工具
- `get_ai_tool_info(version)` - 获取 AI 工具信息

**特性**：
- ✅ 完整的版本检测（Python 兼容性、torch、faster-whisper）
- ✅ 进度回调支持（WebSocket 实时反馈）
- ✅ 错误处理和详细日志
- ✅ 兼容旧接口（`check_faster_whisper()`, `install_faster_whisper()`）

---

### 2. API 端点添加

**文件**：`backend/src/api/system.py`

**新增端点**：

| 端点 | 方法 | 功能 |
|------|------|------|
| `/tools/ai/status` | GET | 检查 AI 工具状态 |
| `/tools/ai/info` | GET | 获取 AI 工具信息 |
| `/tools/ai/install` | POST | 安装 AI 工具 |
| `/tools/ai/uninstall` | POST | 卸载 AI 工具 |

**示例请求**：
```bash
# 检查状态
GET /api/system/tools/ai/status

# 安装 CPU 版本
POST /api/system/tools/ai/install?version=cpu

# 卸载
POST /api/system/tools/ai/uninstall
```

---

### 3. 打包配置修改

**文件**：`backend/backend.spec`

**变更内容**：
```python
# 移除 faster_whisper 从 hiddenimports
hiddenimports = [
    # ...
    # 'faster_whisper',  # 已移除
]

# 新增 excludes 列表
excludes = [
    'torch',
    'torchvision',
    'torchaudio',
    'faster_whisper',
    'ctranslate2',
    'onnxruntime',
    'matplotlib',
    'scipy',
    'pandas',
]
```

**效果**：
- ✅ 排除 AI 相关依赖
- ✅ 预计减小打包体积 **60-70%**（从 ~2 GB 降到 ~500 MB）

---

### 4. 安装脚本更新

**文件**：`scripts/SETUP.bat`

**变更**：
- ❌ 移除 faster-whisper 自动安装（第 263-325 行）
- ✅ 添加按需安装提示
- ✅ Python 版本兼容性检查
- ✅ 引导用户在应用内安装

**新提示内容**：
```
[INFO] AI 字幕功能现已改为可选安装

如需使用 AI 字幕生成功能：
  1. 启动应用后，进入"设置" → "工具管理"
  2. 点击"安装 AI 字幕工具"
  3. 选择版本（推荐 CPU 版本，约 300 MB）
```

---

### 5. 文档创建

**新增文档**：
1. **AI_TOOLS_GUIDE.md** - 完整使用指南
   - API 文档
   - 前端集成示例
   - 常见问题解答
   - 开发者指南

2. **CHANGELOG_AI_TOOLS.md** - 本文档

---

## 📊 效果对比

### 打包体积

| 项目 | 旧版本 | 新版本 | 改善 |
|------|--------|--------|------|
| **基础包** | ~2 GB | **~500 MB** | -75% ⭐ |
| **AI 工具（可选）** | 已包含 | ~300 MB（CPU）| 按需 |
| **总计（完整）** | ~2 GB | ~800 MB | -60% |

### 用户体验

| 场景 | 旧版本 | 新版本 |
|------|--------|--------|
| **下载基础版** | 慢（2 GB）| **快（500 MB）** ⭐ |
| **安装时间** | 长 | **短** ⭐ |
| **不需要 AI** | 浪费空间 | **节省空间** ⭐ |
| **首次使用 AI** | 即用 | 需手动安装 |

### 开发维护

| 方面 | 旧版本 | 新版本 |
|------|--------|--------|
| **打包时间** | 慢 | **快** ⭐ |
| **AI 更新** | 需重新打包 | **独立更新** ⭐ |
| **测试** | 耦合 | **独立测试** ⭐ |

---

## 🔄 迁移指南

### 对于用户

**如果已安装旧版本**：
1. 卸载旧版本（可选）
2. 安装新版本（~500 MB）
3. 首次使用字幕功能时，会提示安装 AI 工具
4. 选择版本后等待安装（3-5 分钟）

**如果是新用户**：
1. 下载安装 VidFlow（~500 MB）
2. 根据需要决定是否安装 AI 功能
3. 在设置→工具管理中安装

### 对于开发者

**前端开发**：
1. 在字幕功能中添加 AI 工具检测：
   ```typescript
   const aiStatus = await fetch('/api/system/tools/ai/status');
   if (!aiStatus.installed) {
     // 提示用户安装
   }
   ```

2. 在设置页面添加工具管理卡片（参考 AI_TOOLS_GUIDE.md）

**后端开发**：
- 无需修改现有代码
- 新的 API 端点已添加
- 旧接口保持兼容

---

## ⚠️ 注意事项

### 1. 兼容性

- ✅ 向后兼容：旧的 API 接口仍然可用
- ✅ Python 版本：自动检测并警告不兼容版本
- ✅ 错误处理：详细的错误信息和解决建议

### 2. 测试建议

**打包测试**：
```bash
# 1. 清理旧文件
scripts\CLEAN.bat

# 2. 重新安装依赖（不含 AI）
scripts\SETUP.bat

# 3. 打包
scripts\BUILD_AUTO.bat

# 4. 检查体积
dir dist-output\*.exe
# 预期：~500 MB

# 5. 测试安装包
# - 基础功能正常
# - 字幕功能提示安装
# - AI 工具可正常安装/卸载
```

**功能测试**：
1. 基础功能（视频下载、管理）→ 应正常
2. 字幕功能未安装 AI → 应提示安装
3. 安装 AI 工具 → 应成功并可用
4. 生成字幕 → 应正常工作
5. 卸载 AI 工具 → 应成功移除

### 3. 已知问题

无（目前）

---

## 🎯 后续工作

### 前端实现（待完成）

1. **设置页面**：
   - [ ] 添加"工具管理"标签页
   - [ ] 实现 AI 工具卡片组件
   - [ ] 显示安装状态和进度
   - [ ] 版本选择（CPU/GPU）

2. **字幕功能**：
   - [ ] 添加 AI 工具状态检测
   - [ ] 未安装时显示友好提示
   - [ ] 提供"前往安装"快捷入口

3. **用户体验**：
   - [ ] 安装进度显示（WebSocket）
   - [ ] 错误提示优化
   - [ ] 安装完成通知

### 文档完善

- [ ] 更新用户手册
- [ ] 添加视频教程
- [ ] FAQ 更新

### 测试覆盖

- [ ] 单元测试（API 端点）
- [ ] 集成测试（安装流程）
- [ ] 端到端测试（用户场景）

---

## 📚 相关文档

- [AI_TOOLS_GUIDE.md](./AI_TOOLS_GUIDE.md) - AI 工具使用指南
- [PACKAGE_OPTIMIZATION.md](./PACKAGE_OPTIMIZATION.md) - 打包优化指南
- [scripts/BUILD_README.md](./scripts/BUILD_README.md) - 构建脚本说明

---

## 🙏 致谢

感谢团队成员的贡献和用户的反馈，使得这次优化得以顺利实施。

---

**实施状态**：✅ 后端完成  
**待完成**：前端 UI 实现  
**预计发布**：VidFlow 3.1.0

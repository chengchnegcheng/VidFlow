# 死代码分析报告

生成时间: 2026-01-24

## 执行摘要

本报告基于以下工具的分析结果：
- **depcheck**: 检测未使用的依赖包
- **knip**: 全面的死代码检测
- **ts-prune**: TypeScript 未使用导出检测

---

## 🟢 SAFE - 安全删除项

这些项目可以安全删除，不会影响应用功能。

### 未使用的文件

| 文件路径 | 类型 | 说明 |
|---------|------|------|
| `src/App.css` | CSS | 未使用的样式文件 |
| `src/components/DownloadManager.css` | CSS | 未使用的样式文件 |
| `src/__tests__/vitest.d.ts` | 类型定义 | 测试类型定义文件 |

### 未使用的开发依赖

| 包名 | 说明 |
|------|------|
| `@testing-library/user-event` | 测试库，未在测试中使用 |
| `@vitest/coverage-v8` | 覆盖率工具，未配置使用 |
| `autoprefixer` | PostCSS 插件，未在配置中使用 |
| `postcss` | CSS 处理工具，未在配置中使用 |

### 未使用的导出（UI 组件）

这些是 UI 组件库的未使用导出，可以安全移除：

| 文件 | 未使用导出 |
|------|-----------|
| `src/components/ui/alert-dialog.tsx` | `AlertDialogPortal`, `AlertDialogOverlay`, `AlertDialogTrigger` |
| `src/components/ui/dialog.tsx` | `DialogPortal`, `DialogOverlay`, `DialogClose`, `DialogTrigger` |
| `src/components/ui/select.tsx` | `SelectGroup`, `SelectLabel`, `SelectSeparator`, `SelectScrollUpButton`, `SelectScrollDownButton` |
| `src/components/ui/scroll-area.tsx` | `ScrollBar` |
| `src/components/ui/card.tsx` | `CardFooter` |
| `src/components/ui/badge.tsx` | `badgeVariants`, `BadgeProps` |
| `src/components/ui/button.tsx` | `ButtonProps` |
| `src/components/ui/input.tsx` | `InputProps` |
| `src/components/ui/textarea.tsx` | `TextareaProps` |

---

## 🟡 CAUTION - 谨慎处理

这些项目可能被使用，需要进一步验证。

### 未使用的组件文件

| 文件路径 | 说明 | 风险 |
|---------|------|------|
| `src/components/GPUSettings.tsx` | GPU 设置组件 | 可能是功能开关控制的功能 |
| `src/components/SystemMonitor.tsx` | 系统监控组件 | 可能是功能开关控制的功能 |

### 未使用的工具文件

| 文件路径 | 说明 | 风险 |
|---------|------|------|
| `src/hooks/useAIToolsStatus.ts` | AI 工具状态 Hook | 可能用于未来功能 |
| `src/hooks/useWebSocket.ts` | WebSocket Hook | 可能用于未来功能 |
| `src/utils/backendConfig.ts` | 后端配置工具 | 可能在运行时动态导入 |
| `src/utils/logger.ts` | 日志工具 | 可能在运行时动态导入 |

### 未使用的生产依赖

| 包名 | 说明 | 风险 |
|------|------|------|
| `@radix-ui/react-dropdown-menu` | 下拉菜单组件 | 可能在未检测到的地方使用 |
| `react-router-dom` | 路由库 | 可能在未检测到的地方使用 |
| `recharts` | 图表库 | 可能用于统计功能 |
| `zustand` | 状态管理 | 可能在未检测到的地方使用 |
| `@types/dompurify` | DOMPurify 类型定义 | 与 dompurify 配套使用 |
| `@typescript-eslint/eslint-plugin` | ESLint 插件 | 在 .eslintrc.cjs 中配置 |

### 未使用的类型和常量导出

| 文件 | 未使用导出 | 说明 |
|------|-----------|------|
| `src/types/channels.ts` | 多个类型和常量 | 可能被外部模块使用 |
| `src/hooks/useChannelsSniffer.ts` | `MAX_CONSECUTIVE_FAILURES`, `CIRCUIT_BREAKER_COOLDOWN_MS` | 配置常量 |
| `src/utils/api.ts` | `apiClient`, 多个类型 | API 客户端和类型定义 |

---

## 🔴 DANGER - 不要删除

这些项目不应删除，它们是必需的或有特殊用途。

### 重复导出（命名导出 + 默认导出）

以下文件同时有命名导出和默认导出，这是常见的 React 组件模式：

- `src/components/QRLoginButton.tsx`
- `src/components/QRLoginDialog.tsx`
- `src/components/CookieManager.tsx`
- `src/components/channels/*.tsx` (多个组件)

**建议**: 保持现状，这是 React 组件的标准模式。

### 索引文件导出

`src/components/channels/index.ts` 中的导出用于模块聚合，不应删除。

### 类型定义

以下类型定义虽然未直接使用，但可能被外部模块或类型推断使用：
- `src/contexts/BackendContext.tsx` 中的类型
- `src/types/channels.ts` 中的类型

---

## 📊 统计摘要

| 类别 | 数量 |
|------|------|
| 未使用的文件 | 9 个 |
| 未使用的生产依赖 | 4 个 |
| 未使用的开发依赖 | 4 个 |
| 未使用的导出 | 50+ 个 |
| 重复导出 | 15+ 个 |

---

## 🎯 建议的清理步骤

### 第一阶段：安全清理（低风险）

1. 删除未使用的 CSS 文件
2. 删除未使用的开发依赖
3. 删除 UI 组件中未使用的导出

### 第二阶段：验证后清理（中风险）

1. 验证 GPUSettings 和 SystemMonitor 是否真的未使用
2. 验证 useWebSocket 和 useAIToolsStatus 是否真的未使用
3. 验证生产依赖是否真的未使用

### 第三阶段：代码优化（低优先级）

1. 统一组件导出方式（命名导出 vs 默认导出）
2. 清理未使用的类型导出
3. 优化导入路径

---

## ⚠️ 注意事项

1. **运行测试**: 每次删除后必须运行完整的测试套件
2. **功能验证**: 手动测试所有主要功能
3. **Git 提交**: 每个清理步骤单独提交，便于回滚
4. **备份**: 在开始清理前创建 Git 分支

---

## 🔍 详细分析

### depcheck 结果

```json
{
  "dependencies": ["@radix-ui/react-dropdown-menu", "react-router-dom", "recharts", "zustand"],
  "devDependencies": ["@testing-library/user-event", "@typescript-eslint/eslint-plugin", "@vitest/coverage-v8", "autoprefixer", "postcss"]
}
```

### knip 检测到的未使用文件

```
- src/App.css
- src/components/DownloadManager.css
- src/components/GPUSettings.tsx
- src/components/SystemMonitor.tsx
- src/hooks/useAIToolsStatus.ts
- src/hooks/useWebSocket.ts
- src/utils/backendConfig.ts
- src/utils/logger.ts
- src/__tests__/vitest.d.ts
```

### 潜在问题

1. **动态导入**: 某些文件可能通过动态 import() 使用，工具无法检测
2. **运行时引用**: 某些模块可能在运行时通过字符串引用
3. **外部引用**: Electron 主进程可能引用某些前端模块
4. **类型推断**: TypeScript 可能隐式使用某些类型定义

---

## 下一步行动

1. ✅ 生成此报告
2. ⏳ 按严重程度分类问题
3. ⏳ 提出安全删除建议
4. ⏳ 执行安全删除并验证测试
5. ⏳ 生成清理摘要报告

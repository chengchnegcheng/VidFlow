# 抖音/TikTok 视频下载问题排查指南

## 📋 常见错误及解决方案

### 1️⃣ **"抖音访问被限制，可能需要登录"**

**错误代码**: HTTP 403 / Forbidden

**原因**:
- 抖音的反爬虫机制检测到非正常访问
- 视频需要登录才能观看
- IP 被限流或封禁

**解决方案**:

#### 方法一：配置抖音 Cookie（推荐）

1. **打开抖音网页版**
   - 访问 [https://www.douyin.com](https://www.douyin.com)
   - 登录你的抖音账号

2. **提取 Cookie**
   - 在 VidFlow 中进入"Cookie 管理"
   - 选择"抖音"
   - 点击"自动提取"（推荐）或"手动导入"

3. **测试**
   - 返回下载页面
   - 重新尝试获取视频信息

#### 方法二：使用不同的网络

- 切换到移动网络（4G/5G）
- 使用 VPN 更换 IP
- 等待一段时间后重试（15-30分钟）

### 2️⃣ **"视频不存在或已被删除"**

**错误代码**: HTTP 404

**原因**:
- 视频已被作者删除
- 视频链接错误或失效
- 短链接已过期

**解决方案**:
1. 确认视频在抖音 App 中是否能正常打开
2. 尝试重新分享视频，获取新的链接
3. 如果是短链接（`v.douyin.com`），可能已过期，请获取新链接

### 3️⃣ **"无法解析视频信息"**

**错误代码**: Unable to extract

**原因**:
- 抖音更新了防护机制
- 视频格式特殊（如直播录像）
- Cookie 失效

**解决方案**:
1. **更新 yt-dlp**:
   ```bash
   # 在后端目录运行
   venv\Scripts\pip install -U yt-dlp
   ```

2. **重新配置 Cookie**:
   - Cookie 可能已过期
   - 重新登录抖音并提取 Cookie

3. **检查视频类型**:
   - 某些特殊视频（如付费内容、直播）可能无法下载

### 4️⃣ **"缺少必要的依赖库"**

**错误代码**: Module not found (httpx)

**原因**:
- `httpx` 库未安装
- Python 环境不完整

**解决方案**:
```bash
# 在后端目录运行
venv\Scripts\pip install httpx>=0.25.0
```

### 5️⃣ **短链接解析失败**

**现象**:
- 使用 `v.douyin.com` 短链接时出错
- 错误提示"短链接解析失败"

**解决方案**:

1. **手动获取完整链接**:
   - 在抖音 App 中打开视频
   - 分享时选择"复制链接"
   - 在浏览器中打开该链接
   - 从浏览器地址栏复制完整的 URL（`www.douyin.com/video/...`）

2. **确保 httpx 已安装**（见上方）

3. **网络问题**:
   - 检查网络连接
   - 短链接解析需要访问抖音服务器

## 🔧 Cookie 配置详细步骤

### 自动提取（推荐）

1. **打开 VidFlow**
2. **进入"Cookie 管理"**
3. **选择"抖音"平台**
4. **点击"自动提取"**
   - 会自动打开抖音网页
   - 登录你的账号
   - 自动提取并保存 Cookie

### 手动导入

1. **准备 Cookie 文件**:
   - 使用浏览器插件导出 Cookie（推荐：EditThisCookie）
   - 格式：Netscape 格式（.txt）

2. **导入到 VidFlow**:
   - 进入"Cookie 管理"
   - 选择"抖音"
   - 点击"导入 Cookie 文件"
   - 选择你导出的 .txt 文件

3. **验证**:
   - Cookie 管理器会显示"Cookie 已配置"
   - 尝试下载一个抖音视频测试

### Cookie 存储位置

```
VidFlow-Desktop/
└── data/
    └── cookies/
        ├── douyin_cookies.txt  ← 抖音 Cookie
        └── tiktok_cookies.txt  ← TikTok Cookie
```

## 📊 错误信息对照表

| 错误提示 | HTTP 状态码 | 常见原因 | 解决方案 |
|---------|-------------|----------|---------|
| 访问被限制 | 403 | 反爬虫机制 | 配置 Cookie |
| 视频不存在 | 404 | 链接失效 | 检查视频是否存在 |
| 无法解析 | 500 | 防护更新 | 更新 yt-dlp |
| 请求超时 | Timeout | 网络问题 | 检查网络连接 |
| 依赖缺失 | Module Error | 库未安装 | 安装缺失依赖 |

## 🎯 最佳实践

### 1. **保持 Cookie 有效**
- 定期（1-2周）重新提取 Cookie
- Cookie 失效是最常见的问题

### 2. **使用完整链接**
- 尽量避免使用短链接（`v.douyin.com`）
- 完整链接更稳定：`www.douyin.com/video/1234567890`

### 3. **合理使用**
- 避免短时间内大量下载
- 被限流后等待一段时间再试

### 4. **保持工具更新**
- 定期更新 yt-dlp
- 抖音会不断更新防护机制

## 🔍 调试技巧

### 查看详细日志

1. **打开日志中心**
2. **搜索关键词**:
   - `Douyin` - 抖音相关日志
   - `ERROR` - 所有错误
   - `403` / `404` - HTTP 错误

3. **查看堆栈跟踪**:
   - 完整的错误堆栈在后端控制台
   - 可以帮助定位具体问题

### 测试 Cookie 是否有效

```bash
# 在后端目录运行
venv\Scripts\python -c "
from pathlib import Path
cookie_file = Path('data/cookies/douyin_cookies.txt')
if cookie_file.exists():
    print(f'Cookie 文件存在，大小: {cookie_file.stat().st_size} bytes')
else:
    print('Cookie 文件不存在')
"
```

### 手动测试 yt-dlp

```bash
# 在后端目录运行
venv\Scripts\python -m yt_dlp ^
    --cookies data/cookies/douyin_cookies.txt ^
    --dump-json ^
    "抖音视频链接"
```

如果能成功输出 JSON，说明 Cookie 有效。

## 📝 常见问题 FAQ

### Q: 为什么有些视频可以下载，有些不行？

A: 可能原因：
- **视频权限不同**：部分视频仅好友可见、需要登录等
- **账号权限**：你的抖音账号可能没有观看权限
- **地区限制**：部分视频有地域限制

### Q: Cookie 会过期吗？

A: 会的。抖音 Cookie 通常在 **7-30 天**后过期。建议：
- 遇到 403 错误时重新提取
- 定期（每 2 周）更新一次

### Q: 能下载私密视频吗？

A: 理论上可以，但需要：
1. 你的抖音账号有观看权限（如你是作者的好友）
2. 使用该账号的 Cookie
3. 视频未设置"禁止下载"

### Q: 短链接和完整链接有什么区别？

A: 
- **短链接**（`v.douyin.com/xxx`）：
  - 方便分享
  - 可能过期
  - 需要额外解析（依赖 httpx）
  
- **完整链接**（`www.douyin.com/video/xxx`）：
  - 更稳定
  - 不需要解析
  - 推荐使用

### Q: 为什么下载速度很慢？

A: 可能原因：
- 抖音服务器限速
- 网络问题
- 被限流（短时间内下载太多）

**建议**：
- 分批下载，不要一次性下载太多
- 使用代理或 VPN
- 在非高峰时段下载

## 🚨 紧急情况处理

### 场景：所有抖音视频都无法下载

1. **检查 yt-dlp 版本**:
   ```bash
   venv\Scripts\pip show yt-dlp
   ```

2. **更新 yt-dlp**:
   ```bash
   venv\Scripts\pip install -U yt-dlp
   ```

3. **清除缓存**:
   ```bash
   venv\Scripts\python -m yt_dlp --rm-cache-dir
   ```

4. **重新配置 Cookie**

5. **等待一段时间**（可能是临时限流）

### 场景：提示"依赖缺失"

```bash
# 重新安装所有依赖
cd backend
venv\Scripts\pip install -r requirements.txt
```

## 📚 相关资源

- **yt-dlp 文档**: https://github.com/yt-dlp/yt-dlp
- **Cookie 提取工具**: 
  - Chrome: EditThisCookie
  - Firefox: cookies.txt
- **抖音网页版**: https://www.douyin.com

---

**最后更新**: 2025-11-05  
**适用版本**: VidFlow Desktop v1.0.0+

如果以上方法都无法解决问题，请：
1. 在日志中心导出完整日志
2. 记录复现步骤
3. 联系技术支持


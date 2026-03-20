# 微信视频号下载功能问题诊断报告

## 📋 问题总结

经过详细测试和诊断，发现以下问题导致微信视频号下载功能无法正常工作：

### 1. **代理软件干扰** ⚠️ 主要问题

**现象**：
- 检测到的 SNI 显示为 `proxy:IP地址` 而不是真实域名
- 无法提取视频 URL
- 缩略图和视频标题无法显示

**原因**：
你正在使用代理软件（Clash/v2rayN），它加密了所有网络流量，导致 VidFlow 无法读取原始的 TLS SNI 和 HTTP 请求。

**证据**：
```
[15:05:03] [✓] 检测到 SNI: proxy:113.240.76.236 -> 113.240.76.236:443
[15:05:03] [✓] 检测到 SNI: proxy:120.53.53.53 -> 120.53.53.53:443
```

### 2. **微信不遵循系统代理设置**

**现象**：
- 设置了系统代理 `127.0.0.1:8888`
- 但微信流量没有经过代理
- `netstat` 显示端口 8888 没有建立连接

**原因**：
微信桌面客户端使用自己的网络栈，忽略 Windows 系统代理设置。

### 3. **当前架构问题**

VidFlow 的 `channels.py` API 使用 `ProxySniffer`（mitmproxy 代理模式），但：
- 需要微信使用系统代理（微信不支持）
- 与代理软件冲突

## ✅ 解决方案

### 方案 A: 临时禁用代理软件（推荐测试）

1. **完全关闭代理软件**
   - 退出 Clash / v2rayN / 其他代理
   - 不只是切换模式，要完全退出

2. **重启微信**
   ```
   任务管理器 -> 结束所有微信进程 -> 重新打开微信
   ```

3. **运行测试**
   ```bash
   cd backend/tests
   python test_windivert_capture.py
   ```

4. **在微信中播放视频号视频**

### 方案 B: 配置代理软件直连规则

如果必须使用代理软件，配置以下规则让微信直连：

**Clash 配置** (`docs/clash_direct_rules.yaml`):
```yaml
# 微信进程直连
- PROCESS-NAME,WeChat.exe,DIRECT
- PROCESS-NAME,WeChatAppEx.exe,DIRECT
- PROCESS-NAME,Weixin.exe,DIRECT
- PROCESS-NAME,QQBrowser.exe,DIRECT
- PROCESS-NAME,msedgewebview2.exe,DIRECT

# 微信视频号域名直连
- DOMAIN-SUFFIX,finder.video.qq.com,DIRECT
- DOMAIN-SUFFIX,wxapp.tc.qq.com,DIRECT
- DOMAIN-SUFFIX,weixin.qq.com,DIRECT
- DOMAIN-SUFFIX,video.qq.com,DIRECT
```

**重要**：添加规则后需要：
1. 重启 Clash
2. 重启微信
3. 验证规则生效

### 方案 C: 使用 WinDivert 透明捕获（长期方案）

修改 VidFlow 使用 WinDivert 透明捕获而不是 mitmproxy：

**优点**：
- 无需系统代理
- 不受代理软件影响
- 直接在驱动层拦截流量

**缺点**：
- 需要管理员权限
- 仅支持 Windows

## 🔧 测试文件

| 文件 | 用途 |
|------|------|
| `backend/tests/diagnose_channels_env.py` | 环境诊断（检查证书、代理、端口等） |
| `backend/tests/test_channels_full.py` | mitmproxy 代理模式测试 |
| `backend/tests/test_windivert_capture.py` | WinDivert 透明捕获测试 ⭐ |
| `backend/tests/test_detailed_analysis.py` | 详细流量分析 |

## 📊 诊断结果

### 环境检查

| 检查项 | 状态 | 说明 |
|--------|------|------|
| 管理员权限 | ✅ | 正常 |
| 微信进程 | ✅ | 检测到 15 个进程 |
| mitmproxy 证书 | ✅ | 已安装到系统 |
| WinDivert 驱动 | ✅ | pydivert 已安装 |
| 系统代理 | ⚠️ | 已设置但微信不使用 |
| **代理软件** | ❌ | **检测到代理软件正在运行** |
| 端口 8888 | ⚠️ | 可用但无连接 |
| 域名解析 | ✅ | 正常 |

### WinDivert 捕获测试结果

```
拦截包: 54,680+
SNI 提取: 0 (因为代理软件加密)
视频检测: 0
QUIC 阻断: 0
```

**关键发现**：
- 捕获到大量数据包（54,000+）
- 但所有 SNI 都被代理软件加密
- 无法提取真实的域名信息

## 🎯 下一步行动

### 立即测试（推荐）

1. **关闭代理软件**
   ```
   右键托盘图标 -> 退出
   ```

2. **重启微信**
   ```
   任务管理器 -> 结束微信 -> 重新打开
   ```

3. **运行 WinDivert 测试**
   ```bash
   cd d:\Coding Project\VidFlow\VidFlow\backend\tests
   python test_windivert_capture.py
   ```

4. **在微信中播放视频号视频**

5. **观察输出**
   - 应该看到真实的 SNI 域名（如 `finder.video.qq.com`）
   - 应该检测到视频 URL

### 如果仍然无法工作

1. 检查 QUIC 是否被阻断
2. 查看详细日志
3. 使用 `test_detailed_analysis.py` 分析流量

## 📝 技术细节

### 为什么代理软件会干扰？

1. **TLS 加密**：代理软件对所有 HTTPS 流量进行中间人攻击，替换了原始的 TLS SNI
2. **流量重定向**：所有流量都经过代理软件的 TUN/TAP 设备
3. **DNS 劫持**：代理软件可能使用 Fake-IP 模式，返回虚假的 IP 地址

### WinDivert 工作原理

1. 在 Windows 驱动层拦截网络包
2. 直接读取 TCP payload
3. 提取 TLS ClientHello 中的 SNI
4. 提取 HTTP 请求中的 URL
5. 不修改原始流量（被动模式）

## 🔗 参考资料

- WinDivert 文档: https://reqrypt.org/windivert-doc.html
- mitmproxy 文档: https://docs.mitmproxy.org/
- Clash 规则: https://github.com/Dreamacro/clash/wiki/configuration

---

**创建时间**: 2026-02-06 15:26
**测试环境**: Windows, Python 3.14, 管理员权限
**代理软件**: Clash (检测到)

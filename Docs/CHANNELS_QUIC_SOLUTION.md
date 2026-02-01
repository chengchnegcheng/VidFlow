# 视频号 QUIC 屏蔽解决方案

## 问题背景

微信视频号使用 QUIC 协议（基于 UDP/443）进行加密通信，导致传统的 HTTP/HTTPS 代理无法拦截流量。

## 解决方案

通过屏蔽 QUIC 协议，强制微信使用 HTTP/HTTPS，然后使用 mitmproxy 拦截流量并提取视频 URL 和解密密钥（encfilekey）。

## 实现功能

### 1. QUIC 屏蔽器 (`quic_blocker.py`)

- 通过防火墙规则屏蔽 UDP/443 端口
- 支持 Windows（netsh advfirewall）
- 支持 Linux（iptables）
- 提供状态检查、屏蔽、解除屏蔽功能

### 2. HTTP 监控器 (`http_monitor.py`)

- 监控 HTTP 流量，识别视频号视频 URL
- 自动提取 `encfilekey` 参数（解密密钥）
- 支持多个视频号域名（wxapp.tc.qq.com, finder.video.qq.com 等）
- 集成到 mitmproxy 作为插件

### 3. 视频解密器增强 (`video_decryptor.py`)

- 支持两种密钥类型：
  - `decodeKey`：短密钥（数字字符串），转换为 4 字节小端序
  - `encfilekey`：长密钥（从 URL 获取），使用 MD5 哈希生成 4 字节密钥
- 使用 XOR 算法解密前 128KB（0x20000 字节）

### 4. API 端点

- `GET /api/channels/quic/status` - 检查 QUIC 屏蔽状态
- `POST /api/channels/quic/block` - 屏蔽 QUIC 协议
- `POST /api/channels/quic/unblock` - 解除 QUIC 屏蔽

## 使用流程

### 1. 屏蔽 QUIC 协议

```bash
# 调用 API
curl -X POST http://localhost:53086/api/channels/quic/block
```

或在前端界面中点击"屏蔽 QUIC"按钮。

**注意：需要管理员权限！**

### 2. 重启微信

屏蔽 QUIC 后，必须重启微信才能生效。

### 3. 启动嗅探器

嗅探器会自动集成 HTTP 监控器，监听视频号流量。

### 4. 播放视频

在微信中播放视频号视频，嗅探器会自动：
- 检测视频 URL
- 提取 `encfilekey`
- 创建视频记录

### 5. 下载视频

下载时会自动使用 `encfilekey` 进行解密。

### 6. 恢复 QUIC（可选）

使用完成后，可以解除 QUIC 屏蔽：

```bash
curl -X POST http://localhost:53086/api/channels/quic/unblock
```

## 技术细节

### QUIC 屏蔽原理

通过防火墙规则阻止 UDP/443 端口的出站流量：

```bash
# Windows
netsh advfirewall firewall add rule name="VidFlow_Block_QUIC" dir=out action=block protocol=UDP remoteport=443

# Linux
iptables -A OUTPUT -p udp --dport 443 -j DROP
```

### 视频加密原理

根据 GitHub 项目研究（KingsleyYau/WeChatChannelsDownloader）：
- 视频前 128KB（0x20000 字节）使用 XOR 加密
- URL 中的 `encfilekey` 参数是解密密钥
- 使用 MD5 哈希 encfilekey 生成 4 字节 XOR 密钥

### HTTP 监控原理

使用 mitmproxy 拦截 HTTPS 流量：
1. 检测视频号域名（wxapp.tc.qq.com 等）
2. 匹配 URL 模式（/stodownload 等）
3. 提取 `encfilekey` 参数
4. 触发回调，创建视频记录

## 测试

运行测试脚本：

```bash
python backend/tests/test_quic_and_http_monitor.py
```

测试内容：
- QUIC 屏蔽器功能
- HTTP 监控器 URL 检测
- 视频信息提取

## 注意事项

1. **需要管理员权限**：屏蔽 QUIC 需要修改防火墙规则
2. **必须重启微信**：屏蔽后需要重启微信才能生效
3. **影响其他应用**：屏蔽 QUIC 会影响所有使用 QUIC 的应用
4. **使用后恢复**：建议使用完成后解除 QUIC 屏蔽

## 参考资料

- [KingsleyYau/WeChatChannelsDownloader](https://github.com/KingsleyYau/WeChatChannelsDownloader)
- [res-downloader](https://github.com/lqzhgood/res-downloader)
- mitmproxy 文档

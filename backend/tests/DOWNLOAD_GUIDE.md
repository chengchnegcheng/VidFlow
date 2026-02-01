# 视频号下载完整指南

## 当前状态

✅ QUIC 已屏蔽（UDP/443 已阻止）
✅ 嗅探器正在运行
✅ 后端服务器正常

## 下载步骤

### 1. 重启微信（重要！）

QUIC 屏蔽后必须重启微信才能生效。

**操作：**
- 完全关闭微信（任务管理器中确认进程已结束）
- 重新打开微信

### 2. 播放视频号视频

**操作：**
- 在微信中打开视频号
- 播放任意视频（如你截图中的"每年杏花落打药一次"）
- 让视频播放几秒钟

### 3. 运行下载测试

**命令：**
```bash
python backend/tests/test_real_video.py
```

**预期结果：**
- 嗅探器会检测到视频 URL
- 自动提取 encfilekey
- 下载并解密视频

### 4. 查看下载的视频

下载的视频保存在：
```
backend/data/downloads/
```

## 故障排除

### 问题 1: 没有检测到视频

**原因：**
- 微信还在使用 QUIC 协议
- 嗅探器未正确拦截流量

**解决：**
1. 确认 QUIC 已屏蔽：
   ```bash
   netsh advfirewall firewall show rule name="VidFlow_Block_QUIC"
   ```

2. 重启微信（必须！）

3. 清除浏览器缓存（如果使用微信内置浏览器）

### 问题 2: 下载失败

**原因：**
- URL 已过期
- 缺少解密密钥

**解决：**
1. 重新播放视频获取新 URL
2. 确保 URL 中包含 encfilekey 参数

### 问题 3: 视频无法播放

**原因：**
- 解密失败
- 缺少 moov box

**解决：**
1. 检查是否提取到 encfilekey
2. 尝试使用其他播放器（VLC、PotPlayer）

## 测试命令

### 检查 QUIC 状态
```bash
python backend/tests/test_quic_and_http_monitor.py
```

### 完整集成测试
```bash
python backend/tests/test_channels_integration.py
```

### 真实下载测试
```bash
python backend/tests/test_real_video.py
```

## 注意事项

1. **管理员权限**：屏蔽 QUIC 需要管理员权限
2. **重启微信**：屏蔽 QUIC 后必须重启微信
3. **URL 时效**：视频 URL 有时效性，需要及时下载
4. **解密密钥**：encfilekey 是解密的关键，必须从 URL 中提取

## 成功标志

当看到以下输出时，说明成功：

```
✅ 检测到 1 个视频
✅ 下载任务已创建
进度: 100% [completed]
✅ 下载完成
✅ 文件格式: MP4 (有效)
✅ 包含 moov box (可以播放)
✅ 视频已保存: backend/data/downloads/xxx.mp4
```

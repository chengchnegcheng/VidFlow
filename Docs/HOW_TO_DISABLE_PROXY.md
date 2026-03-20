# 如何完全关闭代理软件

## 问题
即使在 Clash/Verge 中点击"停止代理"，进程仍在运行，DNS 仍被劫持到 Fake IP (198.18.x.x)，导致无法捕获真实视频流量。

## 解决方案

### 方法 1: 完全退出 Clash/Verge（推荐）

1. **右键点击任务栏托盘图标**
2. **选择"退出"或"Exit"**
3. **确认进程已关闭**：
   ```powershell
   Get-Process | Where-Object {$_.ProcessName -like "*clash*" -or $_.ProcessName -like "*verge*"}
   ```
   应该没有任何输出

### 方法 2: 强制结束进程

```powershell
# 结束 Clash 相关进程
Get-Process | Where-Object {$_.ProcessName -like "*clash*" -or $_.ProcessName -like "*verge*" -or $_.ProcessName -like "*mihomo*"} | Stop-Process -Force
```

### 方法 3: 刷新 DNS 缓存

关闭代理后，刷新 DNS 缓存：
```powershell
ipconfig /flushdns
```

### 方法 4: 配置 Clash 直连规则（不关闭代理）

如果不想关闭代理，可以配置微信直连：

编辑 Clash 配置文件，添加：
```yaml
rules:
  # 微信视频号直连
  - PROCESS-NAME,WeChat.exe,DIRECT
  - PROCESS-NAME,WeChatAppEx.exe,DIRECT
  - PROCESS-NAME,QQBrowser.exe,DIRECT
  - PROCESS-NAME,msedgewebview2.exe,DIRECT
  - DOMAIN-SUFFIX,video.qq.com,DIRECT
  - DOMAIN-SUFFIX,weixin.qq.com,DIRECT
  - DOMAIN-SUFFIX,wxapp.tc.qq.com,DIRECT
```

## 验证

关闭代理后，验证 DNS 是否正常：
```powershell
nslookup wxapp.tc.qq.com 8.8.8.8
```

应该返回真实 IP（如 183.131.x.x），而不是 Fake IP（198.18.x.x）

## 当前检测到的问题

```
检测到代理进程：
- verge-mihomo.exe (PID: 16748)
- clash-verge.exe (PID: 26004)

DNS 被劫持到 Fake IP：
- 所有域名解析到 198.18.x.x
- 无法捕获真实视频流量
```

请完全退出 Clash/Verge，然后重新启动嗅探器。

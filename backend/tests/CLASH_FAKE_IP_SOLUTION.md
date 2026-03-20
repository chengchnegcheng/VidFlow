# Clash Fake-IP 模式解决方案

## 问题描述

当使用 Clash 代理软件时，如果启用了 **Fake-IP 模式**，会导致微信视频号捕获功能无法正常工作。

### 原因

1. Clash 的 Fake-IP 模式会将 DNS 解析结果替换为假 IP（198.18.x.x）
2. WinDivert 捕获服务会尝试拦截这些假 IP 的流量
3. 但实际的网络流量走的是真实 IP，不经过假 IP
4. 导致无法捕获到视频链接

## 解决方案

### 方案 1：临时关闭 Clash（推荐用于测试）

1. 右键点击 Clash 托盘图标
2. 选择"退出"或"关闭系统代理"
3. 重新启动视频号嗅探器
4. 在微信视频号中播放视频
5. 测试是否能捕获到视频

**优点**：简单快速，适合测试
**缺点**：无法同时使用代理和视频捕获

### 方案 2：修改 Clash DNS 模式为 Redir-Host（推荐长期使用）

#### 步骤：

1. **找到 Clash 配置文件**
   - Clash for Windows: `%USERPROFILE%\.config\clash\config.yaml`
   - Clash Verge: `%USERPROFILE%\.config\clash-verge\config.yaml`
   - 或在 Clash 界面中点击"配置" -> "打开配置文件夹"

2. **编辑配置文件**
   
   找到 `dns` 部分，将 `enhanced-mode` 从 `fake-ip` 改为 `redir-host`：

   ```yaml
   dns:
     enable: true
     enhanced-mode: redir-host  # 改为 redir-host
     # enhanced-mode: fake-ip   # 注释掉或删除这行
     nameserver:
       - 223.5.5.5
       - 119.29.29.29
     fallback:
       - 8.8.8.8
       - 1.1.1.1
   ```

3. **重启 Clash**
   - 右键点击 Clash 托盘图标
   - 选择"重启 Clash"
   - 或直接退出后重新启动

4. **验证修改**
   
   运行诊断脚本：
   ```bash
   cd backend
   python tests/diagnose_clash_proxy.py
   ```
   
   检查 DNS 解析是否返回真实 IP（不是 198.18.x.x）

**优点**：可以同时使用代理和视频捕获
**缺点**：需要修改配置文件

### 方案 3：使用 Clash 规则绕过微信（高级）

如果你需要保持 Fake-IP 模式，可以添加规则让微信流量绕过 Clash：

```yaml
rules:
  # 微信相关域名直连
  - DOMAIN-SUFFIX,qq.com,DIRECT
  - DOMAIN-SUFFIX,weixin.qq.com,DIRECT
  - DOMAIN-SUFFIX,wechat.com,DIRECT
  - DOMAIN-KEYWORD,finder,DIRECT
  - DOMAIN-KEYWORD,channels,DIRECT
  - DOMAIN-KEYWORD,wxapp,DIRECT
  
  # 其他规则...
  - MATCH,PROXY
```

## 诊断工具

运行以下命令检查当前环境：

```bash
cd backend
python tests/diagnose_clash_proxy.py
```

该工具会检查：
- Clash 进程是否运行
- Clash API 是否可访问
- DNS 模式（Fake-IP vs Redir-Host）
- DNS 解析结果
- 微信进程状态
- 管理员权限
- 网络连接状态

## 常见问题

### Q: 修改配置后仍然无法捕获视频？

A: 请确保：
1. 已重启 Clash
2. 已重启视频号嗅探器
3. 运行诊断工具确认 DNS 模式已改为 redir-host
4. 应用以管理员身份运行

### Q: 不想修改 Clash 配置怎么办？

A: 可以在使用视频捕获功能时临时关闭 Clash，使用完后再启动。

### Q: Redir-Host 模式会影响代理性能吗？

A: 不会。Redir-Host 模式是标准的 DNS 解析模式，性能和兼容性都很好。Fake-IP 模式主要是为了加快 DNS 解析速度，但在某些场景下会导致兼容性问题。

### Q: 我使用的是其他代理软件（V2Ray/Xray/Sing-Box）？

A: 其他代理软件也可能有类似的 Fake-IP 功能。建议：
1. 检查代理软件的 DNS 配置
2. 关闭 Fake-IP 或类似功能
3. 或临时关闭代理软件进行测试

## 技术细节

### Fake-IP 工作原理

1. 客户端请求解析域名（如 finder.video.qq.com）
2. Clash 返回假 IP（如 198.18.1.1）
3. 客户端向假 IP 发起连接
4. Clash 拦截连接，查询真实 IP
5. Clash 代理连接到真实服务器

### 为什么会影响视频捕获

1. WinDivert 根据 DNS 解析结果（假 IP）设置过滤规则
2. 但实际流量走的是 Clash 代理的真实 IP
3. WinDivert 无法匹配到这些流量
4. 导致无法提取 SNI 和视频 URL

### Redir-Host 模式

1. 客户端请求解析域名
2. Clash 查询真实 IP 并返回
3. 客户端向真实 IP 发起连接
4. Clash 拦截连接并代理

这样 WinDivert 可以正确匹配到流量。

## 参考资料

- [Clash 官方文档 - DNS 配置](https://github.com/Dreamacro/clash/wiki/configuration#dns)
- [Clash Premium 文档](https://github.com/Dreamacro/clash/wiki/premium/introduction)
- [WinDivert 文档](https://reqrypt.org/windivert-doc.html)

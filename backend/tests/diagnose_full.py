"""完整诊断脚本"""
import asyncio
import httpx
import json
import subprocess
from pathlib import Path

async def find_backend_port():
    """查找后端服务器端口"""
    port_file = Path(__file__).parent.parent / "data" / "backend_port.json"
    if port_file.exists():
        try:
            with open(port_file, 'r') as f:
                data = json.load(f)
                return data.get('port', 53086)
        except:
            pass
    return 53086

def check_firewall_rules():
    """检查防火墙规则"""
    print("\n检查防火墙规则...")
    try:
        result = subprocess.run(
            ['netsh', 'advfirewall', 'firewall', 'show', 'rule', 'name=VidFlow_Block_QUIC'],
            capture_output=True,
            text=True,
            encoding='gbk'
        )
        if 'VidFlow_Block_QUIC' in result.stdout:
            print("✅ 防火墙规则存在")
            # 检查是否启用
            if '已启用' in result.stdout or 'Yes' in result.stdout:
                print("✅ 规则已启用")
            else:
                print("❌ 规则未启用")
        else:
            print("❌ 防火墙规则不存在")
    except Exception as e:
        print(f"❌ 检查失败: {e}")

def check_wechat_process():
    """检查微信进程"""
    print("\n检查微信进程...")
    try:
        result = subprocess.run(
            ['tasklist', '/FI', 'IMAGENAME eq WeChat.exe'],
            capture_output=True,
            text=True,
            encoding='gbk'
        )
        if 'WeChat.exe' in result.stdout:
            print("✅ 微信正在运行")
            # 提取 PID
            lines = result.stdout.split('\n')
            for line in lines:
                if 'WeChat.exe' in line:
                    parts = line.split()
                    if len(parts) >= 2:
                        print(f"   PID: {parts[1]}")
        else:
            print("❌ 微信未运行")
    except Exception as e:
        print(f"❌ 检查失败: {e}")

async def main():
    port = await find_backend_port()
    base_url = f"http://127.0.0.1:{port}"
    
    print("=" * 60)
    print("完整诊断")
    print("=" * 60)
    print(f"后端地址: {base_url}\n")
    
    # 1. 检查后端连接
    print("1. 检查后端连接...")
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{base_url}/api/channels/sniffer/status")
            print("✅ 后端连接正常")
    except Exception as e:
        print(f"❌ 后端连接失败: {e}")
        return
    
    # 2. 检查 QUIC 屏蔽
    print("\n2. 检查 QUIC 屏蔽...")
    async with httpx.AsyncClient(timeout=5) as client:
        resp = await client.get(f"{base_url}/api/channels/quic/status")
        quic_status = resp.json()
        if quic_status['is_blocked']:
            print(f"✅ QUIC 已屏蔽（规则: {quic_status['rule_name']}）")
        else:
            print("❌ QUIC 未屏蔽")
    
    # 3. 检查防火墙规则
    check_firewall_rules()
    
    # 4. 检查微信进程
    check_wechat_process()
    
    # 5. 检查嗅探器状态
    print("\n5. 检查嗅探器状态...")
    async with httpx.AsyncClient(timeout=5) as client:
        resp = await client.get(f"{base_url}/api/channels/sniffer/status")
        status = resp.json()
        
        if status['state'] == 'running':
            print("✅ 嗅探器正在运行")
            print(f"   代理地址: {status.get('proxy_address', 'N/A')}")
            print(f"   捕获状态: {status.get('capture_state', 'N/A')}")
            print(f"   检测到的视频: {status['videos_detected']}")
        else:
            print(f"❌ 嗅探器未运行（状态: {status['state']}）")
    
    # 6. 检查检测到的视频
    print("\n6. 检查检测到的视频...")
    async with httpx.AsyncClient(timeout=5) as client:
        resp = await client.get(f"{base_url}/api/channels/videos")
        videos = resp.json()
        
        if videos:
            print(f"✅ 检测到 {len(videos)} 个视频")
            for i, video in enumerate(videos, 1):
                print(f"\n   视频 {i}:")
                print(f"   - 标题: {video['title']}")
                print(f"   - URL: {video['url'][:80]}...")
                print(f"   - 加密类型: {video['encryption_type']}")
                if video.get('decryption_key'):
                    print(f"   - 解密密钥: {video['decryption_key'][:50]}...")
        else:
            print("❌ 未检测到视频")
    
    # 7. 总结和建议
    print("\n" + "=" * 60)
    print("诊断总结")
    print("=" * 60)
    
    if status['state'] != 'running':
        print("\n❌ 嗅探器未运行")
        print("\n建议:")
        print("1. 在前端界面点击'启动嗅探'按钮")
        print("2. 或者调用 API: POST http://127.0.0.1:{}/api/channels/sniffer/start".format(port))
    elif not videos:
        print("\n⚠️  嗅探器运行中但未检测到视频")
        print("\n可能的原因:")
        print("1. 微信使用了 ECH 加密（即使屏蔽 QUIC 也无法拦截 SNI）")
        print("2. 透明捕获模式配置问题")
        print("3. 需要在微信中播放视频号视频")
        print("\n建议:")
        print("1. 确保微信已重启（QUIC 屏蔽后必须重启）")
        print("2. 在微信中打开视频号并播放视频")
        print("3. 如果还是检测不到，尝试使用 Fiddler/Charles 抓包")
        print("4. 从抓包工具复制视频 URL，在前端手动添加")
    else:
        print("\n✅ 一切正常！")
        print(f"\n检测到 {len(videos)} 个视频，可以开始下载测试")
        print(f"\n运行下载测试: python backend/tests/test_real_video.py")

if __name__ == "__main__":
    asyncio.run(main())

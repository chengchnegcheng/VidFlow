"""
检查嗅探器详细状态
"""

import asyncio
import httpx
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


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

async def main():
    port = await find_backend_port()
    base_url = f"http://127.0.0.1:{port}"

    print("=" * 60)
    print("嗅探器状态检查")
    print("=" * 60)

    async with httpx.AsyncClient(timeout=30) as client:
        # 1. 嗅探器状态
        print("\n1. 嗅探器状态:")
        resp = await client.get(f"{base_url}/api/channels/sniffer/status")
        status = resp.json()
        print(json.dumps(status, indent=2, ensure_ascii=False))

        # 2. QUIC 状态
        print("\n2. QUIC 屏蔽状态:")
        try:
            resp = await client.get(f"{base_url}/api/channels/quic/status")
            quic_status = resp.json()
            print(json.dumps(quic_status, indent=2, ensure_ascii=False))
        except Exception as e:
            print(f"获取失败: {e}")

        # 3. 捕获配置
        print("\n3. 捕获配置:")
        try:
            resp = await client.get(f"{base_url}/api/channels/capture/config")
            config = resp.json()
            print(json.dumps(config, indent=2, ensure_ascii=False))
        except Exception as e:
            print(f"获取失败: {e}")

        # 4. 检测到的视频
        print("\n4. 检测到的视频:")
        resp = await client.get(f"{base_url}/api/channels/videos")
        videos = resp.json()
        print(f"数量: {len(videos)}")
        if videos:
            for video in videos:
                print(f"\n  - {video['title']}")
                print(f"    URL: {video['url'][:80]}...")

        # 5. 诊断信息
        print("\n5. 诊断信息:")
        try:
            resp = await client.get(f"{base_url}/api/channels/diagnostics")
            diag = resp.json()
            print(f"  检测到的 SNI: {len(diag.get('detected_snis', []))}")
            print(f"  检测到的 IP: {len(diag.get('detected_ips', []))}")
            print(f"  微信进程: {len(diag.get('wechat_processes', []))}")

            if diag.get('detected_snis'):
                print(f"\n  最近的 SNI:")
                for sni in diag['detected_snis'][:5]:
                    print(f"    - {sni}")
        except Exception as e:
            print(f"获取失败: {e}")

        print("\n" + "=" * 60)
        print("建议:")
        print("=" * 60)

        if status['state'] != 'running':
            print("❌ 嗅探器未运行，请启动嗅探器")
        elif len(videos) == 0:
            print("⚠️  未检测到视频，可能的原因:")
            print("  1. 微信使用了 ECH 加密（即使屏蔽 QUIC 也无法拦截）")
            print("  2. 透明模式配置问题")
            print("  3. 需要使用其他抓包工具（Fiddler、Charles）")
            print("\n建议:")
            print("  1. 尝试使用 Fiddler 或 Charles 抓包")
            print("  2. 从抓包工具中复制视频 URL")
            print("  3. 在前端界面手动添加 URL")
        else:
            print("✅ 嗅探器工作正常")


if __name__ == "__main__":
    asyncio.run(main())

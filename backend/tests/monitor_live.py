"""实时监控视频检测"""
import asyncio
import httpx
import json
from pathlib import Path
from datetime import datetime

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
    print("实时监控视频检测")
    print("=" * 60)
    print(f"后端地址: {base_url}")
    print("按 Ctrl+C 停止监控")
    print("=" * 60)

    last_video_count = 0
    last_sni_count = 0

    async with httpx.AsyncClient(timeout=10) as client:
        while True:
            try:
                # 获取状态
                resp = await client.get(f"{base_url}/api/channels/sniffer/status")
                status = resp.json()

                # 获取视频列表
                resp = await client.get(f"{base_url}/api/channels/videos")
                videos = resp.json()

                # 获取诊断信息
                try:
                    resp = await client.get(f"{base_url}/api/channels/diagnostics")
                    diag = resp.json()
                    sni_count = len(diag.get('detected_snis', []))
                except:
                    sni_count = 0

                # 显示状态
                now = datetime.now().strftime("%H:%M:%S")
                video_count = len(videos)

                print(f"\r[{now}] 嗅探器: {status['state']:10} | "
                      f"视频: {video_count:3} | "
                      f"SNI: {sni_count:3} | "
                      f"捕获: {status.get('capture_state', 'unknown'):10}",
                      end='', flush=True)

                # 检测到新视频
                if video_count > last_video_count:
                    print()  # 换行
                    for video in videos[last_video_count:]:
                        print(f"\n🎬 新视频: {video['title']}")
                        print(f"   URL: {video['url'][:80]}...")
                        if video.get('decryption_key'):
                            print(f"   密钥: {video['decryption_key'][:50]}...")
                    last_video_count = video_count

                # 检测到新 SNI
                if sni_count > last_sni_count:
                    print()  # 换行
                    print(f"\n📡 检测到 {sni_count - last_sni_count} 个新 SNI")
                    last_sni_count = sni_count

                await asyncio.sleep(1)

            except KeyboardInterrupt:
                print("\n\n监控已停止")
                break
            except Exception as e:
                print(f"\n错误: {e}")
                await asyncio.sleep(2)

if __name__ == "__main__":
    asyncio.run(main())

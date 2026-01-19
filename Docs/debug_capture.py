"""调试视频号捕获"""
import asyncio
import httpx
import json
import time
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
PORT_FILE = DATA_DIR / "backend_port.json"

with open(PORT_FILE, 'r') as f:
    data = json.load(f)
    base_url = f"http://{data['host']}:{data['port']}"

async def debug():
    async with httpx.AsyncClient(timeout=30) as client:
        print(f"后端地址: {base_url}")
        
        # 获取状态
        resp = await client.get(f'{base_url}/api/channels/sniffer/status')
        status = resp.json()
        print(f'\n嗅探器状态: {status["state"]}')
        print(f'捕获状态: {status["capture_state"]}')
        
        if status.get('statistics'):
            stats = status['statistics']
            print(f'\n统计信息:')
            print(f'  拦截包数: {stats.get("packets_intercepted", 0)}')
            print(f'  重定向连接: {stats.get("connections_redirected", 0)}')
            print(f'  检测视频数: {stats.get("videos_detected", 0)}')
        
        # 获取检测到的视频
        resp = await client.get(f'{base_url}/api/channels/videos')
        videos = resp.json()
        print(f'\n检测到的视频: {len(videos)} 个')
        for v in videos:
            print(f'  - {v.get("title", "未知")}')
            print(f'    URL: {v["url"][:100]}...' if len(v["url"]) > 100 else f'    URL: {v["url"]}')
        
        # 持续监控
        print("\n开始持续监控（每3秒刷新）...")
        print("请在微信视频号中播放视频...")
        print("按 Ctrl+C 停止\n")
        
        last_packets = 0
        last_redirected = 0
        
        try:
            while True:
                await asyncio.sleep(3)
                
                resp = await client.get(f'{base_url}/api/channels/sniffer/status')
                status = resp.json()
                
                if status.get('statistics'):
                    stats = status['statistics']
                    packets = stats.get("packets_intercepted", 0)
                    redirected = stats.get("connections_redirected", 0)
                    videos_count = stats.get("videos_detected", 0)
                    
                    new_packets = packets - last_packets
                    new_redirected = redirected - last_redirected
                    
                    print(f"[{time.strftime('%H:%M:%S')}] 包: {packets} (+{new_packets}), SNI检测: {redirected} (+{new_redirected}), 视频: {videos_count}")
                    
                    last_packets = packets
                    last_redirected = redirected
                    
                    # 如果有新检测到的视频，显示详情
                    if new_redirected > 0:
                        resp = await client.get(f'{base_url}/api/channels/videos')
                        videos = resp.json()
                        if videos:
                            print(f"  最新视频: {videos[-1].get('title', '未知')}")
                
        except KeyboardInterrupt:
            print("\n停止监控")

asyncio.run(debug())

"""监控代理嗅探器检测到的视频"""
import time
import requests
import json

BACKEND_URL = "http://127.0.0.1:6894"

def main():
    print("=" * 60)
    print("代理嗅探器监控")
    print("=" * 60)
    print("系统代理: 127.0.0.1:8888")
    print("请在微信视频号中播放视频...")
    print("按 Ctrl+C 停止\n")
    
    last_video_count = 0
    
    try:
        while True:
            # 获取状态
            resp = requests.get(f"{BACKEND_URL}/api/channels/sniffer/status", timeout=5)
            status = resp.json()
            
            state = status.get("state", "unknown")
            videos_detected = status.get("videos_detected", 0)
            
            if videos_detected > last_video_count:
                print(f"\n🎬 检测到新视频！总数: {videos_detected}")
                
                # 获取视频列表
                resp = requests.get(f"{BACKEND_URL}/api/channels/videos", timeout=5)
                videos = resp.json()
                
                for v in videos[last_video_count:]:
                    print(f"  标题: {v.get('title', '未知')}")
                    url = v.get('url', '')
                    print(f"  URL: {url[:100]}..." if len(url) > 100 else f"  URL: {url}")
                    print()
                
                last_video_count = videos_detected
            else:
                print(f"[{time.strftime('%H:%M:%S')}] 状态: {state}, 视频数: {videos_detected}", end="\r")
            
            time.sleep(2)
            
    except KeyboardInterrupt:
        print("\n\n停止监控")
        
        # 显示所有检测到的视频
        resp = requests.get(f"{BACKEND_URL}/api/channels/videos", timeout=5)
        videos = resp.json()
        
        print(f"\n检测到的视频 ({len(videos)}):")
        for v in videos:
            print(f"  - {v.get('title', '未知')}")
            print(f"    {v.get('url', '')[:100]}...")


if __name__ == "__main__":
    main()

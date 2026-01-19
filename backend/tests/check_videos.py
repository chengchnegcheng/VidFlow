"""检查检测到的视频"""
import httpx
import json

r = httpx.get('http://127.0.0.1:14683/api/channels/videos', timeout=10)
videos = r.json()
print(f"检测到 {len(videos)} 个视频:")
for v in videos:
    print(f"  - {v['title']}")
    print(f"    URL: {v['url'][:100]}...")
    print()

#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
微信视频号捕获测试 - 调试版本
显示所有捕获到的流量
"""

import asyncio
import sys
import time
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from src.core.channels.proxy_sniffer import ProxySniffer
from src.core.channels.traffic_capture import WinDivertCapture
from src.core.channels.quic_manager import QUICManager
from src.utils.cert_installer import CertInstaller


async def main():
    """测试微信视频号捕获 - 调试版本"""
    print("=" * 60)
    print("微信视频号捕获测试 - 调试版本")
    print("=" * 60)
    
    # 预初始化清理变量
    windivert = None
    sniffer = None
    quic_manager = None
    
    # 1. 检查管理员权限
    import ctypes
    is_admin = ctypes.windll.shell32.IsUserAnAdmin() != 0
    if not is_admin:
        print("\n✗ 错误: 需要管理员权限")
        return
    print("\n✓ 管理员权限检查通过")
    
    # 2. 检查并安装证书
    print("\n检查 mitmproxy 证书...")
    cert_installer = CertInstaller()
    
    if not cert_installer.is_cert_installed():
        print("  证书未安装,开始安装...")
        if not cert_installer.install_cert():
            print("  ✗ 证书安装失败")
            return
        print("  ✓ 证书安装成功")
    else:
        print("  ✓ 证书已安装")
    
    # 3. 启动 QUIC 阻止
    print("\n启动 QUIC 阻止...")
    quic_manager = QUICManager()
    
    if not await quic_manager.start_blocking():
        print("  ✗ QUIC 阻止失败")
        return
    print("  ✓ QUIC 已阻止")
    
    # 4. 启动 mitmproxy (透明模式)
    print("\n启动 mitmproxy (透明模式)...")
    sniffer = ProxySniffer(port=8888, transparent_mode=True)
    
    # 设置视频检测回调
    def on_video_detected(video):
        print(f"\n🎬 检测到视频!")
        print(f"   标题: {video.title}")
        print(f"   URL: {video.url[:100]}...")
        if video.decryption_key:
            print(f"   密钥: {video.decryption_key[:30]}...")
    
    sniffer.set_on_video_detected(on_video_detected)
    
    try:
        result = await sniffer.start()
        
        if not result.success:
            print(f"  ✗ 启动失败: {result.error_message}")
            await quic_manager.stop_blocking()
            return
        
        print(f"  ✓ mitmproxy 已启动")
        
        # 5. 启动 WinDivert
        print("\n启动 WinDivert 透明捕获...")
        windivert = WinDivertCapture(
            proxy_port=8888,
            target_processes=["WeChat.exe", "WeChatAppEx.exe", "Weixin.exe"]
        )
        
        windivert.PASSIVE_MODE = False
        
        capture_result = await windivert.start()
        
        if not capture_result.success:
            print(f"  ✗ 启动失败: {capture_result.error_message}")
            await sniffer.stop()
            await quic_manager.stop_blocking()
            return
        
        print("  ✓ WinDivert 已启动")
        
        # 6. 等待捕获
        print("\n" + "=" * 60)
        print("准备就绪! (调试模式 - 显示所有流量)")
        print("=" * 60)
        print("\n请在微信 PC 端中播放视频号视频")
        print("按 Ctrl+C 停止监控...")
        print("-" * 60)
        
        last_count = 0
        last_flow_count = 0
        start_time = time.time()
        
        try:
            while True:
                await asyncio.sleep(2)
                
                # 获取检测到的视频
                videos = sniffer.get_detected_videos()
                current_count = len(videos)
                
                # 获取 mitmproxy 流量统计
                status = sniffer.get_status()
                
                # 获取 WinDivert 统计
                windivert_status = windivert.get_status()
                stats = windivert_status.statistics
                
                elapsed = int(time.time() - start_time)
                
                # 显示统计信息
                if elapsed % 5 == 0:
                    print(f"\n[{elapsed}s] 统计:")
                    print(f"  - 视频: {current_count}")
                    print(f"  - WinDivert 包: {stats.packets_intercepted}")
                    print(f"  - WinDivert 重定向: {stats.connections_redirected}")
                    print(f"  - mitmproxy 流: {status.videos_detected}")
                
                # 如果有新视频
                if current_count > last_count:
                    print(f"\n✓ 新视频! 总数: {current_count}")
                    for i, video in enumerate(videos[last_count:], start=last_count+1):
                        print(f"\n[{i}] {video.title}")
                        print(f"    URL: {video.url[:80]}...")
                    last_count = current_count
                    
        except KeyboardInterrupt:
            print("\n\n用户中断")
        
        # 7. 显示结果
        print("\n" + "=" * 60)
        print("捕获结果")
        print("=" * 60)
        
        videos = sniffer.get_detected_videos()
        if videos:
            print(f"\n✓ 共检测到 {len(videos)} 个视频:")
            for i, video in enumerate(videos, 1):
                print(f"\n[{i}] {video.title}")
                print(f"    ID: {video.id}")
                print(f"    URL: {video.url[:80]}...")
        else:
            print("\n✗ 未检测到视频")
            
            # 显示详细统计
            windivert_status = windivert.get_status()
            stats = windivert_status.statistics
            
            print(f"\nWinDivert 统计:")
            print(f"  - 拦截包数: {stats.packets_intercepted}")
            print(f"  - 重定向连接: {stats.connections_redirected}")
            print(f"  - 检测到的 SNI: {stats.snis_extracted}")
            
            if stats.packets_intercepted == 0:
                print("\n⚠️  WinDivert 没有拦截到任何包")
                print("可能原因:")
                print("  1. 微信没有产生网络请求（视频已缓存）")
                print("  2. 防火墙阻止了 WinDivert")
                print("  3. 微信使用了其他网络接口")
            elif stats.connections_redirected == 0:
                print("\n⚠️  WinDivert 拦截了包但没有重定向")
                print("可能原因:")
                print("  1. 流量不是目标域名")
                print("  2. 进程过滤没有匹配到微信")
            else:
                print("\n⚠️  流量已重定向但 mitmproxy 没有检测到视频")
                print("可能原因:")
                print("  1. URL 模式不匹配")
                print("  2. 视频使用了新的 URL 格式")
                print("  3. 需要更新 URL 匹配规则")
        
    finally:
        # 8. 清理
        print("\n清理资源...")
        if windivert is not None:
            await windivert.stop()
        if sniffer is not None:
            await sniffer.stop()
        if quic_manager is not None:
            await quic_manager.stop_blocking()
        print("✓ 清理完成")
    
    print("\n" + "=" * 60)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n程序已中断")
    except Exception as e:
        print(f"\n✗ 错误: {e}")
        import traceback
        traceback.print_exc()

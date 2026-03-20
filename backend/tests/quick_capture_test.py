"""
快速视频捕获测试（自动运行，无需交互）

测试 WinDivert 在 Clash 环境下是否能正常捕获微信视频号流量
"""

import sys
import time
import asyncio
from pathlib import Path
from datetime import datetime

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


async def main():
    """主函数"""
    print("=" * 70)
    print("  快速视频捕获测试")
    print("=" * 70)
    print("\n开始测试 WinDivert 捕获功能...")
    print("监控时间: 15 秒")
    print("请在微信视频号中播放视频\n")

    try:
        from src.core.channels.traffic_capture import WinDivertCapture

        # 创建捕获服务
        capture = WinDivertCapture(
            proxy_port=8888,
            target_processes=["WeChat.exe", "WeChatAppEx.exe", "Weixin.exe"]
        )

        # 启用被动嗅探模式
        capture.PASSIVE_MODE = True

        # 记录检测结果
        detected_count = 0
        detected_items = []

        def on_sni_detected(sni: str, dst_ip: str, dst_port: int):
            """SNI 检测回调"""
            nonlocal detected_count
            detected_count += 1

            timestamp = datetime.now().strftime("%H:%M:%S")

            if sni.startswith('http://') or sni.startswith('https://'):
                print(f"[{timestamp}] 🎬 视频 URL: {sni[:80]}...")
                detected_items.append(('url', sni, dst_ip, dst_port))
            elif sni.startswith('ip:') or sni.startswith('proxy:'):
                print(f"[{timestamp}] 📡 视频 IP: {dst_ip}:{dst_port}")
                detected_items.append(('ip', sni, dst_ip, dst_port))
            else:
                print(f"[{timestamp}] 🔗 视频 SNI: {sni} -> {dst_ip}:{dst_port}")
                detected_items.append(('sni', sni, dst_ip, dst_port))

        capture.set_on_sni_detected(on_sni_detected)

        # 启动捕获
        print("启动捕获服务...\n")
        result = await capture.start()

        if not result.success:
            print(f"✗ 启动失败: {result.error_message}")
            if result.error_code == "ADMIN_REQUIRED":
                print("  请以管理员身份运行应用")
            return

        print("✓ 捕获服务已启动")
        print("-" * 70)

        # 监控 15 秒
        start_time = time.time()
        last_stats_time = start_time

        for i in range(15):
            await asyncio.sleep(1)

            # 每 5 秒显示统计
            if i > 0 and i % 5 == 0:
                status = capture.get_status()
                stats = status.statistics
                print(f"\n[{i}s] 统计: 数据包={stats.packets_intercepted}, "
                      f"连接={stats.connections_redirected}, "
                      f"检测={detected_count}")

        # 停止捕获
        print("\n\n停止捕获服务...")
        await capture.stop()

        # 显示结果
        print("\n" + "=" * 70)
        print("  测试结果")
        print("=" * 70)

        status = capture.get_status()
        stats = status.statistics

        print(f"\n捕获统计:")
        print(f"  拦截数据包: {stats.packets_intercepted}")
        print(f"  分析连接: {stats.connections_redirected}")
        print(f"  检测视频: {detected_count}")

        if detected_count > 0:
            print(f"\n✅ 成功！检测到 {detected_count} 个视频相关项")

            # 显示详情
            if detected_items:
                print("\n检测详情:")
                for i, (item_type, value, ip, port) in enumerate(detected_items[:5], 1):
                    print(f"\n  {i}. 类型: {item_type.upper()}")
                    if item_type == 'url':
                        print(f"     URL: {value[:100]}...")
                    else:
                        print(f"     值: {value}")
                    print(f"     目标: {ip}:{port}")

                if len(detected_items) > 5:
                    print(f"\n  ... 还有 {len(detected_items) - 5} 项")
        else:
            print("\n⚠️  未检测到视频")
            print("\n可能的原因:")
            print("  1. 未在微信视频号中播放视频")
            print("  2. Clash 规则未生效（流量仍被代理）")
            print("  3. 视频使用了 QUIC 协议")

            if stats.packets_intercepted == 0:
                print("\n⚠️  未拦截到任何数据包")
                print("  建议:")
                print("  - 检查是否以管理员身份运行")
                print("  - 检查微信是否正在运行")
                print("  - 尝试关闭 Clash 代理")
            elif stats.packets_intercepted > 0 and stats.connections_redirected == 0:
                print("\n⚠️  拦截了数据包但未识别到目标流量")
                print("  建议:")
                print("  - 确认 Clash 规则已生效（微信流量直连）")
                print("  - 在微信中播放视频号视频")

        print("\n" + "=" * 70)

    except KeyboardInterrupt:
        print("\n\n测试被中断")
    except Exception as e:
        print(f"\n✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())

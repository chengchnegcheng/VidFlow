"""
QUIC 协议屏蔽器

通过防火墙规则屏蔽 QUIC 协议（UDP/443），强制微信使用 HTTP/HTTPS
"""

import logging
import subprocess
import platform
from typing import Optional

logger = logging.getLogger(__name__)


class QUICBlocker:
    """QUIC 协议屏蔽器"""
    
    def __init__(self):
        """初始化"""
        self.is_blocked = False
        self.rule_name = "VidFlow_Block_QUIC"
        self.system = platform.system()
    
    def block_quic(self) -> bool:
        """屏蔽 QUIC 协议
        
        Returns:
            是否成功
        """
        if self.is_blocked:
            logger.info("QUIC 已经被屏蔽")
            return True
        
        try:
            if self.system == "Windows":
                return self._block_quic_windows()
            elif self.system == "Linux":
                return self._block_quic_linux()
            elif self.system == "Darwin":  # macOS
                return self._block_quic_macos()
            else:
                logger.error(f"不支持的操作系统: {self.system}")
                return False
        except Exception as e:
            logger.exception(f"屏蔽 QUIC 失败: {e}")
            return False
    
    def unblock_quic(self) -> bool:
        """解除 QUIC 屏蔽
        
        Returns:
            是否成功
        """
        if not self.is_blocked:
            logger.info("QUIC 未被屏蔽")
            return True
        
        try:
            if self.system == "Windows":
                return self._unblock_quic_windows()
            elif self.system == "Linux":
                return self._unblock_quic_linux()
            elif self.system == "Darwin":
                return self._unblock_quic_macos()
            else:
                logger.error(f"不支持的操作系统: {self.system}")
                return False
        except Exception as e:
            logger.exception(f"解除 QUIC 屏蔽失败: {e}")
            return False
    
    def _block_quic_windows(self) -> bool:
        """Windows 系统屏蔽 QUIC"""
        try:
            # 检查规则是否已存在
            check_cmd = f'netsh advfirewall firewall show rule name="{self.rule_name}"'
            result = subprocess.run(check_cmd, shell=True, capture_output=True, text=True)
            
            if "未找到" not in result.stdout and "No rules" not in result.stdout:
                logger.info("防火墙规则已存在，先删除")
                self._unblock_quic_windows()
            
            # 添加出站规则：阻止 UDP 443 端口
            cmd = (
                f'netsh advfirewall firewall add rule '
                f'name="{self.rule_name}" '
                f'dir=out '
                f'action=block '
                f'protocol=UDP '
                f'remoteport=443 '
                f'enable=yes'
            )
            
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            
            if result.returncode == 0:
                logger.info("✅ QUIC 协议已屏蔽（UDP/443）")
                self.is_blocked = True
                return True
            else:
                logger.error(f"屏蔽 QUIC 失败: {result.stderr}")
                return False
                
        except Exception as e:
            logger.exception(f"Windows 屏蔽 QUIC 失败: {e}")
            return False
    
    def _unblock_quic_windows(self) -> bool:
        """Windows 系统解除 QUIC 屏蔽"""
        try:
            cmd = f'netsh advfirewall firewall delete rule name="{self.rule_name}"'
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, encoding='gbk', errors='ignore')
            
            # 检查是否成功删除或规则不存在
            # returncode == 0 表示成功删除
            # 如果规则不存在，也认为是成功的（因为目标是确保规则不存在）
            success = result.returncode == 0 or "未找到" in result.stdout or "No rules" in result.stdout
            
            if success:
                logger.info("✅ QUIC 屏蔽已解除")
                self.is_blocked = False
                return True
            else:
                logger.error(f"解除 QUIC 屏蔽失败: {result.stderr}")
                return False
                
        except Exception as e:
            logger.exception(f"Windows 解除 QUIC 屏蔽失败: {e}")
            return False
    
    def _block_quic_linux(self) -> bool:
        """Linux 系统屏蔽 QUIC"""
        try:
            # 使用 iptables 屏蔽 UDP 443
            cmd = "iptables -A OUTPUT -p udp --dport 443 -j DROP"
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            
            if result.returncode == 0:
                logger.info("✅ QUIC 协议已屏蔽（UDP/443）")
                self.is_blocked = True
                return True
            else:
                logger.error(f"屏蔽 QUIC 失败: {result.stderr}")
                return False
                
        except Exception as e:
            logger.exception(f"Linux 屏蔽 QUIC 失败: {e}")
            return False
    
    def _unblock_quic_linux(self) -> bool:
        """Linux 系统解除 QUIC 屏蔽"""
        try:
            cmd = "iptables -D OUTPUT -p udp --dport 443 -j DROP"
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            
            if result.returncode == 0:
                logger.info("✅ QUIC 屏蔽已解除")
                self.is_blocked = False
                return True
            else:
                logger.error(f"解除 QUIC 屏蔽失败: {result.stderr}")
                return False
                
        except Exception as e:
            logger.exception(f"Linux 解除 QUIC 屏蔽失败: {e}")
            return False
    
    def _block_quic_macos(self) -> bool:
        """macOS 系统屏蔽 QUIC"""
        try:
            # 使用 pfctl 屏蔽 UDP 443
            # 注意：macOS 需要创建 pf 规则文件
            logger.warning("macOS QUIC 屏蔽功能尚未实现")
            return False
                
        except Exception as e:
            logger.exception(f"macOS 屏蔽 QUIC 失败: {e}")
            return False
    
    def _unblock_quic_macos(self) -> bool:
        """macOS 系统解除 QUIC 屏蔽"""
        try:
            logger.warning("macOS QUIC 屏蔽功能尚未实现")
            return False
                
        except Exception as e:
            logger.exception(f"macOS 解除 QUIC 屏蔽失败: {e}")
            return False
    
    def check_status(self) -> dict:
        """检查 QUIC 屏蔽状态
        
        Returns:
            状态信息
        """
        if self.system == "Windows":
            try:
                cmd = f'netsh advfirewall firewall show rule name="{self.rule_name}"'
                result = subprocess.run(cmd, shell=True, capture_output=True, text=True, encoding='gbk', errors='ignore')
                
                # 检查输出中是否包含规则信息
                # 如果找不到规则，输出会包含 "未找到" 或 "No rules"
                is_blocked = "未找到" not in result.stdout and "No rules" not in result.stdout and result.returncode == 0
                
                # 更新内部状态
                self.is_blocked = is_blocked
                
                return {
                    "is_blocked": is_blocked,
                    "system": self.system,
                    "rule_name": self.rule_name,
                }
            except Exception as e:
                logger.exception(f"检查状态失败: {e}")
                return {
                    "is_blocked": False,
                    "system": self.system,
                    "error": str(e),
                }
        else:
            return {
                "is_blocked": self.is_blocked,
                "system": self.system,
            }

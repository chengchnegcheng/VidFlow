"""
ECH加密处理器

处理ECH(Encrypted Client Hello)加密场景，提供替代识别方案。
当TLS使用ECH导致SNI无法提取时，使用IP-based识别。

Validates: Requirements 3.1, 3.2, 3.3, 3.4
"""

import logging
import ipaddress
from typing import Optional, List, Set
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class TLSInfo:
    """TLS连接信息"""
    has_ech: bool
    sni: Optional[str]
    ech_config_id: Optional[bytes]
    cipher_suites: List[int]
    tls_version: int

    def to_dict(self):
        return {
            "has_ech": self.has_ech,
            "sni": self.sni,
            "ech_config_id": self.ech_config_id.hex() if self.ech_config_id else None,
            "cipher_suites": self.cipher_suites,
            "tls_version": self.tls_version,
        }


class ECHHandler:
    """ECH加密处理器
    
    处理ECH加密场景，提供IP-based识别替代方案。
    Validates: Requirements 3.1, 3.2, 3.3, 3.4
    """
    
    # 腾讯CDN IP段（视频服务器）
    TENCENT_CDN_RANGES = [
        "183.3.0.0/16",
        "183.47.0.0/16",
        "183.60.0.0/16",
        "14.17.0.0/16",
        "14.18.0.0/16",
        "113.96.0.0/16",
        "119.147.0.0/16",
        "125.39.0.0/16",
        "180.163.0.0/16",
        "203.205.0.0/16",
        "111.161.0.0/16",
        "123.151.0.0/16",
        "140.207.0.0/16",
        "182.254.0.0/16",
        "59.37.0.0/16",
        "59.36.0.0/16",
        "101.226.0.0/16",
        "101.227.0.0/16",
        "163.177.0.0/16",
        "220.249.0.0/16",
    ]
    
    # TLS扩展类型
    TLS_EXT_SNI = 0
    TLS_EXT_ECH = 0xfe0d  # Encrypted Client Hello
    TLS_EXT_ENCRYPTED_CLIENT_HELLO = 0xfe0d
    
    def __init__(self):
        """初始化ECH处理器"""
        self._ip_networks: List[ipaddress.IPv4Network] = []
        self._load_ip_ranges()
    
    def _load_ip_ranges(self) -> None:
        """加载IP段"""
        self._ip_networks = []
        for cidr in self.TENCENT_CDN_RANGES:
            try:
                network = ipaddress.ip_network(cidr, strict=False)
                self._ip_networks.append(network)
            except ValueError as e:
                logger.warning(f"Invalid CIDR: {cidr}, error: {e}")

    @staticmethod
    def parse_tls_client_hello(payload: bytes) -> Optional[TLSInfo]:
        """解析TLS ClientHello，检测ECH
        
        Args:
            payload: TLS记录数据
            
        Returns:
            TLSInfo: 解析结果，如果不是有效的ClientHello则返回None
        Validates: Requirements 3.1
        """
        if len(payload) < 5:
            return None
        
        # TLS记录头
        content_type = payload[0]
        if content_type != 0x16:  # Handshake
            return None
        
        tls_version = (payload[1] << 8) | payload[2]
        record_length = (payload[3] << 8) | payload[4]
        
        if len(payload) < 5 + record_length:
            return None
        
        handshake = payload[5:5 + record_length]
        if len(handshake) < 4:
            return None
        
        # Handshake头
        handshake_type = handshake[0]
        if handshake_type != 0x01:  # ClientHello
            return None
        
        handshake_length = (handshake[1] << 16) | (handshake[2] << 8) | handshake[3]
        if len(handshake) < 4 + handshake_length:
            return None
        
        client_hello = handshake[4:4 + handshake_length]
        
        # 解析ClientHello
        try:
            return ECHHandler._parse_client_hello_body(client_hello, tls_version)
        except Exception as e:
            logger.debug(f"Failed to parse ClientHello: {e}")
            return None
    
    @staticmethod
    def _parse_client_hello_body(data: bytes, tls_version: int) -> TLSInfo:
        """解析ClientHello主体"""
        pos = 0
        
        # 版本 (2 bytes)
        pos += 2
        
        # Random (32 bytes)
        pos += 32
        
        # Session ID
        if pos >= len(data):
            raise ValueError("Truncated ClientHello")
        session_id_len = data[pos]
        pos += 1 + session_id_len
        
        # Cipher Suites
        if pos + 2 > len(data):
            raise ValueError("Truncated ClientHello")
        cipher_suites_len = (data[pos] << 8) | data[pos + 1]
        pos += 2
        
        cipher_suites = []
        for i in range(0, cipher_suites_len, 2):
            if pos + i + 2 <= len(data):
                suite = (data[pos + i] << 8) | data[pos + i + 1]
                cipher_suites.append(suite)
        pos += cipher_suites_len
        
        # Compression Methods
        if pos >= len(data):
            raise ValueError("Truncated ClientHello")
        compression_len = data[pos]
        pos += 1 + compression_len
        
        # Extensions
        sni = None
        has_ech = False
        ech_config_id = None
        
        if pos + 2 <= len(data):
            extensions_len = (data[pos] << 8) | data[pos + 1]
            pos += 2
            
            ext_end = pos + extensions_len
            while pos + 4 <= ext_end and pos + 4 <= len(data):
                ext_type = (data[pos] << 8) | data[pos + 1]
                ext_len = (data[pos + 2] << 8) | data[pos + 3]
                pos += 4
                
                if pos + ext_len > len(data):
                    break
                
                ext_data = data[pos:pos + ext_len]
                
                if ext_type == ECHHandler.TLS_EXT_SNI:
                    sni = ECHHandler._parse_sni_extension(ext_data)
                elif ext_type == ECHHandler.TLS_EXT_ECH:
                    has_ech = True
                    if len(ext_data) >= 2:
                        ech_config_id = ext_data[:2]
                
                pos += ext_len
        
        return TLSInfo(
            has_ech=has_ech,
            sni=sni,
            ech_config_id=ech_config_id,
            cipher_suites=cipher_suites,
            tls_version=tls_version,
        )
    
    @staticmethod
    def _parse_sni_extension(data: bytes) -> Optional[str]:
        """解析SNI扩展"""
        if len(data) < 5:
            return None
        
        # SNI列表长度
        list_len = (data[0] << 8) | data[1]
        if len(data) < 2 + list_len:
            return None
        
        pos = 2
        while pos + 3 <= len(data):
            name_type = data[pos]
            name_len = (data[pos + 1] << 8) | data[pos + 2]
            pos += 3
            
            if pos + name_len > len(data):
                break
            
            if name_type == 0:  # host_name
                try:
                    return data[pos:pos + name_len].decode('ascii')
                except:
                    pass
            
            pos += name_len
        
        return None

    @staticmethod
    def has_ech_extension(payload: bytes) -> bool:
        """检查是否包含ECH扩展
        
        Args:
            payload: TLS记录数据
            
        Returns:
            bool: 是否包含ECH扩展
        Validates: Requirements 3.1
        """
        info = ECHHandler.parse_tls_client_hello(payload)
        return info.has_ech if info else False
    
    def is_video_server_ip(self, ip: str) -> bool:
        """检查IP是否属于视频服务器
        
        Args:
            ip: IP地址字符串
            
        Returns:
            bool: 是否为视频服务器IP
        Validates: Requirements 3.2, 3.4
        """
        try:
            ip_addr = ipaddress.ip_address(ip)
            for network in self._ip_networks:
                if ip_addr in network:
                    return True
            return False
        except ValueError:
            return False
    
    def get_ip_ranges(self) -> List[str]:
        """获取当前IP段列表
        
        Returns:
            List[str]: CIDR格式的IP段列表
        """
        return self.TENCENT_CDN_RANGES.copy()
    
    def add_ip_range(self, cidr: str) -> bool:
        """添加IP段
        
        Args:
            cidr: CIDR格式的IP段
            
        Returns:
            bool: 是否添加成功
        """
        try:
            network = ipaddress.ip_network(cidr, strict=False)
            if network not in self._ip_networks:
                self._ip_networks.append(network)
            return True
        except ValueError:
            return False
    
    def remove_ip_range(self, cidr: str) -> bool:
        """移除IP段
        
        Args:
            cidr: CIDR格式的IP段
            
        Returns:
            bool: 是否移除成功
        """
        try:
            network = ipaddress.ip_network(cidr, strict=False)
            if network in self._ip_networks:
                self._ip_networks.remove(network)
                return True
            return False
        except ValueError:
            return False
    
    async def update_ip_database(self) -> None:
        """更新视频服务器IP数据库
        
        从远程获取最新的IP段列表。
        Validates: Requirements 3.3
        """
        # TODO: 实现从远程服务器获取最新IP段
        # 目前使用静态列表
        logger.info("IP database update not implemented, using static list")
        pass
    
    def identify_connection(self, payload: bytes, dst_ip: str) -> dict:
        """识别连接
        
        综合使用SNI和IP识别连接。
        
        Args:
            payload: TLS ClientHello数据
            dst_ip: 目标IP
            
        Returns:
            dict: 识别结果
        Validates: Requirements 3.2, 3.4
        """
        result = {
            "identified": False,
            "method": None,
            "sni": None,
            "is_video_ip": False,
            "has_ech": False,
        }
        
        # 尝试解析TLS
        tls_info = self.parse_tls_client_hello(payload)
        if tls_info:
            result["has_ech"] = tls_info.has_ech
            result["sni"] = tls_info.sni
            
            if tls_info.sni:
                result["identified"] = True
                result["method"] = "sni"
                return result
        
        # SNI不可用，尝试IP识别
        if self.is_video_server_ip(dst_ip):
            result["identified"] = True
            result["method"] = "ip"
            result["is_video_ip"] = True
        
        return result

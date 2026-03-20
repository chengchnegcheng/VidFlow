"""
Clash API监控器

通过Clash RESTful API监控连接，无需修改流量。
支持/connections端点轮询和WebSocket流式监控。

Validates: Requirements 5.1, 5.2, 5.3, 5.4, 5.5, 5.6
"""

import logging
import asyncio
import re
from datetime import datetime
from typing import Optional, List, Dict, Any, AsyncIterator, Callable
from dataclasses import dataclass, field

try:
    import aiohttp
    HAS_AIOHTTP = True
except ImportError:
    HAS_AIOHTTP = False

logger = logging.getLogger(__name__)


@dataclass
class ClashConnection:
    """Clash连接信息"""
    id: str
    host: str
    dst_ip: str
    dst_port: int
    src_ip: str
    src_port: int
    network: str  # tcp/udp
    type: str     # HTTP/HTTPS/SOCKS5
    rule: str
    rule_payload: str
    chains: List[str] = field(default_factory=list)
    download: int = 0
    upload: int = 0
    start: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "host": self.host,
            "dst_ip": self.dst_ip,
            "dst_port": self.dst_port,
            "src_ip": self.src_ip,
            "src_port": self.src_port,
            "network": self.network,
            "type": self.type,
            "rule": self.rule,
            "rule_payload": self.rule_payload,
            "chains": self.chains,
            "download": self.download,
            "upload": self.upload,
            "start": self.start.isoformat(),
        }


class ClashAPIMonitor:
    """Clash API监控器

    通过Clash RESTful API监控连接。
    Validates: Requirements 5.1, 5.2, 5.3, 5.4, 5.5, 5.6
    """

    # 视频号相关域名模式
    VIDEO_DOMAIN_PATTERNS = [
        r'finder\.video\.qq\.com',
        r'findermp\.video\.qq\.com',
        r'wxapp\.tc\.qq\.com',
        r'channels\.weixin\.qq\.com',
        r'szextshort\.weixin\.qq\.com',
        r'szvideo\.weixin\.qq\.com',
        r'vd\d?\.video\.qq\.com',
        r'.*\.tc\.qq\.com',
    ]

    def __init__(self, api_address: str = "127.0.0.1:9090", api_secret: Optional[str] = None):
        """初始化Clash API监控器

        Args:
            api_address: Clash API地址 (host:port)
            api_secret: API密钥
        """
        self.api_address = api_address
        self.api_secret = api_secret
        self._session: Optional[aiohttp.ClientSession] = None
        self._is_connected = False
        self._polling_task: Optional[asyncio.Task] = None
        self._on_connection_callback: Optional[Callable[[ClashConnection], None]] = None
        self._compiled_patterns = [re.compile(p, re.IGNORECASE) for p in self.VIDEO_DOMAIN_PATTERNS]

    @property
    def base_url(self) -> str:
        addr = self.api_address
        if not addr.startswith(("http://", "https://")):
            addr = f"http://{addr}"
        return addr

    @property
    def headers(self) -> Dict[str, str]:
        h = {"Content-Type": "application/json"}
        if self.api_secret:
            h["Authorization"] = f"Bearer {self.api_secret}"
        return h

    async def connect(self) -> bool:
        """连接到Clash API

        Returns:
            bool: 连接是否成功
        Validates: Requirements 5.1, 5.6
        """
        if not HAS_AIOHTTP:
            logger.error("aiohttp not available")
            return False

        try:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=10),
                headers=self.headers
            )
            # 测试连接
            async with self._session.get(f"{self.base_url}/version") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    logger.info(f"Connected to Clash API, version: {data.get('version', 'unknown')}")
                    self._is_connected = True
                    return True
                elif resp.status == 401:
                    logger.error("Clash API authentication failed")
                    return False
                else:
                    logger.error(f"Clash API returned status {resp.status}")
                    return False
        except aiohttp.ClientError as e:
            logger.error(f"Failed to connect to Clash API: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error connecting to Clash API: {e}")
            return False

    async def disconnect(self) -> None:
        """断开连接"""
        self._is_connected = False
        if self._polling_task:
            self._polling_task.cancel()
            self._polling_task = None
        if self._session:
            await self._session.close()
            self._session = None

    @property
    def is_connected(self) -> bool:
        return self._is_connected

    async def get_connections(self) -> List[ClashConnection]:
        """获取当前所有连接

        Returns:
            List[ClashConnection]: 连接列表
        Validates: Requirements 5.2
        """
        if not self._session or not self._is_connected:
            return []

        try:
            async with self._session.get(f"{self.base_url}/connections") as resp:
                if resp.status != 200:
                    logger.warning(f"Failed to get connections: status {resp.status}")
                    return []

                data = await resp.json()
                connections = []

                for conn_data in data.get("connections", []):
                    try:
                        metadata = conn_data.get("metadata", {})
                        conn = ClashConnection(
                            id=conn_data.get("id", ""),
                            host=metadata.get("host", ""),
                            dst_ip=metadata.get("destinationIP", ""),
                            dst_port=int(metadata.get("destinationPort", 0)),
                            src_ip=metadata.get("sourceIP", ""),
                            src_port=int(metadata.get("sourcePort", 0)),
                            network=metadata.get("network", "tcp"),
                            type=metadata.get("type", ""),
                            rule=conn_data.get("rule", ""),
                            rule_payload=conn_data.get("rulePayload", ""),
                            chains=conn_data.get("chains", []),
                            download=conn_data.get("download", 0),
                            upload=conn_data.get("upload", 0),
                            start=self._parse_time(conn_data.get("start", "")),
                        )
                        connections.append(conn)
                    except Exception as e:
                        logger.debug(f"Failed to parse connection: {e}")
                        continue

                return connections
        except Exception as e:
            logger.error(f"Error getting connections: {e}")
            return []

    def _parse_time(self, time_str: str) -> datetime:
        """解析时间字符串"""
        if not time_str:
            return datetime.now()
        try:
            # Clash使用RFC3339格式
            return datetime.fromisoformat(time_str.replace("Z", "+00:00"))
        except:
            return datetime.now()

    def filter_video_connections(self, connections: List[ClashConnection]) -> List[ClashConnection]:
        """过滤出视频号相关连接

        Args:
            connections: 所有连接

        Returns:
            List[ClashConnection]: 视频相关连接
        Validates: Requirements 5.3
        """
        video_connections = []
        for conn in connections:
            if self.is_video_connection(conn):
                video_connections.append(conn)
        return video_connections

    def is_video_connection(self, conn: ClashConnection) -> bool:
        """判断是否为视频相关连接"""
        host = conn.host or conn.dst_ip
        if not host:
            return False

        for pattern in self._compiled_patterns:
            if pattern.search(host):
                return True
        return False

    async def get_traffic_stats(self) -> Dict[str, int]:
        """获取流量统计

        Returns:
            Dict with 'download' and 'upload' bytes
        """
        if not self._session or not self._is_connected:
            return {"download": 0, "upload": 0}

        try:
            async with self._session.get(f"{self.base_url}/traffic") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return {
                        "download": data.get("down", 0),
                        "upload": data.get("up", 0),
                    }
        except:
            pass
        return {"download": 0, "upload": 0}

    async def start_polling(self, interval: float = 1.0, callback: Optional[Callable[[ClashConnection], None]] = None) -> None:
        """开始轮询连接

        Args:
            interval: 轮询间隔（秒）
            callback: 发现新视频连接时的回调
        Validates: Requirements 5.2
        """
        self._on_connection_callback = callback
        self._polling_task = asyncio.create_task(self._poll_loop(interval))

    async def stop_polling(self) -> None:
        """停止轮询"""
        if self._polling_task:
            self._polling_task.cancel()
            try:
                await self._polling_task
            except asyncio.CancelledError:
                pass
            self._polling_task = None

    async def _poll_loop(self, interval: float) -> None:
        """轮询循环"""
        seen_ids = set()

        while self._is_connected:
            try:
                connections = await self.get_connections()
                video_connections = self.filter_video_connections(connections)

                for conn in video_connections:
                    if conn.id not in seen_ids:
                        seen_ids.add(conn.id)
                        if self._on_connection_callback:
                            try:
                                self._on_connection_callback(conn)
                            except Exception as e:
                                logger.error(f"Callback error: {e}")

                # 清理旧ID
                current_ids = {c.id for c in connections}
                seen_ids = seen_ids & current_ids

                await asyncio.sleep(interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Polling error: {e}")
                await asyncio.sleep(interval)

    async def stream_connections(self) -> AsyncIterator[ClashConnection]:
        """流式获取新连接（WebSocket）

        Yields:
            ClashConnection: 新检测到的视频连接
        Validates: Requirements 5.2 (optional WebSocket mode)
        """
        if not self._session or not self._is_connected:
            return

        seen_ids = set()
        ws_url = f"{self.base_url.replace('http', 'ws')}/connections"

        try:
            async with self._session.ws_connect(ws_url) as ws:
                async for msg in ws:
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        try:
                            data = msg.json()
                            for conn_data in data.get("connections", []):
                                conn_id = conn_data.get("id", "")
                                if conn_id and conn_id not in seen_ids:
                                    metadata = conn_data.get("metadata", {})
                                    conn = ClashConnection(
                                        id=conn_id,
                                        host=metadata.get("host", ""),
                                        dst_ip=metadata.get("destinationIP", ""),
                                        dst_port=int(metadata.get("destinationPort", 0)),
                                        src_ip=metadata.get("sourceIP", ""),
                                        src_port=int(metadata.get("sourcePort", 0)),
                                        network=metadata.get("network", "tcp"),
                                        type=metadata.get("type", ""),
                                        rule=conn_data.get("rule", ""),
                                        rule_payload=conn_data.get("rulePayload", ""),
                                        chains=conn_data.get("chains", []),
                                        download=conn_data.get("download", 0),
                                        upload=conn_data.get("upload", 0),
                                    )
                                    if self.is_video_connection(conn):
                                        seen_ids.add(conn_id)
                                        yield conn
                        except Exception as e:
                            logger.debug(f"Failed to parse WS message: {e}")
                    elif msg.type == aiohttp.WSMsgType.ERROR:
                        break
        except Exception as e:
            logger.error(f"WebSocket error: {e}")

    async def close_connection(self, conn_id: str) -> bool:
        """关闭指定连接

        Args:
            conn_id: 连接ID

        Returns:
            bool: 是否成功
        """
        if not self._session or not self._is_connected:
            return False

        try:
            async with self._session.delete(f"{self.base_url}/connections/{conn_id}") as resp:
                return resp.status == 204
        except:
            return False

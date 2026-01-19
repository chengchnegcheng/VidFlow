"""
HLS 流组装器

解析 .m3u8 清单，记录和组织 HLS 分片。
"""

import re
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlparse
from threading import Lock

from .models import HlsManifest, HlsSegment


logger = logging.getLogger(__name__)


class HlsAssembler:
    """HLS 流组装器
    
    负责解析 .m3u8 清单文件，记录分片 URL，并组织下载。
    """
    
    def __init__(self):
        """初始化 HLS 组装器"""
        self._manifests: Dict[str, HlsManifest] = {}
        self._segments: Dict[str, List[HlsSegment]] = {}
        self._lock = Lock()
    
    def parse_manifest(self, url: str, content: str) -> HlsManifest:
        """解析 .m3u8 清单文件
        
        Args:
            url: 清单 URL
            content: 清单内容
            
        Returns:
            HlsManifest: 解析后的清单对象
        """
        lines = content.strip().split('\n')
        
        # 检查是否为有效的 M3U8 文件
        if not lines or not lines[0].strip().startswith('#EXTM3U'):
            logger.warning(f"Invalid M3U8 content for URL: {url}")
            return HlsManifest(url=url, is_master=False)
        
        # 判断是主清单还是媒体清单
        is_master = self._is_master_playlist(lines)
        
        if is_master:
            return self._parse_master_playlist(url, lines)
        else:
            return self._parse_media_playlist(url, lines)
    
    def _is_master_playlist(self, lines: List[str]) -> bool:
        """判断是否为主清单（包含多个变体流）
        
        Args:
            lines: 清单内容行
            
        Returns:
            是主清单返回 True
        """
        for line in lines:
            line = line.strip()
            if line.startswith('#EXT-X-STREAM-INF:'):
                return True
            if line.startswith('#EXT-X-MEDIA:'):
                return True
        return False
    
    def _parse_master_playlist(self, url: str, lines: List[str]) -> HlsManifest:
        """解析主清单
        
        Args:
            url: 清单 URL
            lines: 清单内容行
            
        Returns:
            HlsManifest: 主清单对象
        """
        variants = []
        
        for i, line in enumerate(lines):
            line = line.strip()
            if line.startswith('#EXT-X-STREAM-INF:'):
                # 下一行是变体流 URL
                if i + 1 < len(lines):
                    variant_url = lines[i + 1].strip()
                    if variant_url and not variant_url.startswith('#'):
                        # 处理相对 URL
                        variant_url = urljoin(url, variant_url)
                        variants.append(variant_url)
        
        manifest = HlsManifest(
            url=url,
            is_master=True,
            variants=variants,
            detected_at=datetime.now(),
        )
        
        with self._lock:
            self._manifests[url] = manifest
        
        logger.info(f"Parsed master playlist: {url}, variants: {len(variants)}")
        return manifest

    def _parse_media_playlist(self, url: str, lines: List[str]) -> HlsManifest:
        """解析媒体清单
        
        Args:
            url: 清单 URL
            lines: 清单内容行
            
        Returns:
            HlsManifest: 媒体清单对象
        """
        segments = []
        total_duration = 0.0
        current_duration = 0.0
        sequence = 0
        
        # 查找起始序号
        for line in lines:
            line = line.strip()
            if line.startswith('#EXT-X-MEDIA-SEQUENCE:'):
                try:
                    sequence = int(line.split(':')[1])
                except (ValueError, IndexError):
                    pass
                break
        
        # 解析分片
        for i, line in enumerate(lines):
            line = line.strip()
            
            if line.startswith('#EXTINF:'):
                # 提取分片时长
                try:
                    duration_str = line.split(':')[1].split(',')[0]
                    current_duration = float(duration_str)
                except (ValueError, IndexError):
                    current_duration = 0.0
            
            elif line and not line.startswith('#'):
                # 这是一个分片 URL
                segment_url = urljoin(url, line)
                
                segment = HlsSegment(
                    url=segment_url,
                    sequence=sequence,
                    duration=current_duration,
                    manifest_url=url,
                    detected_at=datetime.now(),
                )
                segments.append(segment)
                
                total_duration += current_duration
                sequence += 1
                current_duration = 0.0
        
        manifest = HlsManifest(
            url=url,
            is_master=False,
            duration=total_duration,
            segment_count=len(segments),
            detected_at=datetime.now(),
        )
        
        with self._lock:
            self._manifests[url] = manifest
            self._segments[url] = segments
        
        logger.info(f"Parsed media playlist: {url}, segments: {len(segments)}, duration: {total_duration:.2f}s")
        return manifest
    
    def add_segment(self, manifest_url: str, segment: HlsSegment) -> None:
        """添加分片到对应的清单
        
        Args:
            manifest_url: 清单 URL
            segment: 分片对象
        """
        with self._lock:
            if manifest_url not in self._segments:
                self._segments[manifest_url] = []
            
            # 检查是否已存在（按 URL 去重）
            existing_urls = {s.url for s in self._segments[manifest_url]}
            if segment.url not in existing_urls:
                self._segments[manifest_url].append(segment)
                
                # 更新清单的分片计数
                if manifest_url in self._manifests:
                    self._manifests[manifest_url].segment_count = len(self._segments[manifest_url])
    
    def get_all_segments(self, manifest_url: str) -> List[HlsSegment]:
        """获取清单的所有分片 URL
        
        Args:
            manifest_url: 清单 URL
            
        Returns:
            分片列表，按序号排序
        """
        with self._lock:
            segments = self._segments.get(manifest_url, [])
            return sorted(segments, key=lambda s: s.sequence)
    
    def get_manifest(self, url: str) -> Optional[HlsManifest]:
        """获取清单对象
        
        Args:
            url: 清单 URL
            
        Returns:
            HlsManifest 对象，如果不存在返回 None
        """
        with self._lock:
            return self._manifests.get(url)
    
    def is_complete(self, manifest_url: str) -> bool:
        """检查清单的所有分片是否已检测到
        
        Args:
            manifest_url: 清单 URL
            
        Returns:
            所有分片已检测到返回 True
        """
        with self._lock:
            manifest = self._manifests.get(manifest_url)
            if not manifest:
                return False
            
            if manifest.is_master:
                # 主清单：检查所有变体是否已解析
                return all(v in self._manifests for v in manifest.variants)
            else:
                # 媒体清单：检查分片数量是否匹配
                segments = self._segments.get(manifest_url, [])
                return len(segments) >= manifest.segment_count
    
    def get_segment_urls(self, manifest_url: str) -> List[str]:
        """获取清单的所有分片 URL 列表
        
        Args:
            manifest_url: 清单 URL
            
        Returns:
            分片 URL 列表，按序号排序
        """
        segments = self.get_all_segments(manifest_url)
        return [s.url for s in segments]
    
    def clear(self) -> None:
        """清空所有清单和分片数据"""
        with self._lock:
            self._manifests.clear()
            self._segments.clear()
    
    def remove_manifest(self, url: str) -> None:
        """移除指定清单及其分片
        
        Args:
            url: 清单 URL
        """
        with self._lock:
            self._manifests.pop(url, None)
            self._segments.pop(url, None)
    
    def get_total_duration(self, manifest_url: str) -> float:
        """获取清单的总时长
        
        Args:
            manifest_url: 清单 URL
            
        Returns:
            总时长（秒），如果无法计算返回 0
        """
        with self._lock:
            manifest = self._manifests.get(manifest_url)
            if manifest and manifest.duration:
                return manifest.duration
            
            # 从分片计算
            segments = self._segments.get(manifest_url, [])
            return sum(s.duration for s in segments)

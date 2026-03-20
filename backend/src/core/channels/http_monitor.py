"""
HTTP traffic monitor for Channels video URLs.

The monitor now reports a candidate only after the HTTP response is confirmed
to be video data, which prevents image/jpg thumbnail traffic from polluting
the detected video list.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Callable, Dict, Optional
from urllib.parse import parse_qs, urlparse

from mitmproxy import http

logger = logging.getLogger(__name__)


class HTTPMonitor:
    """Monitor HTTP flows and emit confirmed Channels video candidates."""

    VIDEO_DOMAINS = (
        "wxapp.tc.qq.com",
        "finder.video.qq.com",
        "findermp.video.qq.com",
    )

    URL_PATTERNS = (
        r"/\d+/\d+/stodownload",
        r"/finder/",
    )

    VIDEO_CONTENT_TYPES = (
        "video/",
        "application/vnd.apple.mpegurl",
        "application/x-mpegurl",
    )

    BINARY_CONTENT_TYPES = (
        "application/octet-stream",
        "binary/octet-stream",
    )

    # Guard rail: thumbnails are usually small image responses.
    MIN_BINARY_VIDEO_SIZE = 300 * 1024

    def __init__(self, on_video_detected: Optional[Callable[[Dict[str, Any]], None]] = None):
        self.on_video_detected = on_video_detected
        self.detected_videos: list[Dict[str, Any]] = []
        self._seen_keys: set[str] = set()

    def is_video_url(self, url: str) -> bool:
        """Return True when URL belongs to Channels video endpoints."""
        try:
            parsed = urlparse(url)
            if not any(domain in parsed.netloc for domain in self.VIDEO_DOMAINS):
                return False
            return any(re.search(pattern, parsed.path) for pattern in self.URL_PATTERNS)
        except Exception as exc:
            logger.debug("Failed to check video URL: %s", exc)
            return False

    def _extract_video_info(self, url: str, response: http.Response) -> Optional[Dict[str, Any]]:
        try:
            parsed = urlparse(url)
            query = parse_qs(parsed.query)
            encfilekey = query.get("encfilekey", [None])[0]
            bizid = query.get("bizid", [None])[0]
            idx = query.get("idx", [None])[0]

            return {
                "url": url,
                "encfilekey": encfilekey,
                "bizid": bizid,
                "idx": idx,
                "domain": parsed.netloc,
                "content_type": response.headers.get("Content-Type", ""),
                "content_length": response.headers.get("Content-Length", "0"),
                "status_code": response.status_code,
            }
        except Exception as exc:
            logger.exception("Failed to extract video info: %s", exc)
            return None

    @staticmethod
    def _parse_content_type(raw_content_type: str) -> str:
        if not raw_content_type:
            return ""
        return raw_content_type.split(";", 1)[0].strip().lower()

    @staticmethod
    def _parse_content_length(raw_content_length: str) -> int:
        try:
            return max(0, int(raw_content_length))
        except Exception:
            return 0

    def _is_confirmed_video_response(self, flow: http.HTTPFlow) -> bool:
        response = flow.response
        if response is None:
            return False

        content_type = self._parse_content_type(response.headers.get("Content-Type", ""))
        content_length = self._parse_content_length(response.headers.get("Content-Length", "0"))

        if any(content_type.startswith(prefix) for prefix in self.VIDEO_CONTENT_TYPES):
            return True

        # Some endpoints may return generic binary streams.
        if content_type in self.BINARY_CONTENT_TYPES and content_length >= self.MIN_BINARY_VIDEO_SIZE:
            return True

        # Last fallback for missing content type on large media.
        if not content_type and content_length >= self.MIN_BINARY_VIDEO_SIZE:
            return True

        return False

    def _make_dedup_key(self, url: str) -> str:
        parsed = urlparse(url)
        query = parse_qs(parsed.query)
        stable_token = (
            query.get("encfilekey", [None])[0]
            or query.get("objectid", [None])[0]
            or query.get("feedid", [None])[0]
        )
        if stable_token:
            return stable_token
        return f"{parsed.netloc}{parsed.path}"

    def process_request(self, flow: http.HTTPFlow) -> None:
        """Keep request hook lightweight; confirmation is done in response."""
        try:
            url = flow.request.pretty_url
            if self.is_video_url(url):
                logger.debug("[HTTPMonitor] Candidate request: %s", url[:140])
        except Exception as exc:
            logger.debug("Failed to process request: %s", exc)

    def process_response(self, flow: http.HTTPFlow) -> None:
        """Process response and emit only confirmed video candidates."""
        try:
            url = flow.request.pretty_url
            if not self.is_video_url(url):
                return
            if flow.response is None:
                return
            if not self._is_confirmed_video_response(flow):
                logger.debug(
                    "[HTTPMonitor] Ignore non-video response: ct=%s url=%s",
                    flow.response.headers.get("Content-Type", ""),
                    url[:140],
                )
                return

            dedup_key = self._make_dedup_key(url)
            if dedup_key in self._seen_keys:
                return
            self._seen_keys.add(dedup_key)

            video_info = self._extract_video_info(url, flow.response)
            if not video_info:
                return

            self.detected_videos.append(video_info)
            logger.info(
                "[HTTPMonitor] Confirmed video: ct=%s size=%s url=%s",
                video_info.get("content_type", ""),
                video_info.get("content_length", "0"),
                url[:140],
            )

            if self.on_video_detected:
                self.on_video_detected(video_info)
        except Exception as exc:
            logger.debug("Failed to process response: %s", exc)

    def get_detected_videos(self) -> list[Dict[str, Any]]:
        return self.detected_videos

    def clear_detected_videos(self) -> None:
        self.detected_videos = []
        self._seen_keys.clear()


class HTTPMonitorAddon:
    """mitmproxy addon wrapper."""

    def __init__(self, monitor: HTTPMonitor):
        self.monitor = monitor

    def request(self, flow: http.HTTPFlow) -> None:
        self.monitor.process_request(flow)

    def response(self, flow: http.HTTPFlow) -> None:
        self.monitor.process_response(flow)

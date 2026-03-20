from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.core.channels.models import ProxyInfo, ProxyMode, ProxyType


class TestChannelsDiagnosticLogs:
    def test_read_recent_channels_log_summary_filters_relevant_lines(self, tmp_path, monkeypatch):
        from src.api import channels

        data_dir = tmp_path / "data"
        logs_dir = data_dir / "logs"
        logs_dir.mkdir(parents=True)
        log_file = logs_dir / "app.log"
        log_file.write_text(
            "\n".join(
                [
                    "2026-03-08 19:04:59,633 - src.core.channels.proxy_sniffer - INFO - [META] Channels response observed: status=200 type=application/octet-stream textual=False url=http://extshort.weixin.qq.com/mmtls/00005602",
                    "2026-03-08 19:05:16,623 - mitmproxy.shutdown - ERROR - Task failed: redirect daemon exited prematurely.",
                    "2026-03-08 19:05:17,000 - unrelated.logger - INFO - ignore me",
                ]
            ),
            encoding="utf-8",
        )

        monkeypatch.setattr(channels, "get_data_dir", lambda: data_dir)

        summary = channels._read_recent_channels_log_summary(
            tail_lines=20,
            match_limit=10,
            critical_limit=5,
        )

        assert summary["log_file"] == str(log_file)
        assert any("[META] Channels response observed" in line for line in summary["lines"])
        assert any("redirect daemon exited prematurely" in line for line in summary["critical_messages"])
        assert all("ignore me" not in line for line in summary["lines"])

    @pytest.mark.asyncio
    async def test_build_frontend_diagnostics_payload_includes_recent_channels_log_summary(self, monkeypatch):
        from src.api import channels

        fake_status = SimpleNamespace(
            state=SimpleNamespace(value="running"),
            error_message=None,
            videos_detected=0,
        )
        fake_sniffer = SimpleNamespace(
            get_runtime_statistics=lambda: {
                "top_hosts": [("finder.video.qq.com", 3)],
                "recent_response_samples": [],
                "request_count": 12,
                "flow_count": 8,
                "mmtls_request_count": 2,
                "channels_page_injection_kind": None,
                "channels_page_injection_url": None,
                "channels_page_injection_at": None,
                "renderer_recycle_attempted": True,
                "renderer_recycle_completed": False,
                "renderer_recycle_reason": "channels_web_activity_without_injection",
                "renderer_recycle_at": "2026-03-09T10:00:00",
            },
            get_status=lambda: fake_status,
            get_detected_videos=lambda: [],
        )

        monkeypatch.setattr(channels, "get_sniffer", lambda: fake_sniffer)
        monkeypatch.setattr(
            channels,
            "_detect_proxy_info",
            AsyncMock(
                return_value=ProxyInfo(
                    proxy_type=ProxyType.NONE,
                    proxy_mode=ProxyMode.NONE,
                )
            ),
        )
        monkeypatch.setattr(channels, "_build_proxy_environment_warning", lambda _info: None)
        monkeypatch.setattr(
            channels,
            "get_cert_installer",
            lambda: SimpleNamespace(get_cert_info=lambda: {}),
        )
        monkeypatch.setattr(channels, "_build_channels_certificate_warning", lambda _info: None)
        monkeypatch.setattr(channels, "_detect_admin_status", lambda: True)
        monkeypatch.setattr(channels, "_collect_wechat_processes", lambda: [])
        monkeypatch.setattr(channels, "_generate_recommendations", lambda *_args: [])
        monkeypatch.setattr(
            channels,
            "_read_recent_channels_log_summary",
            lambda: {
                "log_file": "D:/VidFlow/backend/data/logs/app.log",
                "lines": [
                    "19:05:16 ERROR shutdown: Task failed: redirect daemon exited prematurely.",
                ],
                "critical_messages": [
                    "19:05:16 ERROR shutdown: Task failed: redirect daemon exited prematurely.",
                ],
            },
        )

        payload = await channels._build_frontend_diagnostics_payload()

        assert payload["capture_log"] == [
            "19:05:16 ERROR shutdown: Task failed: redirect daemon exited prematurely.",
        ]
        assert any(
            "redirect daemon exited prematurely" in message for message in payload["recent_errors"]
        )
        assert any(
            "VidFlow 现在只记录该问题，不再自动杀进程" in message for message in payload["recent_errors"]
        )
        assert payload["statistics"]["diagnostic_log_file"] == "D:/VidFlow/backend/data/logs/app.log"
        assert payload["statistics"]["diagnostic_log_matches"] == 1
        assert payload["statistics"]["renderer_recycle_attempted"] is True
        assert payload["statistics"]["renderer_recycle_reason"] == "channels_web_activity_without_injection"

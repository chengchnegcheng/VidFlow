"""Shared process target lists for WeChat Channels capture."""

from __future__ import annotations

from typing import Iterable, List, Sequence


CORE_WECHAT_PROCESS_NAMES = [
    "Weixin.exe",
    "WeChat.exe",
    "WeChatAppEx.exe",
    "WeChatApp.exe",
    "WeChatBrowser.exe",
    "WeChatPlayer.exe",
]

CHANNELS_BROWSER_HELPER_PROCESS_NAMES = [
    "QQBrowser.exe",
    "msedgewebview2.exe",
]

# Transparent/local capture must include the helper browser processes used by
# WeChat 4.x Channels pages; otherwise we often only see the rotating
# stodownload URL and miss title/thumbnail/decodeKey metadata.
LOCAL_CAPTURE_TARGET_PROCESSES = list(CORE_WECHAT_PROCESS_NAMES) + list(CHANNELS_BROWSER_HELPER_PROCESS_NAMES)

QUIC_BLOCK_TARGET_PROCESSES = CORE_WECHAT_PROCESS_NAMES + ["WXWork.exe"]

_HELPER_PROCESS_NAMES_LOWER = {
    name.lower() for name in CHANNELS_BROWSER_HELPER_PROCESS_NAMES
}


def dedupe_process_names(processes: Iterable[str]) -> List[str]:
    """Normalize and deduplicate process names while preserving order."""
    normalized: List[str] = []
    seen = set()

    for process in processes:
        name = str(process or "").strip()
        if not name:
            continue

        lowered = name.lower()
        if lowered in seen:
            continue

        seen.add(lowered)
        normalized.append(name)

    return normalized


def resolve_local_capture_processes(processes: Sequence[str] | None = None) -> List[str]:
    """Return the default local-capture process list when none is configured."""
    if not processes:
        return list(LOCAL_CAPTURE_TARGET_PROCESSES)
    return dedupe_process_names(processes)


def resolve_quic_target_processes(processes: Sequence[str] | None = None) -> List[str]:
    """Exclude generic browser helpers from QUIC blocking targets."""
    requested = resolve_local_capture_processes(processes)
    filtered = [
        process
        for process in requested
        if process.lower() not in _HELPER_PROCESS_NAMES_LOWER
    ]
    return filtered or list(QUIC_BLOCK_TARGET_PROCESSES)

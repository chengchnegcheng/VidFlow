import base64
import logging
import os
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional, List, Tuple

logger = logging.getLogger(__name__)

_COOKIE_PREFIX = "VIDFLOW_COOKIE_DPAPI_V1:"
_DPAPI_ENTROPY = b"VidFlowCookieV1"


def _is_windows() -> bool:
    return sys.platform == "win32"


def is_encrypted_cookie_file_text(text: str) -> bool:
    return isinstance(text, str) and text.startswith(_COOKIE_PREFIX)


def validate_netscape_cookie_format(content: str) -> Tuple[bool, List[str], str]:
    """
    验证 Netscape Cookie 格式

    Args:
        content: Cookie 文件内容

    Returns:
        (is_valid, errors, cleaned_content)
        - is_valid: 是否有效
        - errors: 错误列表
        - cleaned_content: 清理后的内容（移除无效行）
    """
    errors = []
    valid_lines = []

    lines = content.split('\n')

    for line_num, line in enumerate(lines, 1):
        # 跳过空行和注释
        stripped = line.strip()
        if not stripped or stripped.startswith('#'):
            valid_lines.append(line)
            continue

        # Netscape Cookie 格式: domain, flag, path, secure, expiration, name, value
        # 使用 tab 分隔，共 7 个字段
        parts = line.split('\t')

        if len(parts) < 7:
            errors.append(f"第 {line_num} 行: 字段数量不足 (需要 7 个字段，实际 {len(parts)} 个)")
            continue

        domain, flag, path, secure, expiration, name, value = parts[0], parts[1], parts[2], parts[3], parts[4], parts[5], parts[6] if len(parts) > 6 else ""

        # 验证必需字段
        if not domain:
            errors.append(f"第 {line_num} 行: domain 为空")
            continue

        if not name:
            errors.append(f"第 {line_num} 行: name 为空")
            continue

        if not path:
            errors.append(f"第 {line_num} 行: path 为空")
            continue

        # 验证 flag 和 secure 字段
        if flag.upper() not in ('TRUE', 'FALSE'):
            errors.append(f"第 {line_num} 行: flag 字段无效 (应为 TRUE 或 FALSE，实际为 '{flag}')")
            continue

        if secure.upper() not in ('TRUE', 'FALSE'):
            errors.append(f"第 {line_num} 行: secure 字段无效 (应为 TRUE 或 FALSE，实际为 '{secure}')")
            continue

        # 验证 expiration 是数字
        try:
            int(expiration)
        except ValueError:
            errors.append(f"第 {line_num} 行: expiration 字段无效 (应为数字，实际为 '{expiration}')")
            continue

        # 这一行有效
        valid_lines.append(line)

    cleaned_content = '\n'.join(valid_lines)
    is_valid = len(errors) == 0

    return is_valid, errors, cleaned_content


def clean_cookie_content(content: str) -> str:
    """
    清理 Cookie 内容，移除无效行

    Args:
        content: 原始 Cookie 内容

    Returns:
        清理后的 Cookie 内容
    """
    _, _, cleaned = validate_netscape_cookie_format(content)
    return cleaned


def _dpapi_encrypt(data: bytes) -> bytes:
    import win32crypt

    return win32crypt.CryptProtectData(data, None, _DPAPI_ENTROPY, None, None, 0)


def _dpapi_decrypt(blob: bytes) -> bytes:
    import win32crypt

    return win32crypt.CryptUnprotectData(blob, _DPAPI_ENTROPY, None, None, 0)[1]


def encrypt_cookie_text(plaintext: str) -> str:
    if not _is_windows():
        return plaintext

    try:
        blob = _dpapi_encrypt(plaintext.encode("utf-8"))
        return _COOKIE_PREFIX + base64.b64encode(blob).decode("ascii")
    except Exception as e:
        logger.warning(f"Failed to encrypt cookie with DPAPI: {e}")
        return plaintext


def decrypt_cookie_text(stored: str) -> str:
    if not is_encrypted_cookie_file_text(stored):
        return stored

    if not _is_windows():
        raise RuntimeError("Encrypted cookie file can only be decrypted on Windows.")

    b64 = stored[len(_COOKIE_PREFIX):].strip()
    try:
        blob = base64.b64decode(b64)
        data = _dpapi_decrypt(blob)
        return data.decode("utf-8")
    except Exception as e:
        raise RuntimeError("Cookie 文件无法解密，可能来自其他 Windows 用户/电脑，请重新获取。") from e


def read_cookie_file(path: Path, *, migrate: bool = True) -> str:
    if not path.exists():
        return ""

    raw = path.read_text(encoding="utf-8", errors="ignore")

    if is_encrypted_cookie_file_text(raw):
        return decrypt_cookie_text(raw)

    plaintext = raw

    if migrate and _is_windows() and plaintext.strip():
        try:
            write_cookie_file(path, plaintext)
        except Exception as e:
            logger.warning(f"Failed to migrate cookie file to encrypted: {e}")

    return plaintext


def write_cookie_file(path: Path, plaintext: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = encrypt_cookie_text(plaintext)

    tmp_path = path.with_suffix(path.suffix + ".tmp")
    try:
        tmp_path.write_text(payload, encoding="utf-8")
        tmp_path.replace(path)
    except Exception:
        path.write_text(payload, encoding="utf-8")
        try:
            tmp_path.unlink(missing_ok=True)
        except Exception:
            pass


@contextmanager
def cookiefile_for_ytdlp(path: Optional[Path], *, migrate: bool = True) -> Iterator[Optional[Path]]:
    if not path:
        yield None
        return

    p = Path(path)
    if not p.exists():
        yield None
        return

    raw = p.read_text(encoding="utf-8", errors="ignore")

    if is_encrypted_cookie_file_text(raw):
        plaintext = decrypt_cookie_text(raw)
        needs_temp = True
    elif migrate and _is_windows() and raw.strip():
        plaintext = raw
        write_cookie_file(p, raw)
        needs_temp = True
    else:
        plaintext = raw
        needs_temp = False

    if not needs_temp:
        yield p
        return

    fd, tmp_name = tempfile.mkstemp(prefix="vidflow_cookies_", suffix=".txt")
    os.close(fd)
    tmp_path = Path(tmp_name)
    try:
        tmp_path.write_text(plaintext, encoding="utf-8")
        yield tmp_path
    finally:
        try:
            tmp_path.unlink(missing_ok=True)
        except Exception:
            pass

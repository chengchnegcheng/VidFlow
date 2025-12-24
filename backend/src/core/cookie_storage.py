import base64
import logging
import os
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional

logger = logging.getLogger(__name__)

_COOKIE_PREFIX = "VIDFLOW_COOKIE_DPAPI_V1:"
_DPAPI_ENTROPY = b"VidFlowCookieV1"


def _is_windows() -> bool:
    return sys.platform == "win32"


def is_encrypted_cookie_file_text(text: str) -> bool:
    return isinstance(text, str) and text.startswith(_COOKIE_PREFIX)


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

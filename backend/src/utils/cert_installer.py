#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Helpers for managing the mitmproxy CA certificate on Windows."""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class CertInstaller:
    """Manage the mitmproxy CA certificate files and Windows trust state."""

    SUPPORTED_EXPORT_FORMATS = {"cer", "p12"}

    def __init__(self) -> None:
        self.cert_dir = Path.home() / ".mitmproxy"
        self.cert_file = self.cert_dir / "mitmproxy-ca-cert.cer"
        self.cert_p12_file = self.cert_dir / "mitmproxy-ca-cert.p12"
        self.ca_p12_file = self.cert_dir / "mitmproxy-ca.p12"

    def _run_certutil(self, *args: str, timeout: int = 30) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["certutil", *args],
            capture_output=True,
            timeout=timeout,
        )

    def _run_powershell(self, script: str, timeout: int = 30) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["powershell", "-NoProfile", "-Command", script],
            capture_output=True,
            timeout=timeout,
        )

    @staticmethod
    def _decode_output(payload: Optional[bytes]) -> str:
        if not payload:
            return ""
        return payload.decode("utf-8", errors="replace").strip()

    @classmethod
    def normalize_export_format(cls, cert_format: Optional[str]) -> str:
        normalized = str(cert_format or "cer").strip().lower()
        if normalized not in cls.SUPPORTED_EXPORT_FORMATS:
            raise ValueError(f"Unsupported certificate format: {cert_format}")
        return normalized

    def get_export_source(self, cert_format: Optional[str] = None) -> Tuple[str, Path]:
        normalized = self.normalize_export_format(cert_format)
        if normalized == "p12":
            if self.ca_p12_file.exists():
                return normalized, self.ca_p12_file
            if self.cert_p12_file.exists():
                return normalized, self.cert_p12_file
            return normalized, self.ca_p12_file
        return normalized, self.cert_file

    def get_wechat_p12_sources(self) -> List[Path]:
        """Return P12 files that should be imported for WeChat compatibility."""
        sources: List[Path] = []
        for candidate in (self.ca_p12_file, self.cert_p12_file):
            if candidate.exists() and candidate not in sources:
                sources.append(candidate)
        return sources

    def has_wechat_cert_subject(self) -> bool:
        """Return True when a mitmproxy certificate exists in CurrentUser\\My."""
        try:
            result = self._run_powershell(
                (
                    "$cert = Get-ChildItem Cert:\\CurrentUser\\My | "
                    "Where-Object { $_.Subject -like '*mitmproxy*' } | "
                    "Select-Object -First 1; "
                    "if ($cert) { exit 0 } else { exit 1 }"
                ),
                timeout=10,
            )
            return result.returncode == 0
        except Exception as exc:
            logger.error("Failed to verify WeChat certificate subject presence: %s", exc)
            return False

    def is_cert_installed(self) -> bool:
        """Return True when the mitmproxy root CA is trusted by Windows."""
        try:
            result = self._run_certutil("-verifystore", "Root", "mitmproxy", timeout=10)
            return result.returncode == 0
        except Exception as exc:
            logger.error("Failed to verify mitmproxy root certificate: %s", exc)
            return False

    def is_wechat_p12_installed(self) -> bool:
        """Return True when the user cert store has a mitmproxy cert with a private key."""
        try:
            result = self._run_powershell(
                (
                    "$cert = Get-ChildItem Cert:\\CurrentUser\\My | "
                    "Where-Object { $_.Subject -like '*mitmproxy*' -and $_.HasPrivateKey } | "
                    "Select-Object -First 1; "
                    "if ($cert) { exit 0 } else { exit 1 }"
                ),
                timeout=10,
            )
            return result.returncode == 0
        except Exception as exc:
            logger.error("Failed to verify WeChat-compatible P12 import: %s", exc)
            return False

    def ensure_cert_exists(self) -> bool:
        """Ensure mitmproxy has generated its CA certificate files.

        失败原因存入 self.last_error 供调用方读取。
        """
        self.last_error: Optional[str] = None

        if self.cert_file.exists():
            return True

        logger.info("mitmproxy certificate file missing, attempting to generate it")

        try:
            self.cert_dir.mkdir(parents=True, exist_ok=True)

            from mitmproxy import options
            from mitmproxy.tools.dump import DumpMaster

            opts = options.Options()
            if not hasattr(opts, "confdir"):
                opts.add_option("confdir", str, str(self.cert_dir), "")
            else:
                opts.confdir = str(self.cert_dir)

            master = DumpMaster(opts)
            master.shutdown()
        except Exception as exc:
            self.last_error = f"证书生成失败: {exc}"
            logger.error("Failed to generate mitmproxy certificate files: %s", exc)
            return False

        if self.cert_file.exists():
            logger.info("mitmproxy certificate file generated: %s", self.cert_file)
            return True

        self.last_error = f"证书生成完成但文件未产生: {self.cert_file}"
        logger.error("mitmproxy certificate generation finished without producing %s", self.cert_file)
        return False

    def _install_cert_elevated(self) -> bool:
        """通过 UAC 提权安装根证书（会弹出管理员授权窗口）。"""
        cert_path = str(self.cert_file).replace("'", "''")
        script = (
            "$proc = Start-Process certutil "
            f"-ArgumentList '-addstore','Root','{cert_path}' "
            "-Verb RunAs -Wait -PassThru -WindowStyle Hidden; "
            "exit $proc.ExitCode"
        )
        result = self._run_powershell(script, timeout=60)
        return result.returncode == 0

    def install_cert(self) -> bool:
        """Import the mitmproxy root CA into Windows Root."""
        try:
            if not self.ensure_cert_exists():
                logger.error("mitmproxy certificate file does not exist")
                return False

            if self.is_cert_installed():
                logger.info("mitmproxy root certificate already installed")
                return True

            logger.info("Installing mitmproxy root certificate into Windows Root: %s", self.cert_file)

            # 先尝试直接安装（已有管理员权限时）
            result = self._run_certutil("-addstore", "Root", str(self.cert_file), timeout=30)
            if result.returncode == 0:
                logger.info("mitmproxy root certificate installed successfully")
                return True

            # 直接安装失败，通过 UAC 提权重试
            stderr_hint = self._decode_output(result.stderr)
            logger.info("直接安装失败 (returncode=%d, stderr=%s)，尝试通过 UAC 提权安装根证书",
                        result.returncode, stderr_hint)
            if self._install_cert_elevated():
                # UAC 提权执行完毕，二次验证是否真正安装成功
                if self.is_cert_installed():
                    logger.info("mitmproxy root certificate installed successfully via UAC elevation")
                    return True
                logger.error("UAC 提权执行成功但证书验证未通过")

            self.last_error = f"安装失败，请在 UAC 弹窗中点击「是」授权。(certutil: {stderr_hint})"
            logger.error("Failed to install mitmproxy root certificate (UAC elevation also failed)")
            return False
        except subprocess.TimeoutExpired:
            logger.error("Installing mitmproxy root certificate timed out")
            return False
        except Exception as exc:
            logger.error("Failed to install mitmproxy root certificate: %s", exc)
            return False

    def install_wechat_p12(self) -> bool:
        """Import the WeChat-compatible P12 into the current user's personal store."""
        try:
            if not self.ensure_cert_exists():
                logger.error("mitmproxy certificate file does not exist")
                return False

            sources = self.get_wechat_p12_sources()
            if not sources:
                logger.error("No WeChat-compatible P12 files exist in %s", self.cert_dir)
                return False

            if self.is_wechat_p12_installed():
                logger.info("WeChat-compatible P12 already imported into the current user store")
                return True

            logger.info(
                "Importing WeChat-compatible P12 files into CurrentUser\\My: %s",
                ", ".join(str(source) for source in sources),
            )
            source_literals = ", ".join(
                "'{}'".format(str(source).replace("'", "''"))
                for source in sources
            )
            script = (
                "$flags = "
                "[System.Security.Cryptography.X509Certificates.X509KeyStorageFlags]::UserKeySet "
                "-bor [System.Security.Cryptography.X509Certificates.X509KeyStorageFlags]::PersistKeySet "
                "-bor [System.Security.Cryptography.X509Certificates.X509KeyStorageFlags]::Exportable; "
                "$store = New-Object System.Security.Cryptography.X509Certificates.X509Store('My', 'CurrentUser'); "
                "$store.Open([System.Security.Cryptography.X509Certificates.OpenFlags]::ReadWrite); "
                f"$paths = @({source_literals}); "
                "foreach ($path in $paths) { "
                "if (-not (Test-Path $path)) { continue }; "
                "$collection = New-Object System.Security.Cryptography.X509Certificates.X509Certificate2Collection; "
                "$collection.Import($path, '', $flags); "
                "foreach ($cert in $collection) { "
                "if ($cert.Subject -like '*mitmproxy*') { $store.Add($cert) } "
                "} "
                "} "
                "$store.Close()"
            )
            result = self._run_powershell(script, timeout=30)
            if result.returncode == 0 and self.is_wechat_p12_installed():
                logger.info("WeChat-compatible P12 imported successfully")
                return True

            logger.error(
                "Failed to import WeChat-compatible P12: stdout=%s stderr=%s",
                self._decode_output(result.stdout),
                self._decode_output(result.stderr),
            )
            return False
        except subprocess.TimeoutExpired:
            logger.error("Importing WeChat-compatible P12 timed out")
            return False
        except Exception as exc:
            logger.error("Failed to import WeChat-compatible P12: %s", exc)
            return False

    def _uninstall_cert_elevated(self) -> bool:
        """通过 UAC 提权卸载根证书。"""
        script = (
            "$proc = Start-Process certutil "
            "-ArgumentList '-delstore','Root','mitmproxy' "
            "-Verb RunAs -Wait -PassThru -WindowStyle Hidden; "
            "exit $proc.ExitCode"
        )
        result = self._run_powershell(script, timeout=60)
        return result.returncode == 0

    def uninstall_cert(self) -> bool:
        """Remove the mitmproxy root CA from Windows Root."""
        try:
            if not self.is_cert_installed():
                logger.info("mitmproxy root certificate is not installed")
                return True

            result = self._run_certutil("-delstore", "Root", "mitmproxy", timeout=30)
            if result.returncode == 0:
                logger.info("mitmproxy root certificate removed successfully")
                return True

            # 直接卸载失败，通过 UAC 提权重试
            logger.info("直接卸载失败，尝试通过 UAC 提权卸载根证书")
            if self._uninstall_cert_elevated():
                logger.info("mitmproxy root certificate removed successfully via UAC elevation")
                return True

            logger.error("Failed to remove mitmproxy root certificate (UAC elevation also failed)")
            return False
        except subprocess.TimeoutExpired:
            logger.error("Removing mitmproxy root certificate timed out")
            return False
        except Exception as exc:
            logger.error("Failed to remove mitmproxy root certificate: %s", exc)
            return False

    def get_cert_info(self) -> Dict[str, object]:
        _, p12_source = self.get_export_source("p12")
        wechat_p12_sources = self.get_wechat_p12_sources()
        has_private_key = self.is_wechat_p12_installed()
        return {
            "cert_dir": str(self.cert_dir),
            "cert_file": str(self.cert_file),
            "cert_p12_file": str(p12_source),
            "cert_exists": self.cert_file.exists(),
            "cert_p12_exists": bool(wechat_p12_sources),
            "cert_installed": self.is_cert_installed(),
            "wechat_p12_installed": has_private_key,
            "wechat_p12_subject_present": self.has_wechat_cert_subject(),
            "wechat_p12_sources": [str(source) for source in wechat_p12_sources],
            "preferred_download_format": "p12",
        }


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    installer = CertInstaller()
    info = installer.get_cert_info()
    print("=" * 60)
    print("mitmproxy certificate helper")
    print("=" * 60)
    print(f"Certificate directory: {info['cert_dir']}")
    print(f"Root certificate file: {info['cert_file']}")
    print(f"WeChat P12 file: {info['cert_p12_file']}")
    print(f"Root certificate exists: {info['cert_exists']}")
    print(f"WeChat P12 exists: {info['cert_p12_exists']}")
    print(f"Root certificate installed: {info['cert_installed']}")
    print(f"WeChat P12 imported: {info['wechat_p12_installed']}")


if __name__ == "__main__":
    main()

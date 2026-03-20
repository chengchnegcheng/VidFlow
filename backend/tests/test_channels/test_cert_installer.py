from pathlib import Path
from types import SimpleNamespace

from src.utils.cert_installer import CertInstaller


def test_get_export_source_prefers_private_key_p12(tmp_path):
    installer = CertInstaller()
    installer.cert_dir = tmp_path
    installer.cert_file = tmp_path / "mitmproxy-ca-cert.cer"
    installer.cert_p12_file = tmp_path / "mitmproxy-ca-cert.p12"
    installer.ca_p12_file = tmp_path / "mitmproxy-ca.p12"
    installer.cert_p12_file.write_bytes(b"public-only")
    installer.ca_p12_file.write_bytes(b"with-key")

    cert_format, source = installer.get_export_source("p12")

    assert cert_format == "p12"
    assert source == installer.ca_p12_file


def test_install_wechat_p12_uses_powershell_store_import(monkeypatch, tmp_path):
    installer = CertInstaller()
    installer.cert_dir = tmp_path
    installer.cert_file = tmp_path / "mitmproxy-ca-cert.cer"
    installer.cert_p12_file = tmp_path / "mitmproxy-ca-cert.p12"
    installer.ca_p12_file = tmp_path / "mitmproxy-ca.p12"
    installer.cert_file.write_bytes(b"cer")
    installer.cert_p12_file.write_bytes(b"p12")
    installer.ca_p12_file.write_bytes(b"p12-with-key")

    checks = {"count": 0}
    scripts: list[str] = []

    monkeypatch.setattr(installer, "ensure_cert_exists", lambda: True)

    def fake_is_wechat_p12_installed() -> bool:
        checks["count"] += 1
        return checks["count"] > 1

    def fake_run_powershell(script: str, timeout: int = 30):
        scripts.append(script)
        return SimpleNamespace(returncode=0, stdout=b"", stderr=b"")

    monkeypatch.setattr(installer, "is_wechat_p12_installed", fake_is_wechat_p12_installed)
    monkeypatch.setattr(installer, "_run_powershell", fake_run_powershell)

    assert installer.install_wechat_p12() is True
    assert len(scripts) == 1
    assert "X509Certificate2Collection" in scripts[0]
    assert "X509Store('My', 'CurrentUser')" in scripts[0]
    assert str(installer.ca_p12_file) in scripts[0]
    assert str(installer.cert_p12_file) in scripts[0]


def test_is_wechat_p12_installed_requires_private_key(monkeypatch):
    installer = CertInstaller()
    scripts: list[str] = []

    def fake_run_powershell(script: str, timeout: int = 30):
        scripts.append(script)
        return SimpleNamespace(returncode=1, stdout=b"", stderr=b"")

    monkeypatch.setattr(installer, "_run_powershell", fake_run_powershell)

    assert installer.is_wechat_p12_installed() is False
    assert scripts
    assert "HasPrivateKey" in scripts[0]

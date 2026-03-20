"""
证书管理器

管理 HTTPS 代理所需的 CA 证书，包括生成、验证和导出功能。
"""

import os
import shutil
import hashlib
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import Optional

from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend

from .models import CertInfo, CertGenerateResult, ErrorCode, get_error_message


class CertificateManager:
    """CA 证书管理器

    负责生成、验证和导出 HTTPS 代理所需的 CA 证书。
    """

    # 证书有效期（天）
    CERT_VALIDITY_DAYS = 365 * 3  # 3 年

    # 证书文件名
    CA_CERT_FILENAME = "mitmproxy-ca-cert.pem"
    CA_KEY_FILENAME = "mitmproxy-ca.pem"

    def __init__(self, cert_dir: Path):
        """初始化证书管理器

        Args:
            cert_dir: 证书存储目录
        """
        self.cert_dir = Path(cert_dir)
        self.ca_cert_path = self.cert_dir / self.CA_CERT_FILENAME
        self.ca_key_path = self.cert_dir / self.CA_KEY_FILENAME

    def _ensure_cert_dir(self) -> None:
        """确保证书目录存在"""
        self.cert_dir.mkdir(parents=True, exist_ok=True)

    def is_cert_valid(self) -> bool:
        """检查证书是否存在且有效

        Returns:
            如果证书存在且未过期返回 True
        """
        if not self.ca_cert_path.exists():
            return False

        try:
            cert_info = self.get_cert_info()
            if not cert_info.exists or not cert_info.valid:
                return False

            # 检查是否过期
            if cert_info.expires_at and cert_info.expires_at < datetime.now():
                return False

            return True
        except Exception:
            return False

    def generate_ca_cert(self) -> CertGenerateResult:
        """生成新的 CA 证书

        Returns:
            CertGenerateResult: 包含生成结果
        """
        try:
            self._ensure_cert_dir()

            # 生成 RSA 私钥
            private_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=2048,
                backend=default_backend()
            )

            # 构建证书主题
            subject = issuer = x509.Name([
                x509.NameAttribute(NameOID.COUNTRY_NAME, "CN"),
                x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "Beijing"),
                x509.NameAttribute(NameOID.LOCALITY_NAME, "Beijing"),
                x509.NameAttribute(NameOID.ORGANIZATION_NAME, "VidFlow"),
                x509.NameAttribute(NameOID.COMMON_NAME, "VidFlow Proxy CA"),
            ])

            # 构建证书
            now = datetime.now(timezone.utc)
            cert = (
                x509.CertificateBuilder()
                .subject_name(subject)
                .issuer_name(issuer)
                .public_key(private_key.public_key())
                .serial_number(x509.random_serial_number())
                .not_valid_before(now)
                .not_valid_after(now + timedelta(days=self.CERT_VALIDITY_DAYS))
                .add_extension(
                    x509.BasicConstraints(ca=True, path_length=None),
                    critical=True,
                )
                .add_extension(
                    x509.KeyUsage(
                        digital_signature=True,
                        content_commitment=False,
                        key_encipherment=False,
                        data_encipherment=False,
                        key_agreement=False,
                        key_cert_sign=True,
                        crl_sign=True,
                        encipher_only=False,
                        decipher_only=False,
                    ),
                    critical=True,
                )
                .sign(private_key, hashes.SHA256(), default_backend())
            )

            # 保存私钥
            with open(self.ca_key_path, "wb") as f:
                f.write(private_key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.TraditionalOpenSSL,
                    encryption_algorithm=serialization.NoEncryption()
                ))

            # 保存证书
            with open(self.ca_cert_path, "wb") as f:
                f.write(cert.public_bytes(serialization.Encoding.PEM))

            return CertGenerateResult(
                success=True,
                cert_path=str(self.ca_cert_path)
            )

        except PermissionError:
            return CertGenerateResult(
                success=False,
                error_message=get_error_message(ErrorCode.PERMISSION_DENIED)
            )
        except Exception as e:
            return CertGenerateResult(
                success=False,
                error_message=f"证书生成失败: {str(e)}"
            )

    def export_cert(self, export_path: Path) -> bool:
        """导出 CA 证书供用户安装

        Args:
            export_path: 导出目标路径

        Returns:
            导出成功返回 True
        """
        if not self.ca_cert_path.exists():
            return False

        try:
            export_path = Path(export_path)
            export_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(self.ca_cert_path, export_path)
            return True
        except Exception:
            return False

    def get_cert_info(self) -> CertInfo:
        """获取证书信息

        Returns:
            CertInfo: 证书信息对象
        """
        if not self.ca_cert_path.exists():
            return CertInfo(
                exists=False,
                valid=False
            )

        try:
            with open(self.ca_cert_path, "rb") as f:
                cert_data = f.read()

            cert = x509.load_pem_x509_certificate(cert_data, default_backend())

            # 计算指纹
            fingerprint = hashlib.sha256(
                cert.public_bytes(serialization.Encoding.DER)
            ).hexdigest().upper()

            # 格式化指纹（每两个字符加冒号）
            fingerprint_formatted = ":".join(
                fingerprint[i:i+2] for i in range(0, len(fingerprint), 2)
            )

            # 检查有效期
            now = datetime.now(timezone.utc)
            not_valid_before = cert.not_valid_before_utc
            not_valid_after = cert.not_valid_after_utc
            is_valid = not_valid_before <= now <= not_valid_after

            return CertInfo(
                exists=True,
                valid=is_valid,
                expires_at=not_valid_after.replace(tzinfo=None),
                fingerprint=fingerprint_formatted,
                path=str(self.ca_cert_path)
            )

        except Exception:
            return CertInfo(
                exists=True,
                valid=False,
                path=str(self.ca_cert_path)
            )

    def get_cert_content(self) -> Optional[bytes]:
        """获取证书内容

        Returns:
            证书内容字节，如果不存在返回 None
        """
        if not self.ca_cert_path.exists():
            return None

        try:
            with open(self.ca_cert_path, "rb") as f:
                return f.read()
        except Exception:
            return None

    def delete_cert(self) -> bool:
        """删除证书文件

        Returns:
            删除成功返回 True
        """
        try:
            if self.ca_cert_path.exists():
                self.ca_cert_path.unlink()
            if self.ca_key_path.exists():
                self.ca_key_path.unlink()
            return True
        except Exception:
            return False

    def get_install_instructions(self) -> str:
        """获取证书安装说明

        Returns:
            安装说明文本
        """
        return """
## CA 证书安装说明

### Windows
1. 双击导出的证书文件
2. 点击"安装证书"
3. 选择"本地计算机"，点击"下一步"
4. 选择"将所有证书放入下列存储"
5. 点击"浏览"，选择"受信任的根证书颁发机构"
6. 点击"确定"，然后"下一步"，"完成"

### macOS
1. 双击导出的证书文件，会打开"钥匙串访问"
2. 在"钥匙串"中选择"系统"
3. 找到 "VidFlow Proxy CA" 证书
4. 双击证书，展开"信任"
5. 将"使用此证书时"改为"始终信任"
6. 关闭窗口，输入密码确认

### iOS
1. 将证书文件发送到 iOS 设备（通过 AirDrop 或邮件）
2. 打开证书文件，点击"安装"
3. 进入 设置 > 通用 > 关于本机 > 证书信任设置
4. 启用 "VidFlow Proxy CA" 的完全信任

### Android
1. 将证书文件复制到设备
2. 进入 设置 > 安全 > 加密与凭据 > 安装证书
3. 选择 "CA 证书"
4. 选择证书文件并安装
"""

"""
差异包数据库模型
"""
from sqlalchemy import Column, Integer, String, BigInteger, Boolean, DateTime, JSON, Numeric, Index
from sqlalchemy.sql import func
from .database import Base


class DeltaPackage(Base):
    """差异包表"""
    __tablename__ = "delta_packages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_version = Column(String(20), nullable=False)
    target_version = Column(String(20), nullable=False)
    platform = Column(String(20), nullable=False)
    arch = Column(String(20), nullable=False)
    delta_size = Column(BigInteger, nullable=False)
    full_size = Column(BigInteger, nullable=False)
    savings_percent = Column(Numeric(5, 2))
    delta_hash = Column(String(128), nullable=False)
    delta_url = Column(String, nullable=False)
    manifest = Column(JSON, nullable=False)
    is_recommended = Column(Boolean, default=True)
    download_count = Column(Integer, default=0)
    success_count = Column(Integer, default=0)
    failure_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=func.now())
    last_used_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index('idx_delta_source', 'source_version'),
        Index('idx_delta_target', 'target_version'),
        Index('idx_delta_platform', 'platform', 'arch'),
    )

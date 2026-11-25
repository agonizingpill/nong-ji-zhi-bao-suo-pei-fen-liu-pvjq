from sqlalchemy import String, Integer, ForeignKey, Text, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column
from .database import Base
class ModelVersion(Base):
    __tablename__='model_versions'
    __table_args__=(CheckConstraint("state IN ('candidate','reviewed','active')"),)
    id:Mapped[int]=mapped_column(primary_key=True)
    name:Mapped[str|None]=mapped_column(String(20),unique=True,nullable=True)
    state:Mapped[str]=mapped_column(String(20),default='candidate')
    algorithm:Mapped[str]=mapped_column(String(200))
    seed:Mapped[int]=mapped_column(Integer,default=42)
    metrics:Mapped[str]=mapped_column(Text)
    samples:Mapped[str]=mapped_column(Text)
    encoder:Mapped[str]=mapped_column(Text)
    artifact:Mapped[str]=mapped_column(String(200),default='')
    trained_by:Mapped[str]=mapped_column(String(120))
    trained_at:Mapped[str]=mapped_column(String(40))
    reviewed_by:Mapped[str|None]=mapped_column(String(120),nullable=True)
    reviewed_at:Mapped[str|None]=mapped_column(String(40),nullable=True)
    review_note:Mapped[str]=mapped_column(Text,default='')
    activated_by:Mapped[str|None]=mapped_column(String(120),nullable=True)
    activated_at:Mapped[str|None]=mapped_column(String(40),nullable=True)
class ClaimTriage(Base):
    __tablename__='claim_triage'
    id:Mapped[int]=mapped_column(primary_key=True)
    claim_id:Mapped[int]=mapped_column(ForeignKey('claims.id'),unique=True)
    version_id:Mapped[int]=mapped_column(ForeignKey('model_versions.id'))
    version_name:Mapped[str]=mapped_column(String(20))
    bound_at:Mapped[str]=mapped_column(String(40))

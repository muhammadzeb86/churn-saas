from datetime import datetime
import uuid
import enum
from sqlalchemy import String, Integer, DateTime, Index, ForeignKey, Text, Column, Boolean, Enum, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.api.database import Base

class PredictionStatus(enum.Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING" 
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    clerk_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(100), nullable=False)
    first_name: Mapped[str] = mapped_column(String(100), nullable=True)
    last_name: Mapped[str] = mapped_column(String(100), nullable=True)
    avatar_url: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        nullable=False, 
        default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )

    # Relationships
    uploads: Mapped[list["Upload"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    predictions: Mapped[list["Prediction"]] = relationship("Prediction", back_populates="user", cascade="all, delete-orphan")

    # Create indexes on email and clerk_id
    __table_args__ = (
        Index("ix_users_email", "email"),
        Index("ix_users_clerk_id", "clerk_id"),
    )

    def __repr__(self) -> str:
        return f"User(id={self.id}, email={self.email}, clerk_id={self.clerk_id}, full_name={self.full_name})"

class Upload(Base):
    __tablename__ = "uploads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    s3_object_key: Mapped[str] = mapped_column(Text, nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    upload_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow
    )
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="uploaded"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )

    # Relationships
    user: Mapped["User"] = relationship(back_populates="uploads")
    predictions: Mapped[list["Prediction"]] = relationship("Prediction", back_populates="upload", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"Upload(id={self.id}, filename={self.filename}, user_id={self.user_id}, status={self.status})"

class Lead(Base):
    __tablename__ = "leads"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow
    )
    source: Mapped[str] = mapped_column(String(100), nullable=True)
    converted_to_user: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    __table_args__ = (
        Index("ix_leads_email", "email"),
    )

    def __repr__(self) -> str:
        return f"Lead(id={self.id}, email={self.email}, source={self.source}, converted={self.converted_to_user})"

class Prediction(Base):
    __tablename__ = "predictions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        primary_key=True, 
        default=uuid.uuid4
    )
    upload_id: Mapped[int] = mapped_column(
        ForeignKey("uploads.id", ondelete="CASCADE"), 
        nullable=False
    )
    user_id: Mapped[str] = mapped_column(
        String(255), 
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, 
        index=True
    )
    status: Mapped[PredictionStatus] = mapped_column(
        Enum(PredictionStatus),
        nullable=False,
        default=PredictionStatus.QUEUED
    )
    s3_output_key: Mapped[str] = mapped_column(
        String(1024), 
        nullable=True
    )
    rows_processed: Mapped[int] = mapped_column(
        Integer, 
        nullable=False, 
        default=0
    )
    metrics_json: Mapped[dict] = mapped_column(
        JSON, 
        nullable=True
    )
    error_message: Mapped[str] = mapped_column(
        Text, 
        nullable=True
    )
    # SQS metadata (Task 1.1)
    sqs_message_id: Mapped[str] = mapped_column(
        String(255),
        nullable=True,
        comment="SQS MessageId for tracking"
    )
    sqs_queued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When message was published to SQS"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )

    # Relationships
    upload: Mapped["Upload"] = relationship("Upload", back_populates="predictions")
    user: Mapped["User"] = relationship("User", back_populates="predictions")

    def __repr__(self) -> str:
        return f"Prediction(id={self.id}, upload_id={self.upload_id}, status={self.status.value})"

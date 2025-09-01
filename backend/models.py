from datetime import datetime
from sqlalchemy import String, Integer, DateTime, Index, ForeignKey, Text, Column, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from api.database import Base

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

    # Relationship to uploads
    uploads: Mapped[list["Upload"]] = relationship(back_populates="user", cascade="all, delete-orphan")

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
    # S3 object key for the uploaded file
    s3_object_key: Mapped[str] = mapped_column(Text, nullable=False)
    # File size in bytes
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
        default="uploaded"  # Changed from "pending" to "uploaded" since we're uploading directly
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

    # Relationship to user
    user: Mapped["User"] = relationship(back_populates="uploads")

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

    # Create an index on email
    __table_args__ = (
        Index("ix_leads_email", "email"),
    )

    def __repr__(self) -> str:
        return f"Lead(id={self.id}, email={self.email}, source={self.source}, converted={self.converted_to_user})" 
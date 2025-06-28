from datetime import datetime
from sqlalchemy import String, Integer, DateTime, Index, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.api.database import Base

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        nullable=False, 
        default=datetime.utcnow
    )

    # Relationship to uploads
    uploads: Mapped[list["Upload"]] = relationship(back_populates="user", cascade="all, delete-orphan")

    # Create an index on email
    __table_args__ = (
        Index("ix_users_email", "email"),
    )

    def __repr__(self) -> str:
        return f"User(id={self.id}, email={self.email}, full_name={self.full_name})"

class Upload(Base):
    __tablename__ = "uploads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    # S3 object key for the uploaded file
    s3_object_key: Mapped[str] = mapped_column(Text, nullable=False)
    # File size in bytes
    file_size: Mapped[int] = mapped_column(Integer, nullable=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
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

    # Relationship to user
    user: Mapped["User"] = relationship(back_populates="uploads")

    def __repr__(self) -> str:
        return f"Upload(id={self.id}, filename={self.filename}, user_id={self.user_id}, status={self.status})" 
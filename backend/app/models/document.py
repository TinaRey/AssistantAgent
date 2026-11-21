import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, ForeignKey, Integer, LargeBinary, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

EMBEDDING_DIM = 1536  # text-embedding-3-small


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    filename: Mapped[str] = mapped_column(String(255))
    kind: Mapped[str] = mapped_column(String(20))  # pdf | docx | txt | md | note
    size_bytes: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64), unique=True)  # blocks duplicate uploads
    # Render's disk is ephemeral, so originals live in the database (small volume).
    data: Mapped[bytes] = mapped_column(LargeBinary, deferred=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    chunks: Mapped[list["Chunk"]] = relationship(
        back_populates="document", cascade="all, delete-orphan", passive_deletes=True
    )


class Chunk(Base):
    __tablename__ = "chunks"

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    position: Mapped[int] = mapped_column(Integer)
    page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    text: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIM))

    document: Mapped[Document] = relationship(back_populates="chunks")


class Presentation(Base):
    """A generated presentation: editable structured content; PDF/PPTX are built on demand from it."""

    __tablename__ = "presentations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(300))
    company: Mapped[str | None] = mapped_column(String(200), nullable=True)
    visual_style: Mapped[str | None] = mapped_column(String(200), nullable=True)
    content: Mapped[dict] = mapped_column(JSONB)
    theme: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True
    )  # {primary, tint}; null = brand colors
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    images: Mapped[list["PresentationImage"]] = relationship(
        cascade="all, delete-orphan", passive_deletes=True
    )


class PresentationImage(Base):
    __tablename__ = "presentation_images"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    presentation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("presentations.id", ondelete="CASCADE"), index=True
    )
    data: Mapped[bytes] = mapped_column(LargeBinary, deferred=True)
    mime: Mapped[str] = mapped_column(String(50), default="image/png")
    prompt: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

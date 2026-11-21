"""Storage of generated presentations: Postgres in normal use, in memory when no database is set."""

import asyncio
import uuid
from dataclasses import dataclass
from typing import Protocol

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session, sessionmaker

from app.document_generation.theme import Theme
from app.models import Presentation, PresentationImage
from app.schemas.tools import PresentationContent


@dataclass
class StoredPresentation:
    id: str
    content: PresentationContent
    company: str | None
    visual_style: str | None
    theme: Theme | None = None


class PresentationStore(Protocol):
    async def create(
        self,
        content: PresentationContent,
        company: str | None,
        visual_style: str | None,
        theme: Theme | None = None,
    ) -> str: ...
    async def set_theme(self, pid: str, theme: Theme | None) -> StoredPresentation | None: ...
    async def get(self, pid: str) -> StoredPresentation | None: ...
    async def update_content(
        self, pid: str, content: PresentationContent
    ) -> StoredPresentation | None: ...
    async def add_image(self, pid: str, data: bytes, prompt: str) -> str: ...
    async def get_image(self, pid: str, image_id: str) -> bytes | None: ...
    async def images_for(self, pid: str) -> dict[str, bytes]: ...
    async def image_count(self, pid: str) -> int: ...
    async def delete_image(self, pid: str, image_id: str) -> None: ...


def _theme_of(row: Presentation) -> Theme | None:
    return Theme.model_validate(row.theme) if row.theme else None


def _valid_uuid(value: str) -> uuid.UUID | None:
    try:
        return uuid.UUID(value)
    except ValueError:
        return None


def referenced_ids(content: PresentationContent) -> set[str]:
    return {s.image_id for s in content.slides if s.image_id}


def drop_foreign_images(content: PresentationContent, valid_ids: set[str]) -> PresentationContent:
    """A slide may only reference images that belong to this presentation."""
    slides = [
        s.model_copy(update={"image_id": s.image_id if s.image_id in valid_ids else None})
        for s in content.slides
    ]
    return content.model_copy(update={"slides": slides})


class MemoryPresentationStore:
    def __init__(self) -> None:
        self._items: dict[str, StoredPresentation] = {}
        self._images: dict[str, dict[str, bytes]] = {}

    async def create(self, content, company, visual_style, theme=None):  # type: ignore[no-untyped-def]
        pid = uuid.uuid4().hex
        self._items[pid] = StoredPresentation(pid, content, company, visual_style, theme)
        self._images[pid] = {}
        return pid

    async def set_theme(self, pid, theme):  # type: ignore[no-untyped-def]
        item = self._items.get(pid)
        if item is not None:
            item.theme = theme
        return item

    async def get(self, pid: str) -> StoredPresentation | None:
        return self._items.get(pid)

    async def update_content(self, pid, content):  # type: ignore[no-untyped-def]
        item = self._items.get(pid)
        if item is None:
            return None
        item.content = drop_foreign_images(content, set(self._images[pid]))
        keep = referenced_ids(item.content)  # images no slide uses any more are deleted
        self._images[pid] = {k: v for k, v in self._images[pid].items() if k in keep}
        return item

    async def add_image(self, pid: str, data: bytes, prompt: str) -> str:
        image_id = uuid.uuid4().hex
        self._images[pid][image_id] = data
        return image_id

    async def get_image(self, pid: str, image_id: str) -> bytes | None:
        return self._images.get(pid, {}).get(image_id)

    async def images_for(self, pid: str) -> dict[str, bytes]:
        return dict(self._images.get(pid, {}))

    async def image_count(self, pid: str) -> int:
        return len(self._images.get(pid, {}))

    async def delete_image(self, pid: str, image_id: str) -> None:
        self._images.get(pid, {}).pop(image_id, None)


class PgPresentationStore:
    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self._sessions = sessions

    async def create(self, content, company, visual_style, theme=None):  # type: ignore[no-untyped-def]
        def work() -> str:
            row = Presentation(
                title=content.title[:300],
                company=company,
                visual_style=visual_style,
                content=content.model_dump(mode="json"),
                theme=theme.model_dump() if theme else None,
            )
            with self._sessions() as s:
                s.add(row)
                s.commit()
                return row.id.hex

        return await asyncio.to_thread(work)

    async def get(self, pid: str) -> StoredPresentation | None:
        def work() -> StoredPresentation | None:
            key = _valid_uuid(pid)
            if key is None:
                return None
            with self._sessions() as s:
                row = s.get(Presentation, key)
                if row is None:
                    return None
                return StoredPresentation(
                    row.id.hex,
                    PresentationContent.model_validate(row.content),
                    row.company,
                    row.visual_style,
                    _theme_of(row),
                )

        return await asyncio.to_thread(work)

    async def update_content(self, pid, content):  # type: ignore[no-untyped-def]
        def work() -> StoredPresentation | None:
            key = _valid_uuid(pid)
            if key is None:
                return None
            with self._sessions() as s:
                row = s.get(Presentation, key)
                if row is None:
                    return None
                ids = {
                    i.hex
                    for i in s.scalars(
                        select(PresentationImage.id).where(PresentationImage.presentation_id == key)
                    )
                }
                clean = drop_foreign_images(content, ids)
                keep = [uuid.UUID(i) for i in referenced_ids(clean)]
                s.execute(  # images no slide uses any more are deleted
                    delete(PresentationImage).where(
                        PresentationImage.presentation_id == key,
                        PresentationImage.id.not_in(keep) if keep else True,
                    )
                )
                row.content = clean.model_dump(mode="json")
                row.title = clean.title[:300]
                s.commit()
                return StoredPresentation(
                    row.id.hex, clean, row.company, row.visual_style, _theme_of(row)
                )

        return await asyncio.to_thread(work)

    async def set_theme(self, pid: str, theme: Theme | None) -> StoredPresentation | None:
        def work() -> StoredPresentation | None:
            key = _valid_uuid(pid)
            if key is None:
                return None
            with self._sessions() as s:
                row = s.get(Presentation, key)
                if row is None:
                    return None
                row.theme = theme.model_dump() if theme else None
                s.commit()
                return StoredPresentation(
                    row.id.hex,
                    PresentationContent.model_validate(row.content),
                    row.company,
                    row.visual_style,
                    _theme_of(row),
                )

        return await asyncio.to_thread(work)

    async def add_image(self, pid: str, data: bytes, prompt: str) -> str:
        def work() -> str:
            img = PresentationImage(presentation_id=uuid.UUID(pid), data=data, prompt=prompt)
            with self._sessions() as s:
                s.add(img)
                s.commit()
                return img.id.hex

        return await asyncio.to_thread(work)

    async def get_image(self, pid: str, image_id: str) -> bytes | None:
        def work() -> bytes | None:
            p, i = _valid_uuid(pid), _valid_uuid(image_id)
            if p is None or i is None:
                return None
            with self._sessions() as s:
                img = s.scalar(
                    select(PresentationImage).where(
                        PresentationImage.id == i, PresentationImage.presentation_id == p
                    )
                )
                return img.data if img else None

        return await asyncio.to_thread(work)

    async def images_for(self, pid: str) -> dict[str, bytes]:
        def work() -> dict[str, bytes]:
            key = _valid_uuid(pid)
            if key is None:
                return {}
            with self._sessions() as s:
                rows = s.scalars(
                    select(PresentationImage).where(PresentationImage.presentation_id == key)
                )
                return {r.id.hex: r.data for r in rows}

        return await asyncio.to_thread(work)

    async def image_count(self, pid: str) -> int:
        def work() -> int:
            key = _valid_uuid(pid)
            if key is None:
                return 0
            with self._sessions() as s:
                return (
                    s.scalar(
                        select(func.count())
                        .select_from(PresentationImage)
                        .where(PresentationImage.presentation_id == key)
                    )
                    or 0
                )

        return await asyncio.to_thread(work)

    async def delete_image(self, pid: str, image_id: str) -> None:
        def work() -> None:
            p, i = _valid_uuid(pid), _valid_uuid(image_id)
            if p is None or i is None:
                return
            with self._sessions() as s:
                s.execute(
                    delete(PresentationImage).where(
                        PresentationImage.id == i, PresentationImage.presentation_id == p
                    )
                )
                s.commit()

        await asyncio.to_thread(work)

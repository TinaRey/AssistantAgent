import re

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from app.api.deps import Runtime, get_runtime

router = APIRouter()
_ID = re.compile(r"^[0-9a-f]{32}$")  # strict: blocks path traversal


@router.get("/files/{file_id}")
def download(file_id: str, rt: Runtime = Depends(get_runtime)) -> FileResponse:
    path = rt.storage_dir / f"{file_id}.pptx"
    if not _ID.match(file_id) or not path.is_file():
        raise HTTPException(404, "File not found")
    return FileResponse(path, filename="pantalelle-presentation.pptx")

"""File attachments on transactions (invoices/receipts), stored in the DB."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, File, HTTPException, Response, UploadFile

from backend.api.deps import CurrentUser, SessionDep
from backend.persistence import repository
from backend.schemas import AttachmentOut

router = APIRouter(tags=["attachments"])

_MAX_BYTES = 10 * 1024 * 1024  # 10 MB (matches nginx client_max_body_size)
_ALLOWED = {"application/pdf", "image/png", "image/jpeg", "image/jpg", "image/webp"}


@router.post(
    "/transactions/{txn_id}/attachments", response_model=AttachmentOut, status_code=201
)
def upload_attachment(
    txn_id: uuid.UUID, session: SessionDep, user: CurrentUser, file: UploadFile = File(...)
) -> AttachmentOut:
    if repository.get_transaction(session, txn_id, user.id) is None:
        raise HTTPException(status_code=404, detail="transaction not found")
    content_type = (file.content_type or "application/octet-stream").lower()
    if content_type not in _ALLOWED:
        raise HTTPException(status_code=415, detail="only PDF or image files are allowed")
    data = file.file.read()
    if len(data) == 0:
        raise HTTPException(status_code=400, detail="empty file")
    if len(data) > _MAX_BYTES:
        raise HTTPException(status_code=413, detail="file too large (max 10 MB)")

    attachment = repository.create_attachment(
        session,
        user_id=user.id,
        transaction_id=txn_id,
        filename=(file.filename or "file")[:255],
        content_type=content_type,
        size=len(data),
        data=data,
    )
    session.commit()
    return AttachmentOut.model_validate(attachment)


@router.get("/transactions/{txn_id}/attachments", response_model=list[AttachmentOut])
def list_attachments(
    txn_id: uuid.UUID, session: SessionDep, user: CurrentUser
) -> list[AttachmentOut]:
    if repository.get_transaction(session, txn_id, user.id) is None:
        raise HTTPException(status_code=404, detail="transaction not found")
    return [
        AttachmentOut.model_validate(a)
        for a in repository.list_attachments(session, txn_id, user.id)
    ]


@router.get("/attachments/{attachment_id}")
def download_attachment(
    attachment_id: uuid.UUID, session: SessionDep, user: CurrentUser
) -> Response:
    attachment = repository.get_attachment(session, attachment_id, user.id)
    if attachment is None:
        raise HTTPException(status_code=404, detail="attachment not found")
    return Response(
        content=attachment.data,
        media_type=attachment.content_type,
        headers={"Content-Disposition": f'inline; filename="{attachment.filename}"'},
    )


@router.delete("/attachments/{attachment_id}", status_code=204)
def delete_attachment(
    attachment_id: uuid.UUID, session: SessionDep, user: CurrentUser
) -> Response:
    if not repository.delete_attachment(session, attachment_id, user.id):
        raise HTTPException(status_code=404, detail="attachment not found")
    session.commit()
    return Response(status_code=204)

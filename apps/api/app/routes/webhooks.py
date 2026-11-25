"""Stage 12C.2: Isolated FastAPI Webhook Endpoint for MSG91 Delivery Receipts (DLR).

Security guarantees:
- Fails closed (`503`) if `MSG91_WEBHOOK_SECRET` is unconfigured.
- Authenticates every request using constant-time comparison (`hmac.compare_digest`)
  on the custom `X-Webhook-Secret` header (`401` missing / `403` invalid).
- Enforces `Content-Type: application/json` (`415`) and max payload size (`413`).
- Rejects malformed payloads (`400`).
- Never exposes tenant IDs, reminder IDs, or internal state in HTTP responses.
- Never triggers outbound SMS or retries.
- Never logs secrets, phone numbers, message bodies, or raw callback payloads.
"""

from __future__ import annotations

import json
import logging
from typing import Dict
from fastapi import APIRouter, Depends, HTTPException, Request, status
from app.core.config import Settings, get_settings
from app.modules.notifications.dlr import (
    DeliveryReceiptService,
    parse_msg91_webhook_payload,
    verify_msg91_webhook_secret,
)
from app.modules.notifications.repository import (
    ReminderRepositoryProtocol,
    SupabaseRestReminderRepository,
    get_in_memory_reminder_repository,
)

logger = logging.getLogger("svario.routes.webhooks")

router = APIRouter(
    prefix="/api/v1/webhooks/sms",
    tags=["SMS Webhooks (Stage 12C.2)"],
)


def get_dlr_service(
    settings: Settings = Depends(get_settings),
) -> DeliveryReceiptService:
    """Resolve backend-only `DeliveryReceiptService` (service_role in live mode)."""
    if settings.is_live_supabase_configured:
        if not settings.supabase_service_role_key:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Delivery receipt persistence is not configured.",
            )
        repo: ReminderRepositoryProtocol = SupabaseRestReminderRepository(settings=settings)
    else:
        repo = get_in_memory_reminder_repository()
    return DeliveryReceiptService(repo=repo)


@router.post(
    "/msg91",
    status_code=status.HTTP_200_OK,
    summary="Receive authenticated MSG91 SMS delivery receipts (DLR)",
)
async def receive_msg91_dlr_webhook(
    request: Request,
    settings: Settings = Depends(get_settings),
    dlr_service: DeliveryReceiptService = Depends(get_dlr_service),
) -> Dict[str, str]:
    # 1. Fail-closed authentication check
    ok, reason = verify_msg91_webhook_secret(
        request.headers.get("x-webhook-secret"),
        settings.msg91_webhook_secret,
    )
    if not ok:
        if reason == "webhook_secret_not_configured":
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Webhook authentication is not configured.",
            )
        if reason == "missing_webhook_secret":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing webhook authentication header.",
            )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid webhook authentication header.",
        )

    # 2. Content-Type check
    content_type = (request.headers.get("content-type") or "").split(";")[0].strip().lower()
    if content_type != "application/json":
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Content-Type must be application/json.",
        )

    # 3. Payload size check
    raw_body = await request.body()
    if len(raw_body) > settings.msg91_webhook_max_body_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Webhook payload exceeds maximum allowed size.",
        )

    # 4. Strict JSON & MSG91 DLR schema validation
    try:
        parsed_json = json.loads(raw_body.decode("utf-8"))
        receipts = parse_msg91_webhook_payload(
            parsed_json,
            configured_timezone=settings.msg91_webhook_timezone,
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Malformed delivery receipt payload.",
        )

    # 5. Process each normalized receipt (never leaks tenant/reminder IDs in response)
    for receipt in receipts:
        await dlr_service.process_receipt(receipt)

    return {"status": "received"}

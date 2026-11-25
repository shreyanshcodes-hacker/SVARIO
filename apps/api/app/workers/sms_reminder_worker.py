"""Stage 12B Standalone SMS Reminder Background Worker (Render-compatible).

Run with:
    python -m app.workers.sms_reminder_worker [--once]

Guarantees:
- Polls every `SMS_WORKER_POLL_INTERVAL_SECONDS` (default 30s).
- Uses `NoopSmsProvider` exclusively in Stage 12B (zero real SMS transmissions).
- Respects `SMS_REMINDERS_ENABLED` (defaults to False).
- Survives transient database outages without crashing permanently.
- Handles SIGTERM / SIGINT gracefully for zero-downtime Render restarts.
- Never logs phone numbers, secrets, or sensitive customer data.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import signal
import socket
import time
from typing import Optional
from uuid import uuid4
from app.core.config import Settings, get_settings
from app.modules.notifications.providers import NoopSmsProvider
from app.modules.notifications.service import (
    AppointmentReminderService,
    ReconciliationSummary,
    WorkerDispatchSummary,
    build_appointment_reminder_service,
)

logger = logging.getLogger("svario.workers.sms_reminder")


def _default_worker_id() -> str:
    host = socket.gethostname()[:40]
    return f"sms-worker-{host}-{os.getpid()}-{uuid4().hex[:6]}"


class SmsReminderWorker:
    """Polling worker wrapping `AppointmentReminderService.process_due_reminders_once`."""

    def __init__(
        self,
        *,
        settings: Optional[Settings] = None,
        service: Optional[AppointmentReminderService] = None,
        worker_id: Optional[str] = None,
        reconcile_interval_seconds: int = 300,
    ) -> None:
        self._settings = settings or get_settings()
        self._worker_id = worker_id or _default_worker_id()
        self._reconcile_interval_seconds = max(60, int(reconcile_interval_seconds))
        self._stop_event = asyncio.Event()

        if service is not None:
            self._service: Optional[AppointmentReminderService] = service
        elif not self._settings.sms_reminders_enabled:
            # Never instantiate live providers when reminders are disabled
            self._service = build_appointment_reminder_service(
                settings=self._settings,
                provider=NoopSmsProvider(),
            )
        else:
            self._service = build_appointment_reminder_service(
                settings=self._settings,
            )

    @property
    def worker_id(self) -> str:
        return self._worker_id

    def request_stop(self) -> None:
        self._stop_event.set()

    async def run_once(self) -> WorkerDispatchSummary:
        """Execute a single fault-tolerant claim-and-dispatch tick."""
        if not self._settings.sms_reminders_enabled:
            logger.debug("sms_worker_disabled worker_id=%s", self._worker_id)
            return WorkerDispatchSummary(skipped_disabled=True)

        if self._service is None:
            logger.warning(
                "sms_worker_unconfigured worker_id=%s reason=missing_service_role_key",
                self._worker_id,
            )
            return WorkerDispatchSummary()

        try:
            summary = await self._service.process_due_reminders_once(
                worker_id=self._worker_id
            )
            if summary.claimed > 0:
                logger.info(
                    "sms_worker_tick worker_id=%s claimed=%s sent_simulated=%s "
                    "cancelled_stale=%s retried=%s failed=%s",
                    self._worker_id,
                    summary.claimed,
                    summary.sent_simulated,
                    summary.cancelled_stale,
                    summary.retried,
                    summary.failed,
                )
            return summary
        except Exception as exc:
            # Survive transient database or network outages without crashing permanently
            logger.error(
                "sms_worker_tick_error worker_id=%s error_type=%s",
                self._worker_id,
                type(exc).__name__,
            )
            return WorkerDispatchSummary()

    async def run_reconciliation_once(self) -> ReconciliationSummary:
        """Execute one fault-tolerant recipient-level reconciliation pass."""
        if not self._settings.sms_reminders_enabled:
            return ReconciliationSummary(skipped_disabled=True)

        if self._service is None:
            return ReconciliationSummary()

        try:
            return await self._service.reconcile_missing_reminders_once()
        except Exception as exc:
            logger.error(
                "sms_worker_reconcile_error worker_id=%s error_type=%s",
                self._worker_id,
                type(exc).__name__,
            )
            return ReconciliationSummary()

    async def run_forever(self) -> None:
        """Poll on the configured interval and reconcile missing reminders every ~5 minutes."""
        interval = self._settings.sms_worker_poll_interval_seconds
        logger.info(
            "sms_worker_started worker_id=%s poll_interval_s=%s reconcile_interval_s=%s enabled=%s provider=noop",
            self._worker_id,
            interval,
            self._reconcile_interval_seconds,
            self._settings.sms_reminders_enabled,
        )
        last_reconcile = 0.0
        while not self._stop_event.is_set():
            now_mono = time.monotonic()
            if (now_mono - last_reconcile) >= self._reconcile_interval_seconds:
                await self.run_reconciliation_once()
                last_reconcile = now_mono
            await self.run_once()
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=interval)
            except asyncio.TimeoutError:
                continue
        logger.info("sms_worker_stopped worker_id=%s", self._worker_id)


async def _main_async(run_once_only: bool) -> None:
    worker = SmsReminderWorker()
    loop = asyncio.get_running_loop()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, worker.request_stop)
        except NotImplementedError:
            # Windows event loops do not support add_signal_handler
            pass

    if run_once_only:
        await worker.run_once()
    else:
        await worker.run_forever()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    parser = argparse.ArgumentParser(description="Svario Stage 12B SMS Reminder Worker (Noop)")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Execute a single polling tick and exit.",
    )
    args = parser.parse_args()
    asyncio.run(_main_async(run_once_only=args.once))


if __name__ == "__main__":
    main()

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
import os
import socket
import tempfile
from typing import Protocol

from .config import TargetConfig


class OutcomeKind(str, Enum):
    ACCEPTED = 'ACCEPTED'
    DEFINITE_RETRYABLE_FAILURE = 'DEFINITE_RETRYABLE_FAILURE'
    ACTION_REQUIRED = 'ACTION_REQUIRED'
    UNCERTAIN = 'UNCERTAIN'


@dataclass(frozen=True, slots=True)
class SubmissionOutcome:
    kind: OutcomeKind
    category: str | None = None
    local_job_reference: str | None = None


class PrinterAdapter(Protocol):
    version: str

    def submit(self, document: str, target: TargetConfig, operation_id: str) -> SubmissionOutcome: ...
    def reconcile(self, target: TargetConfig, operation_id: str) -> SubmissionOutcome: ...
    def queues(self) -> tuple[str, ...]: ...


class FakeAdapter:
    version = 'fake-v1'

    def __init__(self, mode: OutcomeKind = OutcomeKind.ACCEPTED) -> None:
        self.mode = mode
        self.submissions: list[tuple[str, str, str]] = []

    def submit(self, document: str, target: TargetConfig, operation_id: str) -> SubmissionOutcome:
        self.submissions.append((document, target.queue, operation_id))
        if self.mode is OutcomeKind.ACCEPTED:
            return SubmissionOutcome(self.mode, local_job_reference=f'fake:{target.queue}:{len(self.submissions)}')
        return SubmissionOutcome(self.mode, category=f'FAKE_{self.mode.value}')

    def reconcile(self, target: TargetConfig, operation_id: str) -> SubmissionOutcome:
        matches = [item for item in self.submissions if item[2] == operation_id]
        if matches:
            return SubmissionOutcome(OutcomeKind.ACCEPTED, local_job_reference=f'fake:{target.queue}:1')
        return SubmissionOutcome(OutcomeKind.DEFINITE_RETRYABLE_FAILURE, category='NO_MATCHING_FAKE_JOB')

    def queues(self) -> tuple[str, ...]:
        return ()


class CupsAdapter:
    version = 'pycups-v1'

    def __init__(self, connection: object | None = None) -> None:
        if connection is None:
            try:
                import cups  # type: ignore[import-not-found]
            except ImportError as exc:
                raise RuntimeError('PyCUPS is required for the CUPS adapter') from exc
            connection = cups.Connection()
        self.connection = connection

    @staticmethod
    def _title(operation_id: str) -> str:
        safe = ''.join(char if char.isalnum() or char in '-_.' else '-' for char in operation_id)
        return f'pryecip-{safe}'[:120]

    def queues(self) -> tuple[str, ...]:
        return tuple(sorted(self.connection.getPrinters().keys()))  # type: ignore[attr-defined]

    def submit(self, document: str, target: TargetConfig, operation_id: str) -> SubmissionOutcome:
        try:
            printers = self.connection.getPrinters()  # type: ignore[attr-defined]
        except Exception:
            return SubmissionOutcome(OutcomeKind.DEFINITE_RETRYABLE_FAILURE, category='CUPS_UNAVAILABLE_BEFORE_SUBMISSION')
        if target.queue not in printers:
            return SubmissionOutcome(OutcomeKind.ACTION_REQUIRED, category='CUPS_QUEUE_NOT_CONFIGURED')
        transmitted = False
        path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode='w', encoding='utf-8', suffix='.txt', prefix='pryecip-ticket-', delete=False,
            ) as stream:
                stream.write(document)
                stream.flush()
                path = Path(stream.name)
            transmitted = True
            job_id = int(self.connection.printFile(  # type: ignore[attr-defined]
                target.queue, str(path), self._title(operation_id), {'document-format': 'text/plain'},
            ))
            if job_id <= 0:
                return SubmissionOutcome(OutcomeKind.UNCERTAIN, category='CUPS_INVALID_JOB_REFERENCE')
            return SubmissionOutcome(
                OutcomeKind.ACCEPTED,
                local_job_reference=f'cups:{target.queue}:{job_id}',
            )
        except Exception:
            return SubmissionOutcome(
                OutcomeKind.UNCERTAIN if transmitted else OutcomeKind.DEFINITE_RETRYABLE_FAILURE,
                category='CUPS_SUBMISSION_OUTCOME_UNCERTAIN' if transmitted else 'CUPS_REFUSED_BEFORE_SUBMISSION',
            )
        finally:
            if path is not None:
                path.unlink(missing_ok=True)

    def reconcile(self, target: TargetConfig, operation_id: str) -> SubmissionOutcome:
        title = self._title(operation_id)
        try:
            jobs = self.connection.getJobs(which_jobs='all', my_jobs=False)  # type: ignore[attr-defined]
        except Exception:
            return SubmissionOutcome(OutcomeKind.UNCERTAIN, category='CUPS_RECONCILIATION_UNAVAILABLE')
        matches = [
            int(job_id) for job_id, attributes in jobs.items()
            if attributes.get('job-name') == title
            and attributes.get('job-printer-uri', '').rstrip('/').endswith('/' + target.queue)
        ]
        if len(matches) == 1:
            return SubmissionOutcome(
                OutcomeKind.ACCEPTED,
                local_job_reference=f'cups:{target.queue}:{matches[0]}',
            )
        # CUPS history may be pruned, so absence is not definitive after a crash.
        return SubmissionOutcome(OutcomeKind.UNCERTAIN, category='CUPS_JOB_EVIDENCE_INCONCLUSIVE')


def encode_escpos(document: str, *, encoding: str) -> bytes:
    """Encode the bounded ticket profile used by the platform's thermal documents."""
    body = document.replace('\r\n', '\n').replace('\r', '\n').encode(
        encoding, errors='replace'
    )
    return b'\x1b@' + body + b'\n\n\n' + b'\x1dV\x00'


class EscPosNetworkAdapter:
    version = 'escpos-network-v1'

    def queues(self) -> tuple[str, ...]:
        return ()

    def submit(self, document: str, target: TargetConfig, operation_id: str) -> SubmissionOutcome:
        if target.host is None:
            return SubmissionOutcome(OutcomeKind.ACTION_REQUIRED, category='ESCPOS_HOST_NOT_CONFIGURED')
        transmitted = False
        try:
            with socket.create_connection((target.host, target.port), timeout=5.0) as connection:
                data = encode_escpos(document, encoding=target.encoding)
                transmitted = True
                connection.sendall(data)
            return SubmissionOutcome(
                OutcomeKind.ACCEPTED,
                local_job_reference=f'escpos-network:{operation_id}',
            )
        except (TimeoutError, OSError):
            return SubmissionOutcome(
                OutcomeKind.UNCERTAIN if transmitted else OutcomeKind.DEFINITE_RETRYABLE_FAILURE,
                category=(
                    'ESCPOS_NETWORK_OUTCOME_UNCERTAIN'
                    if transmitted else 'ESCPOS_NETWORK_UNAVAILABLE_BEFORE_SUBMISSION'
                ),
            )

    def reconcile(self, target: TargetConfig, operation_id: str) -> SubmissionOutcome:
        return SubmissionOutcome(
            OutcomeKind.UNCERTAIN, category='ESCPOS_NETWORK_HAS_NO_DURABLE_JOB_EVIDENCE'
        )


class EscPosUsbAdapter:
    version = 'escpos-usb-device-v1'

    def queues(self) -> tuple[str, ...]:
        return ()

    def submit(self, document: str, target: TargetConfig, operation_id: str) -> SubmissionOutcome:
        if target.device_path is None:
            return SubmissionOutcome(OutcomeKind.ACTION_REQUIRED, category='ESCPOS_DEVICE_NOT_CONFIGURED')
        descriptor: int | None = None
        transmitted = False
        try:
            descriptor = os.open(target.device_path, os.O_WRONLY)
            data = encode_escpos(document, encoding=target.encoding)
            transmitted = True
            written = os.write(descriptor, data)
            if written != len(data):
                return SubmissionOutcome(OutcomeKind.UNCERTAIN, category='ESCPOS_USB_PARTIAL_WRITE')
            return SubmissionOutcome(
                OutcomeKind.ACCEPTED,
                local_job_reference=f'escpos-usb:{operation_id}',
            )
        except OSError:
            return SubmissionOutcome(
                OutcomeKind.UNCERTAIN if transmitted else OutcomeKind.DEFINITE_RETRYABLE_FAILURE,
                category=(
                    'ESCPOS_USB_OUTCOME_UNCERTAIN'
                    if transmitted else 'ESCPOS_USB_UNAVAILABLE_BEFORE_SUBMISSION'
                ),
            )
        finally:
            if descriptor is not None:
                os.close(descriptor)

    def reconcile(self, target: TargetConfig, operation_id: str) -> SubmissionOutcome:
        return SubmissionOutcome(
            OutcomeKind.UNCERTAIN, category='ESCPOS_USB_HAS_NO_DURABLE_JOB_EVIDENCE'
        )

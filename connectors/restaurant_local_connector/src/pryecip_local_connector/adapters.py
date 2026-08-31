from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
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

from __future__ import annotations

import logging

from prometheus_client import Counter


OPERATIONAL_EVENTS_TOTAL = Counter(
    'ecip_operational_events_total',
    'Bounded operational event signals emitted by ECIP.',
    ('domain', 'event', 'outcome'),
)

_EVENT_DOMAINS = {
    'order_preparation_routing_failed': 'preparation',
    'fiscal_artifact_persistence_failed': 'fiscal',
    'fiscal_result_persisted': 'fiscal',
    'preparation_dispatch_result_recorded': 'printing',
}


class OperationalEventMetricHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        event = str(getattr(record, 'event', ''))
        domain = _EVENT_DOMAINS.get(event)
        if domain is None:
            return
        outcome = str(getattr(record, 'outcome', 'unknown')).lower()
        OPERATIONAL_EVENTS_TOTAL.labels(domain, event, outcome).inc()

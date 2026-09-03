from prometheus_client import Counter, Histogram


PAYMENT_EXECUTION_TOTAL = Counter(
    'restaurant_payment_execution_total',
    'Provider-neutral restaurant payment execution outcomes',
    ('method', 'outcome', 'adapter_kind', 'topology'),
)
PAYMENT_RECOVERY_TOTAL = Counter(
    'restaurant_payment_recovery_total',
    'Provider-neutral restaurant payment recovery outcomes',
    ('method', 'outcome', 'adapter_kind', 'topology'),
)
PAYMENT_EXECUTION_DURATION_SECONDS = Histogram(
    'restaurant_payment_execution_duration_seconds',
    'Provider-neutral restaurant payment executor duration',
    ('method', 'outcome', 'adapter_kind', 'topology'),
)

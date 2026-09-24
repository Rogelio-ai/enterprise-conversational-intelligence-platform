from __future__ import annotations

import re


_USERNAME_PATTERN = re.compile(r'^[a-z0-9](?:[a-z0-9._-]{1,62}[a-z0-9])?$')


def normalize_username(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError('A valid username is required')
    normalized = value.strip().casefold()
    if not _USERNAME_PATTERN.fullmatch(normalized):
        raise ValueError('A valid username is required')
    return normalized

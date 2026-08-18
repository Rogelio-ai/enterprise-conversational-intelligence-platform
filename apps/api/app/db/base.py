from sqlalchemy import Table
from sqlalchemy.orm import DeclarativeBase


MYSQL_TABLE_OPTIONS = {
    'mysql_engine': 'InnoDB',
    'mysql_charset': 'utf8mb4',
    'mysql_collate': 'utf8mb4_unicode_ci',
}


class Base(DeclarativeBase):
    """Metadata root with the portable ECIP table contract."""

    @classmethod
    def __table_cls__(cls, *args, **kwargs):
        for option, value in MYSQL_TABLE_OPTIONS.items():
            kwargs.setdefault(option, value)
        return Table(*args, **kwargs)

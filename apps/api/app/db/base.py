from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Metadata root for future bounded migrations."""

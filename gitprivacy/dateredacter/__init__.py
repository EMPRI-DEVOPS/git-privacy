import abc
from datetime import datetime


class DateRedacter(abc.ABC):
    """Abstract timestamp redater."""

    @abc.abstractmethod
    def redact(self, timestamp: datetime) -> datetime:
        """Redact timestamp."""


from .reduce import ResolutionDateRedacter

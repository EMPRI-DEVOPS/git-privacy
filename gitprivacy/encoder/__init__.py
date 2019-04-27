import abc
from datetime import datetime
import git
from typing import Tuple

from ..dateredacter import DateRedacter


class Encoder(abc.ABC):
    """Abstract commit encoder."""
    def __init__(self,
                 redacter: DateRedacter) -> None:
        self.redacter = redacter


    @abc.abstractmethod
    def encode(self, commit: git.Commit) -> Tuple[datetime, datetime, str]:
        pass


    @abc.abstractmethod
    def decode(self, commit: git.Commit) -> Tuple[datetime, datetime]:
        pass


class BasicEncoder(Encoder):
    """Basic commit encoder that only inserts redacted dates."""
    def encode(self, commit: git.Commit) -> Tuple[datetime, datetime, str]:
        msg_extra = self.get_message_extra(commit)
        return (self.redacter.redact(commit.authored_datetime),
                self.redacter.redact(commit.committed_datetime),
                msg_extra)


    def decode(self, commit: git.Commit) -> Tuple[datetime, datetime]:
        return (commit.authored_datetime,
                commit.committed_datetime)


    def get_message_extra(self, commit: git.Commit) -> str:
        return ""


from .msgembed import MessageEmbeddingEncoder

import abc
import git  # type: ignore

from datetime import datetime
from typing import Callable, Optional, Tuple, Union

from ..dateredacter import DateRedacter


class Encoder(abc.ABC):
    """Abstract commit encoder."""
    @abc.abstractmethod
    def encode(self, commit: git.Commit) -> Tuple[datetime, datetime, str]:
        """Encode commit."""


class Decoder(abc.ABC):
    """Abstract commit decoder."""
    @abc.abstractmethod
    def decode(self, commit: git.Commit) -> Tuple[Optional[datetime],
                                                  Optional[datetime]]:
        """Decode commit."""


class BasicEncoder(Encoder):
    """Basic commit encoder that only inserts redacted dates."""
    def __init__(self, redacter: DateRedacter) -> None:
        self.redacter = redacter

    def encode(self, commit: git.Commit) -> Tuple[datetime, datetime, str]:
        new_ad = self.redacter.redact(commit.authored_datetime)
        new_cd = self.redacter.redact(commit.committed_datetime)
        if (new_ad == commit.authored_datetime and
                new_cd == commit.committed_datetime):
            # already redacted – nothing to do
            return (new_ad, new_cd, "")
        msg_extra = self.get_message_extra(commit)
        new_msg = ""  # signifies no change to old message
        if isinstance(msg_extra, str):
            if msg_extra:
                new_msg = "\n".join((commit.message, msg_extra))
        elif callable(msg_extra):
            rpl_msg = msg_extra(commit.message)  # pylint: disable=not-callable
            if rpl_msg != commit.message:
                new_msg = rpl_msg
        else:
            raise TypeError("Unexpected msg_extra type")
        return (new_ad, new_cd, new_msg)

    def get_message_extra(self, commit: git.Commit) -> Union[
            str,
            Callable[[str], str]
    ]:
        # pylint: disable=no-self-use,unused-argument
        return ""


class BasicDecoder(Decoder):
    """Basic commit decoder returning dates as in the commit metadata."""
    def decode(self, commit: git.Commit) -> Tuple[Optional[datetime],
                                                  Optional[datetime]]:
        return (commit.authored_datetime,
                commit.committed_datetime)


from .msgembed import MessageEmbeddingEncoder, MessageEmbeddingDecoder

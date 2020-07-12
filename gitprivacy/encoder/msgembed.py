import git  # type: ignore
import re

from datetime import datetime
from typing import Callable, Optional, Tuple, Union

from . import BasicEncoder, Decoder
from .. import utils
from ..crypto import DecryptionProvider, EncryptionProvider
from ..dateredacter import DateRedacter


MSG_TAG = "GitPrivacy: "
TAG_REGEX = fr'^{MSG_TAG}(\S+)(?: (\S+))?'


class MessageEmbeddingEncoder(BasicEncoder):
    def __init__(self,
                 redacter: DateRedacter,
                 crypto: EncryptionProvider) -> None:
        super().__init__(redacter)
        self.crypto = crypto


    def get_message_extra(self, commit: git.Commit) -> Union[
            str,
            Callable[[str], str],
    ]:
        """Get date ciphertext addition to commit message."""
        if not _contains_tag(commit):  # keep prior tag if already present
            # create new tag
            a_date = _encrypt_for_msg(self.crypto, commit.authored_datetime)
            c_date = _encrypt_for_msg(self.crypto, commit.committed_datetime)
            return f"{MSG_TAG}{a_date} {c_date}"
        # update the committer date ciphertext
        ciphers = _extract_enc_dates(commit.message)
        assert ciphers is not None  # we know it contains the tag
        ad_cipher, _cd_cipher = ciphers
        c_date = _encrypt_for_msg(self.crypto, commit.committed_datetime)
        new_extra = f"{MSG_TAG}{ad_cipher} {c_date}"
        return lambda msg: re.sub(TAG_REGEX, new_extra, msg,
                                  flags=re.MULTILINE)


class MessageEmbeddingDecoder(Decoder):
    def __init__(self, crypto: DecryptionProvider) -> None:
        self.crypto = crypto

    def decode(self, commit: git.Commit) -> Tuple[Optional[datetime],
                                                  Optional[datetime]]:
        return _decrypt_from_msg(self.crypto, commit.message)


def _contains_tag(commit: git.Commit):
    return any([line.startswith(MSG_TAG)
                for line in commit.message.splitlines()])


def _extract_enc_dates(msg: str) -> Optional[Tuple[str, Optional[str]]]:
    """Extract encrypted dates from the commit message

    Returns either a combined cipher for author and committer date or one
    separate cipher each if present.
    """
    for line in msg.splitlines():
        # 2nd cipher is optional for backward compatability with
        # combined author and committer date ciphers
        match = re.search(TAG_REGEX, line)
        if match:
            ad_cipher, cd_cipher = match.groups()
            return (ad_cipher, cd_cipher)
    return None


def _encrypt_for_msg(crypto: EncryptionProvider, date: datetime) -> str:
    """Returns ciphertext date."""
    return crypto.encrypt(utils.dt2gitdate(date))


def _decrypt_from_msg(crypto: DecryptionProvider, message: str) -> Tuple[
        Optional[datetime],
        Optional[datetime],
]:
    enc_dates = _extract_enc_dates(message)
    if crypto is None or enc_dates is None:
        return (None, None)
    enc_adate, enc_cdate = enc_dates
    raw_adate = crypto.decrypt(enc_adate)
    if enc_cdate:
        # use separate committer date
        raw_cdate = crypto.decrypt(enc_cdate)
        if raw_adate and ";" in raw_adate:
            # discard combined committer date for newer separate
            raw_adate, _ = raw_adate.split(";")
    elif raw_adate and not enc_cdate:
        # combined cipher compatability mode
        assert ";" in raw_adate
        raw_adate, raw_cdate = raw_adate.split(";")
    else:
        # no readable ciphertext to use
        assert not raw_adate and not enc_cdate
        raw_cdate = None

    a_date = None
    c_date = None
    if raw_adate:
        assert ";" not in raw_adate
        a_date = utils.gitdate2dt(raw_adate)
    if raw_cdate:
        c_date = utils.gitdate2dt(raw_cdate)
    return a_date, c_date

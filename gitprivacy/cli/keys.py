import click
import git  # type: ignore
import os

from typing import Iterator, Tuple

import gitprivacy as gp

from .. import crypto as gpcrypto
from .. import gitprivacy as gpm


KEY_DIR = os.path.join(gp.GIT_SUBDIR, "keys")
KEY_CURRENT = os.path.join(KEY_DIR, "current")
KEY_ARCHIVE = os.path.join(KEY_DIR, "archive")


@click.command("keys")
@click.option('--init', 'mode', flag_value='init', default=True,
              help="Generate an initial key. (Default mode)")
@click.option('--new', 'mode', flag_value='new',
              help="Generate new key and archive the existing.")
@click.option('--disable', 'mode', flag_value='disable',
              help="Disable and archive the active key.")
@click.option('--migrate-pwd', 'mode', flag_value='migrate',
              help="Migrate from password-based encryption.")
@click.option('--archive/--no-archive', default=True,
              show_default=True,
              help="Archive the replaced key instead of deleting it.")
@click.pass_context
def manage_keys(ctx: click.Context, mode: str, archive: bool) -> None:
    """Create and manage encryption keys."""
    # pylint: disable=too-many-branches
    repo: git.Repo = ctx.obj.repo
    gpm._create_git_subdir(repo)
    base = repo.git_dir
    _keydir, archivedir = _setup_keydir(base)
    cur_path = os.path.join(base, KEY_CURRENT)

    # check if previous password settings exist
    crypto = ctx.obj.get_crypto()
    if mode != "migrate":
        _check_abort_passwordbased(ctx, crypto)

    has_cur = os.path.exists(cur_path)
    if mode == "init":
        if has_cur:
            click.echo(
                "A key has already been set. "
                "To generate a new key use the '--new' option.",
                err=True,
            )
            ctx.exit(1)
        key = gpcrypto.SecretBox.generate_key()
        with open(cur_path, "x") as f:
            f.write(key)
        click.echo("Key initialisation successful")
    elif mode == "new":
        if not has_cur:
            click.echo(
                "No active key found. "
                "To generate an initial key use the '--init' option.",
                err=True,
            )
            ctx.exit(1)
        if archive:
            _archive_key(cur_path, archivedir)
        key = gpcrypto.SecretBox.generate_key()
        with open(cur_path, "w") as f:
            f.write(key)
        click.echo("Key replacement successful")
    elif mode == "migrate":
        # store old password-derived key
        if not isinstance(crypto, gpcrypto.PasswordSecretBox):
            click.echo("No password setting found to migrate.", err=True)
            ctx.exit(1)
        if has_cur:
            click.confirm(
                "A key has already been set. "
                "Replace it with password key?",
                abort=True,
            )
            if archive:
                _archive_key(cur_path, archivedir)
        pwdkey = crypto._export_key()
        with open(cur_path, "w") as f:
            f.write(pwdkey)
        # comment out password and salt
        ctx.obj.comment_out_password_options()
        #click.echo("Migration successful", err=True)
    elif mode == "disable":
        if not has_cur:
            click.echo(
                "No active key found to disable.",
                err=True,
            )
            ctx.exit(1)
        if archive:
            _archive_key(cur_path, archivedir)
        else:
            os.remove(cur_path)
        click.echo("Key disabled")
    else:
        raise ValueError("Unexpected value for mode")


def _setup_keydir(base: str) -> Tuple[str, str]:
    keydir = os.path.join(base, KEY_DIR)
    if not os.path.exists(keydir):
        os.mkdir(keydir, mode=0o700)
    archivedir = os.path.join(base, KEY_ARCHIVE)
    if not os.path.exists(archivedir):
        os.mkdir(archivedir, mode=0o700)
    return (keydir, archivedir)


def _archive_key(key_path: str, archivedir: str) -> None:
    """Archived keys are stored under incrementing ids."""
    next_id = int(max(os.listdir(archivedir), key=_int_or_null, default=0)) + 1
    new_path = os.path.join(archivedir, str(next_id))
    if os.path.exists(new_path):
        raise RuntimeError(f"Archived key already exists at {new_path}")
    os.rename(key_path, new_path)


def _int_or_null(obj: str) -> int:
    try:
        return int(obj)
    except TypeError:
        return 0


def _check_migrate_passwordbased(
        ctx: click.Context,
        crypto: gpcrypto.EncryptionProvider
) -> None:
    if isinstance(crypto, gpcrypto.PasswordSecretBox):
        ctx.invoke(manage_keys, mode="migrate", no_archive=False)


def _check_abort_passwordbased(
        ctx: click.Context,
        crypto: gpcrypto.EncryptionProvider
) -> None:
    if isinstance(crypto, gpcrypto.PasswordSecretBox):
        click.echo(
            "A password is set in your config. "
            "Password-based encryption is no longer supported. "
            "To migrate run\n\n"
            "    git-privacy keys --migrate-pwd\n",
            err=True,
        )
        ctx.exit(1)


def get_active_key(base: str) -> str:
    """Returns the encoded active key."""
    path = os.path.join(base, KEY_CURRENT)
    try:
        with open(path) as f:
            key = f.read()
    except FileNotFoundError:
        key = ""
    return key


def get_archived_keys(base: str) -> Iterator[str]:
    """Returns an iterator over all archived keys. Newest first."""
    archivedir = os.path.join(base, KEY_ARCHIVE)
    if os.path.isdir(archivedir):
        keyfiles = os.listdir(archivedir)
    else:
        keyfiles = []
    ids = filter(
        lambda x: x != 0,  # sort out non-integer filenames
        map(_int_or_null, keyfiles),
    )
    # newest key has highest id
    for key_id in sorted(ids, reverse=True):
        path = os.path.join(archivedir, str(key_id))
        with open(path) as f:
            key = f.read()
        yield key

import argparse
import logging
import os
import random
import string
from threading import Thread
from typing import Callable, Iterable, Optional, Tuple, Union

from deltachat_rpc_client import Bot, DeltaChat, Rpc
from deltachat_rpc_client._utils import AttrDict
from deltachat_rpc_client.events import EventFilter

from .commands import migrate_from_cffi
from .relay import relayhooks
from .setup import setuphooks
from .util import has_crew

ALPHANUMERIC = string.ascii_lowercase + string.digits


def run_bot(
    log: logging.Logger,
    accounts_dir: Optional[str] = None,
    until: Optional[Callable[[AttrDict], bool]] = None,
    email: Optional[str] = None,
    password: Optional[str] = None,
    hooks: Optional[Iterable[Tuple[Callable, Union[type, "EventFilter"]]]] = None,
    **kwargs,
) -> str:
    """Run the bot until a condition returns true.

    :param log: the logger object
    :param accounts_dir: the directory where the account database is stored
    :param until: to stop the bot, make this function return True
    :param email: the email address of the bot
    :param password: the password for the email address
    :param hooks: a collection of hooks which the bot will use
    :return the accounts directory
    """
    if not accounts_dir:
        accounts_dir = os.getcwd() + "/.config/team-bot/"
        log.warning(f"No --dbdir specified, using the default directory: {accounts_dir}")

    if os.path.exists(os.path.join(accounts_dir, "delta.sqlite")):
        log.warning(f"Migrating data from {accounts_dir}/delta.sqlite to new accounts.toml format:")
        migrate_from_cffi(accounts_dir, **kwargs)

    with Rpc(accounts_dir=accounts_dir, **kwargs) as rpc:
        deltachat = DeltaChat(rpc)
        core_version = (deltachat.get_system_info()).deltachat_core_version
        accounts = deltachat.get_all_accounts()
        account = accounts[0] if accounts else deltachat.add_account()

        client = Bot(account, hooks)
        client.logger.debug("Running deltachat core %s", core_version)

        if not client.is_configured():
            if not email:
                email = "".join(random.choices(ALPHANUMERIC, k=9)) + "@nine.testrun.org"
                log.warning(f"No email specified, creating new chatmail address: {email}")
            if not password:
                password = "".join(random.choices(ALPHANUMERIC, k=20))
                log.warning("No password specified, trying with random password")
            configure_thread = Thread(
                target=client.configure,
                daemon=True,
                kwargs={"email": email, "password": password},
            )
            configure_thread.start()
        if until:
            client.run_until(until)
            return accounts_dir
        else:
            client.run_forever()


def main():
    """This is the CLI entry point."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--dbdir", help="accounts folder", default=os.getenv("TEAMS_DBDIR"))
    parser.add_argument("--email", action="store", help="email address", default=os.getenv("TEAMS_INIT_EMAIL"))
    parser.add_argument("--password", action="store", help="password", default=os.getenv("TEAMS_INIT_PASSWORD"))
    parser.add_argument("--verbose", "-v", action="count", default=0)
    args = parser.parse_args()

    log = logging.getLogger("root")
    if args.verbose:
        log.setLevel(logging.INFO)
        if args.verbose > 1:
            log.setLevel(logging.DEBUG)

    accounts_dir = run_bot(
        log,
        until=has_crew,
        accounts_dir=args.dbdir,
        email=args.email,
        password=args.password,
        hooks=setuphooks,
    )

    run_bot(
        log,
        accounts_dir=accounts_dir,
        email=args.email,
        password=args.password,
        hooks=relayhooks,
    )


if __name__ == "__main__":
    main()

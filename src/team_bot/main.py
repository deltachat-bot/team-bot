import argparse
import os
import random
import string
from typing import Optional, Iterable, Tuple, Callable, Union
from threading import Thread

from deltachat_rpc_client import Rpc, DeltaChat, Bot
from deltachat_rpc_client.events import EventFilter
from deltachat_rpc_client._utils import AttrDict

from .setup import setuphooks
from .relay import relayhooks
from .util import get_crew_id


ALPHANUMERIC = string.ascii_lowercase + string.digits

def run_bot(
        accounts_dir: Optional[str] = None,
        until: Optional[Callable[[AttrDict], int]] = None,
        email: Optional[str] = None,
        password: Optional[str] = None,
        hooks: Optional[Iterable[Tuple[Callable, Union[type, "EventFilter"]]]] = None,
        **kwargs,
):
    """Run the bot until a condition returns true.

    :param accounts_dir: the directory where the account database is stored
    :param until: to stop the bot, make this function return True
    :param email: the email address of the bot
    :param password: the password for the email address
    :param hooks: a collection of hooks which the bot will use
    """
    with Rpc(accounts_dir=accounts_dir, **kwargs) as rpc:
        deltachat = DeltaChat(rpc)
        core_version = (deltachat.get_system_info()).deltachat_core_version
        accounts = deltachat.get_all_accounts()
        account = accounts[0] if accounts else deltachat.add_account()

        client = Bot(account, hooks)
        client.logger.debug("Running deltachat core %s", core_version)
        if not client.is_configured():
            assert email, "Account is not configured and email must be provided"
            assert password, "Account is not configured and password must be provided"
            configure_thread = Thread(
                target=client.configure,
                daemon=True,
                kwargs={"email": email, "password": password},
            )
            configure_thread.start()
        if until:
            client.run_until(until)
        else:
            client.run_forever()


def main():
    """This is the CLI entry point."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--dbdir", help="accounts folder", default=os.getenv("TEAMS_DBDIR"))
    parser.add_argument("--email", action="store", help="email address", default=os.getenv("TEAMS_INIT_EMAIL"))
    parser.add_argument("--password", action="store", help="password", default=os.getenv("TEAMS_INIT_PASSWORD"))
    args = parser.parse_args()

    email = args.email
    if not email:
        email = "".join(random.choices(ALPHANUMERIC, k=9)) + "@nine.testrun.org"
    password = "".join(random.choices(ALPHANUMERIC, k=20)) if not args.password else args.password

    accounts_dir = args.dbdir
    if not accounts_dir:
        accounts_dir = os.getcwd() + "/.config/team-bot/" + email

    run_bot(
        until=get_crew_id,
        accounts_dir=accounts_dir,
        email=email,
        password=password,
        hooks=setuphooks,
    )

    run_bot(
        accounts_dir=accounts_dir,
        hooks=relayhooks,
    )


if __name__ == "__main__":
    main()

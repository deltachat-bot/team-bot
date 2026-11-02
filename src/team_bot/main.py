import argparse
import logging
import os
from threading import Thread
from typing import Callable, Iterable, Optional, Tuple, Union

from deltachat_rpc_client import Bot, DeltaChat, Rpc
from deltachat_rpc_client._utils import AttrDict
from deltachat_rpc_client.events import EventFilter

from .commands import migrate_from_cffi
from .exception_notifier import exception_notifier
from .relay import relayhooks
from .setup import configure_email, configure_password, configure_proxy, setuphooks
from .util import has_crew


def run_bot(
    log: logging.Logger,
    accounts_dir: Optional[str] = None,
    until: Optional[Callable[[AttrDict], bool]] = None,
    specified_email: Optional[str] = None,
    specified_password: Optional[str] = None,
    proxy_url: Optional[str] = None,
    hooks: Optional[Iterable[Tuple[Callable, Union[type, "EventFilter"]]]] = None,
    **kwargs,
) -> str:
    """Run the bot until a condition returns true.

    :param log: the logger object
    :param accounts_dir: the directory where the account database is stored
    :param until: to stop the bot, make this function return True
    :param specified_email: the email address of the bot
    :param specified_password: the password for the email address
    :param proxy_url: a proxy to run connections through
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
        exception_notifier.set_account(account)
        client.logger.debug("Running deltachat core %s", core_version)

        if hooks.__name__ == "Setup hooks":
            email_changed, email = configure_email(specified_email, account.get_config("configured_addr"))
            pass_changed, password = configure_password(specified_password, account.get_config("mail_pw"))
            proxy_changed = configure_proxy(proxy_url, account)
            if email_changed or pass_changed or proxy_changed:
                configure_thread = Thread(
                    target=client.configure,
                    daemon=True,
                    kwargs={"email": email, "password": password},
                )
                configure_thread.start()

        log.info("Start listening to messages with " + hooks.__name__)
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
    parser.add_argument(
        "--proxy-url", help="A proxy, e.g. socks5://127.0.0.1:9050", default=os.getenv("TEAMS_PROXY_URL")
    )
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
        proxy_url=args.proxy_url,
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

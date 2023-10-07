import logging
import sys

import click
import qrcode
import deltachat

from .bot import SetupPlugin, RelayPlugin, get_crew_id


def set_log_level(verbose: int, db: str):
    """Set log level; only call this function once, as it uses logging.basicConfig only.

    :param verbose: 0: WARNING, 1: INFO, 2: DEBUG
    :param db: the path to the delta chat database
    """
    loglevel = logging.WARNING
    if verbose:
        loglevel = logging.INFO
        if verbose == 2:
            loglevel = logging.DEBUG
    logging.basicConfig(format="%(levelname)s:%(message)s", level=loglevel)
    logging.info("the delta chat database path is %s", db)


@click.command(
    cls=click.Group, context_settings={"help_option_names": ["-h", "--help"]}
)
@click.pass_context
def teams_bot(ctx):
    """This bot connects your team to the outside and makes it addressable."""


@teams_bot.command()
@click.option("--email", type=str, default=None, help="the email account for the bot")
@click.option(
    "--password", type=str, default=None, help="the password of the email account"
)
@click.option(
    "--db", type=str, default="bot.db/db.sqlite", help="path to the bot's database"
)
@click.option(
    "-v", "--verbose", count=True, help="show low level delta chat ffi events"
)
@click.pass_context
def init(ctx, email: str, password: str, db: str, verbose: int):
    """Configure bot; create crew; add user to crew by scanning a QR code."""
    set_log_level(verbose, db)

    ac = deltachat.Account(db)
    ac.run_account(addr=email, password=password, show_ffi=verbose)
    ac.set_config("mvbox_move", "1")
    ac.set_config("sentbox_watch", "0")

    crew_id_old = get_crew_id(ac)

    chat = ac.create_group_chat(
        "Team: {}".format(ac.get_config("addr")), contacts=[], verified=True
    )

    setupplugin = SetupPlugin(chat.id)
    ac.add_account_plugin(setupplugin)

    chatinvite = chat.get_join_qr()
    qr = qrcode.QRCode()
    qr.add_data(chatinvite)
    print(
        "\nPlease scan this qr code with Delta Chat to join the verified crew group:\n\n"
    )
    qr.print_ascii(invert=True)
    print(
        "\nAlternatively, copy-paste this invite to your Delta Chat desktop client:",
        chatinvite,
    )

    print("\nWaiting until you join the chat")
    sys.stdout.flush()  # flush stdout to actually show the messages above
    setupplugin.member_added.wait()
    setupplugin.message_sent.clear()

    chat.send_text(
        "Welcome to the %s crew! Type /help to see the existing commands."
        % (ac.get_config("addr"),)
    )
    print("Welcome message sent.")
    setupplugin.message_sent.wait()

    if crew_id_old:
        setupplugin.message_sent.clear()
        try:
            new_crew_id = get_crew_id(
                ac, setupplugin
            )  # notify old crew about who created the new crew
            assert (
                new_crew_id == chat.id
            ), f"Bot found different 'new crew' than the one we just created; consider deleting {db}"
            setupplugin.message_sent.wait()
        except ValueError as e:
            logging.warning("Could not notify the old crew: %s", str(e))
        print("The old crew was deactivated.")
    sys.stdout.flush()  # flush stdout to actually show the messages above
    ac.shutdown()


@teams_bot.command()
@click.option(
    "--db", type=str, default="bot.db/db.sqlite", help="path to the bot's database"
)
@click.option(
    "-v", "--verbose", count=True, help="show low level delta chat ffi events"
)
@click.pass_context
def run(ctx, db: str, verbose: int):
    """Run the bot, so it relays messages between the crew and the outside."""
    set_log_level(verbose, db)

    ac = deltachat.Account(db)
    display_name = ac.get_config("displayname")
    ac.run_account(account_plugins=[RelayPlugin(ac)], show_ffi=verbose)
    ac.set_config("displayname", display_name)
    try:
        ac.wait_shutdown()
    except KeyboardInterrupt:
        logging.info("Received KeyboardInterrupt")
        print("Shutting down...")
        ac.shutdown()
        ac.wait_shutdown()


def main():
    teams_bot(auto_envvar_prefix="TEAMS")


if __name__ == "__main__":
    main()

import logging
import pathlib
import sys

import pickledb
import click
import qrcode
import deltachat

from .bot import SetupPlugin, RelayPlugin


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
    "--dbdir",
    type=str,
    default="teams_bot_data",
    help="path to the bot's database",
    envvar="TEAMS_DBDIR",
)
@click.option(
    "-v", "--verbose", count=True, help="show low level delta chat ffi events"
)
@click.pass_context
def init(ctx, email: str, password: str, dbdir: str, verbose: int):
    """Scan a QR code to create a crew and join it"""
    dbdir = pathlib.Path(dbdir)
    delta_db = str(dbdir.joinpath("delta.sqlite"))
    pickle_path = dbdir.joinpath("pickle.db")
    kvstore = pickledb.load(pickle_path, True)

    set_log_level(verbose, delta_db)

    ac = deltachat.Account(delta_db)
    ac.run_account(addr=email, password=password, show_ffi=verbose)
    ac.set_config("mvbox_move", "1")
    ac.set_config("sentbox_watch", "0")

    crew_id_old = kvstore.get("crew_id")

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
        old_crew = ac.get_chat_by_id(crew_id_old)
        old_crew.set_name(f"Old Team: {ac.get_config('addr')}")
        new_crew = [contact.addr for contact in chat.get_contacts()]
        new_crew_emails = " or ".join(new_crew)
        quit_message = f"There is a new Group for the Team now; you can ask {new_crew_emails} to add you to it."
        logging.debug(
            "Sending quit message to old crew with ID %s: %s",
            old_crew.id,
            quit_message,
        )
        try:
            old_crew.send_text(quit_message)
            setupplugin.outgoing_messages += 1
            old_crew.remove_contact(ac.get_self_contact())
            setupplugin.message_sent.wait()
        except ValueError as e:
            logging.warning("Could not notify the old crew: %s", str(e))
        print("The old crew was deactivated.")
    sys.stdout.flush()  # flush stdout to actually show the messages above
    ac.shutdown()

    kvstore.set("crew_id", chat.id)
    logging.info("Successfully changed crew ID to the new group.")


@teams_bot.command()
@click.option(
    "--dbdir",
    type=str,
    default="teams_bot_data",
    help="path to the bot's database",
    envvar="TEAMS_DBDIR",
)
@click.option(
    "-v", "--verbose", count=True, help="show low level delta chat ffi events"
)
@click.pass_context
def run(ctx, dbdir: str, verbose: int):
    """Run the bot, so it relays messages from and to the outside"""
    dbdir = pathlib.Path(dbdir)
    delta_db = str(dbdir.joinpath("delta.sqlite"))
    pickle_path = dbdir.joinpath("pickle.db")
    kvstore = pickledb.load(pickle_path, True)

    set_log_level(verbose, delta_db)

    ac = deltachat.Account(delta_db)
    display_name = ac.get_config("displayname")
    ac.run_account(account_plugins=[RelayPlugin(ac, kvstore)], show_ffi=verbose)
    ac.set_config("displayname", display_name)
    try:
        ac.wait_shutdown()
    except KeyboardInterrupt:
        logging.info("Received KeyboardInterrupt")
        print("Shutting down...")
        ac.shutdown()
        ac.wait_shutdown()


@teams_bot.command()
@click.option(
    "--dbdir",
    type=str,
    default="teams_bot_data",
    help="path to the bot's database",
    envvar="TEAMS_DBDIR",
)
@click.option(
    "-v", "--verbose", count=True, help="show low level delta chat ffi events"
)
@click.pass_context
def verify_crypto(ctx, dbdir: str, verbose: int):
    """Show a QR code to verify the encryption with the bot"""
    dbdir = pathlib.Path(dbdir)
    delta_db = str(dbdir.joinpath("delta.sqlite"))

    set_log_level(verbose, delta_db)

    ac = deltachat.Account(delta_db)
    ac.run_account(show_ffi=verbose)

    setup_contact = ac.get_setup_contact_qr()
    qr = qrcode.QRCode()
    qr.add_data(setup_contact)
    print(
        "\nPlease scan this qr code with Delta Chat to verify the bot:\n\n"
    )
    qr.print_ascii(invert=True)
    print(
        "\nAlternatively, copy-paste this invite to your Delta Chat desktop client:",
        setup_contact,
    )


def main():
    teams_bot(auto_envvar_prefix="TEAMS")


if __name__ == "__main__":
    main()

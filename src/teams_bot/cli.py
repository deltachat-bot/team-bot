import click
import logging


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


@click.group()
@click.pass_context
def cli(ctx):
    """This bot connects your team to the outside and makes it addressable."""


@cli.command()
@click.option("--email", type=str, default=None, help="the email account for the bot")
@click.option("--password", type=str, default=None, help="the password of the email account")
@click.option("--db", type=str, default="bot.db/db.sqlite", help="path to the bot's database")
@click.option("-v", "--verbose", count=True, help="show low level delta chat ffi events")
@click.pass_context
def init(ctx, email: str, password: str, db: str, verbose: int):
    """Configure the bot, create a crew, and add the user to crew by scanning a QR code."""
    set_log_level(verbose, db)


@cli.command()
@click.option(
    "--db", type=str, default="bot.db/db.sqlite", help="path to the bot's database"
)
@click.option(
    "-v", "--verbose", count=True, help="show low level delta chat ffi events"
)
@click.pass_context
def run(ctx, db: str, verbose: int):
    set_log_level(verbose, db)


def main():
    cli(auto_envvar_prefix="TEAMS")


if __name__ == "__main__":
    main()

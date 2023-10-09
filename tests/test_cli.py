def test_help(cmd):
    cmd.run_ok(
        [],
        """
        Usage: teams-bot [OPTIONS] COMMAND [ARGS]...
        * -h, --help  Show this message and exit.
        * init           Scan a QR code to create a crew and join it
        * run            Run the bot, so it relays messages from and to the outside
        * verify-crypto  Show a QR code to verify the encryption with the bot
        """,
    )

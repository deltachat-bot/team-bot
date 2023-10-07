def test_help(cmd):
    cmd.run_ok(
        [],
        """
        Usage: teams-bot [OPTIONS] COMMAND [ARGS]...
        * -h, --help  Show this message and exit.
        * init  Configure bot; create crew; add user to crew by scanning a QR code.
        """,
    )

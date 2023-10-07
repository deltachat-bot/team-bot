# Teams Bot

This bot connects your team to the outside
and makes it addressable.

Configure this bot with your team address
(e.g. helpdesk@example.org),
and add all your **team members** to the **crew**.
Then,
every time **an outsider** writes to your team address,
the bot opens a new **relay group** with all of you;
you can use the relay group to discuss the request in private
and when you have come to a conclusion,
**answer** the **request**.
The bot will forward the answer to the outsider
in the name of the team,
hiding the identities of the team members.

## Setup

To install this bot,
run:

```
git clone https://git.0x90.space/missytake/teams-bot
cd teams-bot
pip install .
```

Now you can configure it
with an email address
you want to use as a team:

```
teams-bot init --email das_synthikat@systemli.org --password p455w0rD
```

This command will show a QR code;
scan it with Delta Chat
to become part of the "team",
the verified group which manages the Teams Bot.

Now to run it,
simply execute:

```
teams-bot init --email das_synthikat@systemli.org --password p455w0rD
```

The bot only works as long as this command is running.
Read more about [running bots on
bots.delta.chat](https://bots.delta.chat/howto.html).

## Development Environment

To get started with developing,
run:

```
python3 -m venv venv
. venv/bin/activate
pip install pytest tox black pytest-xdist
pip install -e .
DCC_NEW_TMP_EMAIL='https://ci.testrun.org/new_email?t=1h_2364962873z' tox
```

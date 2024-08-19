# Team Bot

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
git clone https://github.com/deltachat-bot/team-bot
cd team-bot
pip install .
```

Now you can configure it
with an email address
you want to use as a team:

```
team-bot init --email helpdesk@example.org --password p455w0rD
```

This command will show a QR code;
scan it with Delta Chat
to become part of the "team",
the verified group which manages the Team Bot.

Now to run it,
simply execute:

```
team-bot run -v
```

The bot only works as long as this command is running.
Read more about [running bots on
bots.delta.chat](https://bots.delta.chat/howto.html).


### Deploy with pyinfra

If you use [pyinfra](https://pyinfra.com/) to manage a server,
you can deploy this bot with it.
Just import it into your [deploy.py file](https://docs.pyinfra.com/en/2.x/getting-started.html#create-a-deploy) like this:

```
from team_bot.pyinfra import deploy_team_bot

deploy_team_bot(
    unix_user='root',                   # an existing UNIX user (doesn't need root or sudo privileges)
    bot_email='helpdesk@example.org',   # the email address your team wants to use
    bot_passwd='p4ssw0rd',              # the password to the email account
)
```

After you deployed it,
you need to do two steps manually:

First,
to initialize the bot,
create the crew,
and join the crew,
login to the user with ssh
and run:

```
export $(cat ~/.env | xargs) && ~/.local/lib/team-bot.venv/bin/team-bot init
```

Then,
to start the bot
and keep it running in the background,
run:

```
systemctl --user enable --now team-bot
```

You can view the log output
with `journalctl --user -fu team-bot`
to confirm that it works.

## Development Environment

To get started with developing,
run:

```
python3 -m venv venv
. venv/bin/activate
pip install -e .[dev]
tox
```

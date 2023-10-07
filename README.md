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

### Configuration

## Usage: Command Line Interface

## Development Environment

To get started with developing,
run:

```
python3 -m venv venv
. venv/bin/activate
pip install pytest tox black
pip install -e .
tox
```

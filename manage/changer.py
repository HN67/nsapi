"""Changes the password of nations.

Written by HN67.
"""

import dataclasses
import logging
import sys
import time

import mechanize

loggerMechanize = logging.getLogger("mechanize")
# loggerMechanize.addHandler(logging.StreamHandler(sys.stdout))
# loggerMechanize.setLevel(logging.DEBUG)


@dataclasses.dataclass
class Change:
    """Dataclass representing a change to be performed."""

    nation: str
    current: str
    new: str


def delay() -> None:
    """Delay long enough to obey HTML ratelimits."""
    time.sleep(6.1)


user_agent = input("Please enter a user agent (i.e. nation name): ")
user_agent = "HN67 Password Changer, run by " + user_agent

log_file = "passwordchanger.log"
file_handler = logging.FileHandler(log_file)
std_handler = logging.StreamHandler(sys.stdout)
logger = logging.getLogger("changer")
logger.addHandler(file_handler)
logger.addHandler(std_handler)
logger.setLevel(logging.INFO)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
file_handler.setFormatter(formatter)
std_handler.setFormatter(formatter)


# debugging
# bot.set_debug_http(True)
# bot.set_debug_responses(True)
# bot.set_debug_redirects(True)

# https://www.nationstates.net/page=settings/template-overall=none

data_file = input("Enter file name of nation,current,new lines: ")

# load file
changes = []
with open(data_file, "r") as file:
    for line in file:
        if not line == "\n":
            pieces = line.strip().split(",")
            changes.append(Change(pieces[0], pieces[1], pieces[2]))

logger.info("Starting session")

# create bot
bot = mechanize.Browser()
bot.addheaders = [("User-Agent", user_agent)]

for change in changes:

    logger.info("Operating on nation %s", change.nation)

    # open login page
    logger.info("Sleeping to meet ratelimit")
    delay()
    logger.info("Opening login page.")
    bot.open("https://www.nationstates.net/page=login/template-overall=none")

    if bot.forms():

        # attempt to submit login
        # obey ratelimit
        logger.info("Sleeping to meet ratelimit")
        delay()
        logger.info("Logging in")
        bot.form = bot.forms()[0]
        bot.form.set_value(change.nation, name="nation")
        bot.form.set_value(change.current, name="password")
        response = bot.submit()

        # verify success
        if b'body id="loggedin"' in response.get_data():

            # go to settings page
            logger.info("Sleeping to meet ratelimit")
            delay()
            logger.info("Opening settings page")
            bot.open("https://www.nationstates.net/page=settings/template-overall=none")
            # attempt to submit password change
            logger.info("Sleeping to meet ratelimit")
            delay()
            logger.info("Submitting password change")
            bot.form = bot.forms()[0]
            bot.form.set_value(change.new, name="password")
            bot.form.set_value(change.new, name="confirm_password")
            settings_response = bot.submit()

            # verify success
            if (
                b"Your settings have been successfully updated."
                in settings_response.get_data()
            ):
                logger.info("Nation %s has been sucsessfully updated.", change.nation)
            else:
                logger.warning(
                    "Something went wrong with changing password for %s", change.nation
                )

        else:
            logger.info("Failed to log in nation %s", change.nation)

    else:
        logger.warning(
            "Unknown error, login form could not be found for nation %s", change.nation
        )

logger.info("Session finished.")

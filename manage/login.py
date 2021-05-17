"""Pings a nation to register activity, and also returns an autologin"""

import getpass
import logging

import config
import nsapi

# Set logging level
level = logging.INFO
logging.basicConfig(level=level)
# Name logger
logger = logging.getLogger()
# Change nsapi logging level
nsapi.logger.setLevel(level=level)


def main() -> None:
    """Main function"""

    requester = nsapi.NSRequester(config.userAgent)

    nation = input("Nation: ")

    try:
        autologin = requester.nation(
            nation, auth=nsapi.Auth(password=getpass.getpass("Password: "))
        ).get_autologin()
    except KeyError:
        print("Something went wrong, likely incorrect password")
    else:
        print(f"Autologin: {autologin}")


if __name__ == "__main__":
    main()

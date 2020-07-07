"""Autologins a list of nations, with the option of also generating autologin keys."""

import logging
from typing import Dict, Mapping, Optional

import config
import nsapi

# Set logging level
level = logging.WARNING
logging.basicConfig(level=level)
# Name logger
logger = logging.getLogger()
# Change nsapi logging level
nsapi.logger.setLevel(level=level)


def autologin(
    requester: nsapi.NSRequester, nations: Mapping[str, str], isAutologin: bool
) -> Mapping[str, Optional[str]]:
    """Autologins a list of nations, from the nations dict of {nation: password/autologin}.
    If isAutologin is true, the passwords are interpreted as autologins.
    Returns a dict mapping from nations to autologins.
    If the autologin value of the returned mapping is None, that means the login failed.
    """
    output: Dict[str, Optional[str]] = {}
    for nation, password in nations.items():
        # Check how to interpret password
        if isAutologin:
            nationAPI = requester.nation(nation, nsapi.Auth(autologin=password))
        else:
            nationAPI = requester.nation(nation, nsapi.Auth(password=password))
        # .ping is true if the authentication was succseful
        if nationAPI.ping():
            # This shouldnt make a request since the ping was succsesful
            output[nation] = nationAPI.get_autologin()
        else:
            output[nation] = None
    return output


def main() -> None:
    """Main function"""

    print(
        "Specify a file to load the nation list from. (Based on this script's directory)"
    )
    print("Nation name and password should be seperated with a single comma, no space.")
    inputPath = input("File: ")

    print(
        "\nShould the passwords be interpreted as autologins keys (encrypted versions)? (y/n)"
    )
    autologinInput = input("Interpret as autologins? ").lower()
    if autologinInput in ("yes", "y"):
        isAutologin = True
        print("Okay, will interpret as autologin keys.")
    else:
        isAutologin = False
        print("Okay, will interpret as regular passwords.")

    print(
        "\nEnter a file to generate autologin keys in, or enter nothing to not generate a file."
    )
    outputPath = input("Autologin Output File: ")

    requester = nsapi.NSRequester(config.userAgent)

    # Collect nationlist
    nations = {}
    with open(nsapi.absolute_path(inputPath), "r") as file:
        for line in file:
            # Split exactly once to allow passwords that contain commas
            nation, password = line.strip().split(",", maxsplit=1)
            nations[nation] = password

    output = autologin(requester, nations, isAutologin)

    # Summarize results
    for nation, autologinValue in output.items():
        if autologinValue:
            print(f"Successfully logged {nation} in.")
        else:
            print(f"Failed to log in {nation}. Likely an incorrect password.")

    # Only generate output if desired
    if outputPath != "":
        with open(nsapi.absolute_path(outputPath), "w") as file:
            for nation, autologinValue in output.items():
                print(f"{nation},{autologinValue}", file=file)


if __name__ == "__main__":
    main()

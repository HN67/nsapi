"""Autologins a list of nations, with the option of also generating autologin keys."""

import dataclasses
import logging
from typing import Dict, Mapping, Optional

import config
import nsapi

# Set logging level
level = logging.INFO
# Name logger
logger = logging.getLogger(__name__)
# Configure loggers
nsapi.configure_logger(logging.getLogger(), level=level)


@dataclasses.dataclass()
class Result:
    """Class containing resulting data from autologin method."""

    autologin: str
    region: str
    wa: bool


def autologin(
    requester: nsapi.NSRequester, nations: Mapping[str, str], isAutologin: bool
) -> Mapping[str, Optional[Result]]:
    """Autologins a list of nations, from the nations dict of {nation: password/autologin}.
    If isAutologin is true, the passwords are interpreted as autologins.
    Returns a dict mapping from nations to autologins.
    If the autologin value of the returned mapping is None, that means the login failed.
    """
    output: Dict[str, Optional[Result]] = {}
    for nation, password in nations.items():
        # Check how to interpret password
        if isAutologin:
            nationAPI = requester.nation(nation, nsapi.Auth(autologin=password))
        else:
            nationAPI = requester.nation(nation, nsapi.Auth(password=password))
        # Try making the shard request
        try:
            shards = nationAPI.shards("region", "ping", "wa")
        except nsapi.APIError:
            output[nation] = None
        else:
            output[nation] = Result(
                autologin=nationAPI.get_autologin(),
                region=shards["region"],
                wa=shards["unstatus"].startswith("WA"),
            )
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
    with open(inputPath, "r") as file:
        for line in file:
            # Ignore empty lines
            if not line == "\n":
                # Split exactly once to allow passwords that contain commas
                nation, password = line.strip().split(",", maxsplit=1)
                nations[nation] = password

    output = autologin(requester, nations, isAutologin)

    # Summarize results
    for nation, result in output.items():
        if result:
            string = f"Successfully logged {nation} in. (Region: {result.region})"
            if result.wa:
                string += " (WA)"
            print(string)
        else:
            print(f"Failed to log in {nation}. Likely an incorrect password.")

    # Only generate output if desired
    if outputPath != "":
        with open(outputPath, "w") as file:
            for nation, result in output.items():
                print(f"{nation},{result.autologin if result else None}", file=file)


if __name__ == "__main__":
    main()

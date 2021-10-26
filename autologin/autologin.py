"""Autologins a list of nations, with the option of also generating autologin keys."""

import argparse
import dataclasses
import logging
import sys
import typing as t

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


def autologin_many(
    requester: nsapi.NSRequester, nations: t.Mapping[str, str], isAutologin: bool
) -> t.Mapping[str, t.Optional[Result]]:
    """Autologins a list of nations, from the nations dict of {nation: password/autologin}.
    If isAutologin is true, the passwords are interpreted as autologins.
    Returns a dict mapping from nations to autologins.
    If the autologin value of the returned mapping is None, that means the login failed.
    """
    output: t.Dict[str, t.Optional[Result]] = {}
    for nation, password in nations.items():
        # Check how to interpret password
        if isAutologin:
            auth = nsapi.Auth(autologin=password)
        else:
            auth = nsapi.Auth(password=password)
        # Create API object
        nationAPI = requester.nation(nation, auth)
        # Try making the shard request
        try:
            shards = nationAPI.shards("region", "ping", "wa")
        except nsapi.APIError:
            # None indicates any failure
            output[nation] = None
        else:
            output[nation] = Result(
                autologin=nationAPI.get_autologin(),
                region=shards["region"],
                wa=shards["unstatus"].startswith("WA"),
            )
    return output


def login(
    requester: nsapi.NSRequester,
    nation: str,
    autologin: t.Optional[str],
    password: t.Optional[str],
) -> t.Optional[Result]:
    """Attempts to log in a nation via NS API.

    Returns None on failure.

    At least one of password or autologin must be provided;
    autologin is used if both are provided.
    """
    # Create API object
    nationAPI = requester.nation(
        nation, auth=nsapi.Auth(autologin=autologin, password=password)
    )
    # Try making the shard request
    try:
        shards = nationAPI.shards("region", "ping", "wa")
    except nsapi.APIError:
        # None indicates any failure
        return None
    else:
        return Result(
            autologin=nationAPI.get_autologin(),
            region=shards["region"],
            wa=shards["unstatus"].startswith("WA"),
        )


def parse_line(line: str, delimiter: str = ",") -> t.Tuple[str, t.Optional[str]]:
    """Attempt to parse a two value line.

    Splits on the given delimiter,
    and returns None for the second token
    if the delimiter does not exist.
    """
    tokens = line.strip().split(delimiter, maxsplit=1)
    return (tokens[0], tokens[1] if len(tokens) > 1 else None)


def main() -> None:
    """Autlogin a list of nations.

    Each line should contain a <nation>,<password> pair.

    Blank lines and lines without a comma are ignored.
    """

    parser = argparse.ArgumentParser(description="Autologin a list of nations.")
    parser.add_argument(
        "--plain",
        action="store_true",
        dest="plain",
        help="Treat passwords as plaintext instead of autologin keys.",
    )
    parser.add_argument(
        "-o", "--output", default=None, help="Output destination of autologin keys."
    )

    args = parser.parse_args()

    requester = nsapi.NSRequester(config.userAgent)

    # Parse input
    results = []
    for nation, key in (parse_line(line) for line in sys.stdin):
        if key:
            result = login(
                requester,
                nation,
                key if not args.plain else None,
                key if args.plain else None,
            )
            if result:
                string = f"Success: {nation} ({result.region})"
                if result.wa:
                    string += " (WA)"
                print(string)
            else:
                print(f"Failed: {nation}")
            results.append((nation, result))

    # Only generate output if desired
    if args.output:
        with open(args.output, "w", encoding="utf-8") as file:
            for nation, result in results:
                print(f"{nation},{result.autologin if result else None}", file=file)


if __name__ == "__main__":
    main()

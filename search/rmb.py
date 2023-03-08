"""Collect regional message board messages"""

import logging
import os

import config
import nsapi

import pandas

# Name logger
logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


def main() -> None:
    """Main function."""

    # TODO add argparse
    # with options for region,
    # offset, amount, output path

    nsapi.enable_logging()

    requester = nsapi.NSRequester(config.userAgent)

    region_api = requester.region("10000 Islands")

    output_path = "messages.csv"

    for offset in range(0, 1000, 100):
        messages = list(region_api.messages(offset=str(offset)))
        # logger.info(messages)
        dataframe = pandas.DataFrame(
            (
                (message.id, message.timestamp, message.nation, message.message)
                for message in messages
            ),
            columns=("id", "timestamp", "author", "text"),
        )
        dataframe.to_csv(
            output_path, mode="a", header=not os.path.exists(output_path), index=False
        )


if __name__ == "__main__":
    main()

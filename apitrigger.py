"""Returns a link to an API trigger for a nation."""

import argparse
import sys

# TODO would kinda be nice if nsapi had a way to 'prepare' a request, i.e.
# create the link. (maybe even prepare things such as headers?
# requests probably has a Prepared object)


def trigger(nation: str) -> str:
    """Returns a link to an API trigger for the provided nation."""
    return (
        f"https://www.nationstates.net/cgi-bin/api.cgi?nation={nation}"
        "&q=census&mode=score&scale=65"
    )


# Not sure if I like argparse being in the if statement.
# I think it makes sense for main() to be pythonic arguments,
# maybe another function could take argparse arguments and chuck them into a parser.


def main(nation: str) -> None:
    """Main function."""
    print(trigger(nation))


if __name__ == "__main__":

    parser = argparse.ArgumentParser(description="Generates an API trigger link.")

    parser.add_argument("nation", help="Nation to generate trigger for.")

    if len(sys.argv) > 1:
        args = parser.parse_args()
    else:
        args = parser.parse_args([input("Nation: ")])

    main(args.nation)

"""Automatically generate containerrise rules."""

import argparse
import sys

import nsapi


def rule(nation: str) -> str:
    """Produce a ContainerRise rule for a nation."""

    clean = nsapi.clean_format(nation)
    return fr"@^.*\.nationstates\.net/(.*/)?nation={clean}(/.*)?$ , {nation}"


def main() -> None:
    """Main function."""

    parser = argparse.ArgumentParser(
        "Convert list of nation names to ContainerRise rules."
    )
    # Trigger functionality for -h, etc
    parser.parse_args()

    # Ignore blank lines and convert non-blank ones
    for line in sys.stdin:
        nation = line.strip()
        if nation:
            print(rule(nation))
        else:
            print()


if __name__ == "__main__":
    main()

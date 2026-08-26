import asyncio

from sandrone import config
from sandrone.client import runBot


def main() -> None:
    if config.TOKEN is None:
        raise SystemExit("The Bot Token is not set, please configure .env")
    asyncio.run(runBot())


if __name__ == "__main__":
    main()

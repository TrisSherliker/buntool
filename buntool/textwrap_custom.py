# New file: buntool/textwrap_custom.py
import textwrap
from logging import Logger


def dedent_and_log(logger: Logger, message):
    """Dedent a multi-line string and log it."""
    dedented_message = textwrap.dedent(message).strip()
    for line in dedented_message.split("\n"):
        logger.debug(line)

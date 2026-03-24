from enum import Enum

ENDC = "\033[0m"
BOLD = "\033[1m"
UNDERLINE = "\033[4m"
BACK = "\033[22m"


class Color(Enum):
    """ANSI color codes for terminal output."""

    HEADER = "\033[95m"
    OKBLUE = "\033[94m"
    OKGREEN = "\033[92m"
    WARNING = "\033[93m"
    ERROR = "\033[91m"


def colorize(message, color=Color.OKGREEN, underline=False, bold=False):
    """
    Colorizes a message for terminal output.

    Parameters
    ----------
    message : str
        The message to colorize
    color : Color
        The color to use for the message
    underline : bool
        Whether to underline the message
    bold : bool
        Whether to make the message bold

    Returns
    -------
    str
        The colorized message
    """
    colorized_command = ""
    if message.startswith(">>>"):
        parts = message.split(maxsplit=2)
        message = ""
        if len(parts) > 1:
            command = parts[1]
            colorized_command = f">>> {Color.OKGREEN.value}{command}{BACK} "
            message = parts[2] if len(parts) > 2 else ""

    msg = colorized_command + color.value if colorized_command else color.value

    if underline:
        msg += UNDERLINE
    if bold:
        msg += BOLD

    msg += message + ENDC

    return msg

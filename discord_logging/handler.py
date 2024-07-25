"""Python logging support for Discord."""
import logging
import sys
from typing import Optional

from frozendict import frozendict
from discord import SyncWebhook, Embed, HTTPException

DEFAULT_COLOURS = frozendict({
    None: 2040357,  # Unknown log level
    logging.CRITICAL: 14362664,  # Red
    logging.ERROR: 14362664,  # Red
    logging.WARNING: 16497928,  # Yellow
    logging.INFO: 2196944,  # Blue
    logging.DEBUG: 8947848,  # Gray
})


#: The default log emojis as
DEFAULT_EMOJIS = frozendict({
    None: "",  # Unknown log level
    logging.CRITICAL: "🆘",
    logging.ERROR: "❌",
    logging.WARNING: "⚠️",
    logging.INFO: "",
    logging.DEBUG: "",
})


class DiscordHandler(logging.Handler):
    """Output logs to Discord chat.

    A handler class which writes logging records, appropriately formatted,
    to a Discord Server using webhooks.
    """

    def __init__(self,
                 service_name: str,
                 webhook_url: str,
                 colours=DEFAULT_COLOURS,
                 emojis=DEFAULT_EMOJIS,
                 avatar_url: Optional[str]=None):
        """
        :param service_name: Shows at the bot username in Discord.
        :param webhook_url: Channel webhook URL. See README for details.
        :param colours: Log level to Discord embed color mapping
        :param emojis:
            Log level to emoticon decoration mapping.
            If present this is appended as a prefix to the first line of the log.
        :param avatar_url: Bot profile picture
        """

        logging.Handler.__init__(self)
        self.webhook_url = webhook_url
        self.service_name = service_name
        self.colours = colours
        self.emojis = emojis
        self.avatar_url = avatar_url
        self.reentry_barrier = False

    def emit(self, record: logging.LogRecord):
        """Send a log entry to Discord."""

        if self.reentry_barrier:
            # Don't let Discord and request internals to cause logging
            # and thus infinite recursion. This is because the underlying
            # requests package itself uses logging.
            return

        self.reentry_barrier = True

        try:
            # Run internal log message formatting that will expand %s, %d and such
            msg = self.format(record)

            # Choose colour and emoji for this log record
            colour = self.colours.get(record.levelno, self.colours[None])
            emoji = self.emojis.get(record.levelno, "")

            if emoji:
                msg = f"{emoji} {msg}"

            discord = SyncWebhook.from_url(self.webhook_url)
            embed = Embed(color=colour, title=msg)
            discord.send(username=self.service_name, avatar_url=self.avatar_url,embed=embed)
        except HTTPException as he:
            print(f"Error from Discord logger {he}", file=sys.stderr)
        except Exception:
            self.handleError(record)
        finally:
            self.reentry_barrier = False

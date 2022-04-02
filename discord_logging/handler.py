"""Python logging support for Discord."""
import logging
import os
import sys
import textwrap
from typing import Optional

from discord_webhook import DiscordEmbed, DiscordWebhook

#: The default log level colors as hexacimal, converted int
DEFAULT_COLOURS = {
    None: 2040357,
    logging.CRITICAL: 14362664,  # Red
    logging.ERROR: 14362664,  # Red
    logging.WARNING: 16497928,  # Yellow
    logging.INFO: 2196944,  # Blue
    logging.DEBUG: 8947848,  # Gray
}


#: The default log emojis as
DEFAULT_EMOJIS = {
    None: "",
    logging.CRITICAL: "🆘",
    logging.ERROR: "❌",
    logging.WARNING: "⚠️",
    logging.INFO: "",
    logging.DEBUG: "",
}


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
                 avatar_url: Optional[str]=None,
                 rate_limit_retry: bool=True,
                 embed_line_wrap_threshold: int=60):
        """

        :param service_name: Shows at the bot username in Discord.
        :param webhook_url: Channel webhook URL. See README for details.
        :param colours: Log level to Discord embed color mapping
        :param emojis:
            Log level to emoticon decoration mapping.
            If present this is appended as a prefix to the first line of the log.
        :param avatar_url: Bot profile picture
        :param rate_limit_retry: Try to recover when Discord server tells us to slow down
        :param embed_line_wrap_threshold:
            How many characters a text line can contain until we go to "long line" output format.
        """

        logging.Handler.__init__(self)
        self.webhook_url = webhook_url
        self.service_name = service_name
        self.colours = colours
        self.emojis = emojis
        self.rate_limit_retry = rate_limit_retry
        self.avatar_url = avatar_url
        self.reentry_barrier = False
        self.embed_line_wrap_threshold = embed_line_wrap_threshold

    def should_format_as_code_block(self, record: logging.LogRecord, msg: str) -> bool:
        """Figure out whether we want to use code block formatting in Discord.

        Check for new lines and long lines in the log message.
        """

        if "\n" not in msg:
            if len(msg) > self.embed_line_wrap_threshold:
                return True

        return "\n" in msg

    def clip_content(self, content: str, max_len=1900, clip_to_end=True) -> str:
        """Make sure the text fits to a Discord message.

        Discord max message length is 2000 chars.
        """
        if len(content) > max_len - 5:
            if clip_to_end:
                return "..." + content[-max_len:]
            else:
                return content[0:max_len] + "..."
        else:
            return content

    def emit(self, record: logging.LogRecord):
        """Send a log entry to Discord."""

        if self.reentry_barrier:
            # Don't let Discord and request internals to cause logging
            # and thus infinite recursion. This is because the underlying
            # requests package itself uses logging.
            return

        self.reentry_barrier = True

        try:

            discord = DiscordWebhook(
                url=self.webhook_url,
                username=self.service_name,
                rate_limit_retry=self.rate_limit_retry,
                avatar_url=self.avatar_url,
            )

            # About the Embed footer trick
            # https://stackoverflow.com/a/65543555/315168

            try:
                msg = self.format(record)

                colour = self.colours.get(record.levelno) or self.colours[None]
                emoji = self.emojis.get(record.levelno)
                if emoji:
                    # Add some space before the next char
                    emoji += " "

                # discord.content = msg
                if self.should_format_as_code_block(record, msg):

                    try:
                        first, remainder = msg.split("\n", maxsplit=1)
                    except ValueError:
                        first = msg
                        remainder = ""

                    max_line_length = max([len(l) for l in msg.split("\n")])
                    clipped = self.clip_content(remainder)

                    if max_line_length > self.embed_line_wrap_threshold:
                        # msg_with_bold = f"**{first}**\n```{clipped}```"
                        clipped_msg = self.clip_content(msg)
                        discord.content = f"```{emoji}{clipped_msg}```"
                    else:
                        embed = DiscordEmbed(title=f"{emoji}{first}", description=clipped, color=colour)
                        discord.add_embed(embed)

                else:
                    # discord.content = content
                    if emoji:
                        title = f"{emoji}{msg}"
                    else:
                        title = msg
                    embed = DiscordEmbed(title=title, color=colour)
                    discord.add_embed(embed)

                discord.execute()

            except Exception as e:
                # We cannot use handleError here, because Discord request may cause
                # infinite recursion when Discord connection fails and
                # it tries to log.
                # We fall back to writing the error to stderr
                print(f"Error from Discord logger {e}", file=sys.stderr)
                self.handleError(record)
        finally:
            self.reentry_barrier = False



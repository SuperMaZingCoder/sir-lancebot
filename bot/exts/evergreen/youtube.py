import logging
from dataclasses import dataclass
from html import unescape
from typing import List, Optional
from urllib.parse import quote_plus

from discord import Embed
from discord.ext import commands
from discord.utils import escape_markdown

from bot.constants import Colours, Emojis, Tokens

log = logging.getLogger(__name__)

KEY = Tokens.youtube
SEARCH_API = "https://www.googleapis.com/youtube/v3/search"
STATS_API = "https://www.googleapis.com/youtube/v3/videos"
YOUTUBE_VIDEO_URL = "https://www.youtube.com/watch?v={id}"
YOUTUBE_SEARCH_URL = "https://www.youtube.com/results?search_query={search}"
RESULT = (
    "**{index}. [{title}]({url})**\n"
    "{post_detail_emoji} {user_emoji} {username} {view_emoji} {view_count} {like_emoji} {like_count}\n"
)


@dataclass
class VideoStatistics:
    """Represents YouTube video statistics."""

    view_count: int
    like_count: int


@dataclass
class Video:
    """Represents a video search result."""

    title: str
    username: str
    id: str
    video_statistics: VideoStatistics


class YouTubeSearch(commands.Cog):
    """Sends the top 5 results of a query from YouTube."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def format_search_result(self, index: int, result: List[Video]) -> str:
        """Formats search result to put in embed."""
        return RESULT.format(
            index=index,
            title=result.title,
            url=YOUTUBE_VIDEO_URL.format(id=result.id),
            post_detail_emoji=Emojis.post_detail,
            user_emoji=Emojis.user,
            username=result.username,
            view_emoji=Emojis.view,
            view_count=result.video_statistics.view_count,
            like_emoji=Emojis.like,
            like_count=result.video_statistics.like_count,
        )

    async def get_statistics(self, id: str) -> Optional[VideoStatistics]:
        """Queries API for statistics of one video."""
        async with self.bot.http_session.get(
            STATS_API,
            params={"part": "statistics", "id": id, "key": KEY},
        ) as response:
            if response.status != 200:
                log.error(
                    f"YouTube statistics response not successful: response code {response.status}"
                )
                return None

            statistics = (await response.json())["items"][0]["statistics"]

            return VideoStatistics(
                view_count=statistics["viewCount"], like_count=statistics["likeCount"]
            )

    async def search_youtube(self, search: str) -> Optional[List[Video]]:
        """Queries API for top 5 results matching the search term."""
        results = []
        async with self.bot.http_session.get(
            SEARCH_API,
            params={"part": "snippet", "q": search, "safeSearch": "strict", "type": "video", "key": KEY},
        ) as response:
            if response.status != 200:
                log.error(
                    f"YouTube search response not successful: response code {response.status}"
                )
                return None

            video_snippet = await response.json()

            for item in video_snippet["items"]:
                video_statistics = await self.get_statistics(item["id"]["videoId"])

                if video_statistics is None:
                    log.warning(
                        "YouTube statistics response not successful, aborting youtube search"
                    )
                    return None

                results.append(
                    Video(
                        title=escape_markdown(unescape(item["snippet"]["title"])),
                        username=escape_markdown(
                            unescape(item["snippet"]["channelTitle"])
                        ),
                        id=item["id"]["videoId"],
                        video_statistics=video_statistics,
                    )
                )

        return results

    @commands.command(aliases=["yt"])
    @commands.cooldown(1, 15, commands.BucketType.user)
    async def youtube(self, ctx: commands.Context, *, search: str) -> None:
        """Sends the top 5 results of a query from YouTube with fifteen second cool down per user."""
        results = await self.search_youtube(search)

        if results:
            description = "\n".join(
                [
                    await self.format_search_result(index, result)
                    for index, result in enumerate(results, start=1)
                ]
            )
            embed = Embed(
                colour=Colours.dark_green,
                title=f"{Emojis.youtube} YouTube results for `{search}`",
                url=YOUTUBE_SEARCH_URL.format(search=quote_plus(search)),
                description=description,
            )
            await ctx.send(embed=embed)
        else:
            embed = Embed(
                colour=Colours.soft_red,
                title="Something went wrong :/",
                description="Sorry, we could not find a YouTube video.",
            )
            await ctx.send(embed=embed)


def setup(bot: commands.Bot) -> None:
    """Load the YouTube cog."""
    bot.add_cog(YouTubeSearch(bot))

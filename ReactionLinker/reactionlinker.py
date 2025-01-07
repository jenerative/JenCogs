from redbot.core import commands, Config, checks
import discord

class ReactionLinker(commands.Cog):
    """ReactionLinker"""

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=1234567890, force_registration=True)
        default_guild = {
            "channel_id": None,
            "emoji": None
        }
        self.config.register_guild(**default_guild)

    @commands.group()
    @checks.admin()
    async def reactionlinkerset(self, ctx):
        """Make a reaction link to a user's last post."""
        pass

    @reactionlinkerset.command()
    async def channel(self, ctx, channel: discord.TextChannel):
        """Set the channel to track for the user's last post."""
        await self.config.guild(ctx.guild).channel_id.set(channel.id)
        await ctx.send(f"Channel set to {channel.mention}")

    @reactionlinkerset.command()
    async def emoji(self, ctx, emoji: str):
        """Set the emoji to listen for reactions."""
        await self.config.guild(ctx.guild).emoji.set(emoji)
        await ctx.send(f"Emoji set to {emoji}")

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        if user.bot:
            return

        message = reaction.message
        guild = message.guild
        channel_id = await self.config.guild(guild).channel_id()
        emoji = await self.config.guild(guild).emoji()

        if not channel_id or not emoji:
            return

        if str(reaction.emoji) != emoji:
            return

        channel = guild.get_channel(channel_id)
        if not channel:
            return

        async for msg in channel.history(limit=100):
            if msg.author == message.author:
                link = msg.jump_url
                try:
                    await user.send(f"Here is {message.author.mention}'s post in {channel.mention}: {link}")
                except discord.Forbidden:
                    pass
                break

        try:
            await reaction.remove(user)
        except discord.Forbidden:
            pass

def setup(bot):
    bot.add_cog(ReactionLinker(bot))
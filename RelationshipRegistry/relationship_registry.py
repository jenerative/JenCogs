import discord
from discord.ext import commands
from redbot.core import commands

class RelationshipRegistry(commands.Cog):
    def __init__(self, bot):
        super().__init__()
        self.bot = bot
        self.relationships = {}  # Dictionary to store relationships
        self.channel_id = None  # Channel ID for logging relationships

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def set_relationship_channel(self, ctx, channel_id: int):
        """Set the channel ID for logging relationships."""
        self.channel_id = channel_id
        await ctx.send(f"Relationship log channel ID set to {channel_id}.")

    @commands.command()
    async def set_relationship(self, ctx, user: discord.User, relationship_type: str):
        """Set a relationship with another user."""
        author_id = ctx.author.id
        user_id = user.id

        if author_id not in self.relationships:
            self.relationships[author_id] = {}

        if self.channel_id:
            channel = self.bot.get_channel(self.channel_id)
            log_message = await channel.send(f"{ctx.author.mention} has set a relationship with {user.mention} as {relationship_type}.")
            self.relationships[author_id][user_id] = {
                'relationship_type': relationship_type,
                'log_message_id': log_message.id
            }
        else:
            self.relationships[author_id][user_id] = {
                'relationship_type': relationship_type,
                'log_message_id': None
            }

        await ctx.send(f"Relationship with {user.mention} set as {relationship_type}.")

    @commands.command()
    async def remove_relationship(self, ctx, user: discord.User):
        """Remove a relationship with another user."""
        author_id = ctx.author.id
        user_id = user.id

        if author_id in self.relationships and user_id in self.relationships[author_id]:
            log_message_id = self.relationships[author_id][user_id]['log_message_id']
            if log_message_id and self.channel_id:
                channel = self.bot.get_channel(self.channel_id)
                try:
                    log_message = await channel.fetch_message(log_message_id)
                    await log_message.delete()
                except discord.NotFound:
                    pass

            del self.relationships[author_id][user_id]
            await ctx.send(f"Relationship with {user.mention} removed.")
        else:
            await ctx.send(f"No relationship found with {user.mention}.")

async def setup(bot):
    await bot.add_cog(RelationshipRegistry(bot))
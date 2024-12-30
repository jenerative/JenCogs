import discord
from discord.ext import commands, tasks
from redbot.core import commands
import datetime

class RelationshipRegistry(commands.Cog):
    def __init__(self, bot):
        super().__init__()
        self.bot = bot
        self.relationships = {}  # Dictionary to store relationships
        self.channel_id = None  # Channel ID for logging relationships
        self.user_leave_times = {}  # Dictionary to store user leave times
        self.check_inactive_users.start()  # Start the task to check for inactive users

    @commands.command(name="relationshipchannel")
    @commands.has_permissions(administrator=True)
    async def set_relationship_channel(self, ctx, channel_id: int):
        """Set the channel ID for logging relationships."""
        self.channel_id = channel_id
        await ctx.send(f"Relationship log channel ID set to {channel_id}.")

    @commands.command(name="relationshipset")
    async def relationship_set(self, ctx, user: discord.User, *, relationship_type: str):
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

    @commands.command(name="relationshipremove")
    async def relationship_remove(self, ctx, user: discord.User = None):
        """Remove a relationship with another user or all relationships."""
        author_id = ctx.author.id

        if user is None:
            await ctx.send("Please mention a user or use 'all' to remove all relationships.")
            return

        if user == "all":
            if author_id in self.relationships:
                for user_id, relationship in self.relationships[author_id].items():
                    log_message_id = relationship['log_message_id']
                    if log_message_id and self.channel_id:
                        channel = self.bot.get_channel(self.channel_id)
                        try:
                            log_message = await channel.fetch_message(log_message_id)
                            await log_message.delete()
                        except discord.NotFound:
                            pass
                del self.relationships[author_id]
                await ctx.send("All relationships removed.")
            else:
                await ctx.send("You have no relationships to remove.")
        else:
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
            elif user_id in self.relationships and author_id in self.relationships[user_id]:
                log_message_id = self.relationships[user_id][author_id]['log_message_id']
                if log_message_id and self.channel_id:
                    channel = self.bot.get_channel(self.channel_id)
                    try:
                        log_message = await channel.fetch_message(log_message_id)
                        await log_message.delete()
                    except discord.NotFound:
                        pass

                del self.relationships[user_id][author_id]
                await ctx.send(f"Relationship with {ctx.author.mention} removed.")
            else:
                await ctx.send(f"No relationship found with {user.mention}.")

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        """Track when a member leaves the guild."""
        self.user_leave_times[member.id] = datetime.datetime.now()

    @tasks.loop(hours=24)
    async def check_inactive_users(self):
        """Check for users who have been gone for more than one week and remove their relationships."""
        now = datetime.datetime.now()
        one_week_ago = now - datetime.timedelta(weeks=1)
        to_remove = [user_id for user_id, leave_time in self.user_leave_times.items() if leave_time < one_week_ago]

        for user_id in to_remove:
            if user_id in self.relationships:
                del self.relationships[user_id]
            del self.user_leave_times[user_id]

    @check_inactive_users.before_loop
    async def before_check_inactive_users(self):
        await self.bot.wait_until_ready()

async def setup(bot):
    await bot.add_cog(RelationshipRegistry(bot))
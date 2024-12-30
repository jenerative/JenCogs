import datetime
from discord.ext import commands, tasks
from redbot.core import commands

class ExposureCountdown(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.files = {}  # Dictionary to store file metadata
        self.channel_id = None  # Channel ID for posting expired files
        self.check_expiry.start()  # Start the task to check for expired files

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def set_channel(self, ctx, channel_id: int):
        """Set the channel ID for posting exposure files."""
        self.channel_id = channel_id
        await ctx.send(f"Channel ID set to {channel_id}.")

    @commands.command()
    async def upload_file(self, ctx, file):
        user_id = ctx.author.id
        # Logic to save the file and set privacy duration
        self.files[user_id] = {
            'file_path': file,
            'expiry': None  # Set initial expiry to None
        }
        await ctx.send("File uploaded successfully!")

    @commands.command()
    async def set_privacy_duration(self, ctx, duration: int):
        user_id = ctx.author.id
        if user_id in self.files:
            # Logic to set expiry based on duration
            self.files[user_id]['expiry'] = datetime.datetime.now() + datetime.timedelta(seconds=duration)
            await ctx.send(f"Countdown duration set to {duration}!")
        else:
            await ctx.send("You have not uploaded a file.")

    @commands.command()
    async def extend_privacy_duration(self, ctx, additional_time: int):
        user_id = ctx.author.id
        if user_id in self.files and self.files[user_id]['expiry']:
            # Logic to extend expiry
            self.files[user_id]['expiry'] += datetime.timedelta(seconds=additional_time)
            await ctx.send(f"Countdown duration extended by {additional_time} seconds!")
        else:
            await ctx.send("You have not uploaded a file or the expiry is not set.")

    @tasks.loop(minutes=1)
    async def check_expiry(self):
        current_time = datetime.datetime.now()
        for user_id, data in list(self.files.items()):
            if data['expiry'] and data['expiry'] <= current_time:
                if self.channel_id:
                    channel = self.bot.get_channel(self.channel_id)
                    await channel.send(f"File from user {user_id} is now public.")
                del self.files[user_id]  # Remove the file from the dictionary

    @check_expiry.before_loop
    async def before_check_expiry(self):
        await self.bot.wait_until_ready()

async def setup(bot):
    await bot.add_cog(ExposureCountdown(bot))
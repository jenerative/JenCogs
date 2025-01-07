from redbot.core import commands, Config, checks, bank
import discord
from datetime import datetime, timedelta
from discord.ext import tasks
import re

class MisoSoup(commands.Cog):
    """MisoSoup"""

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=1234567890, force_registration=True)
        default_guild = {
            "sir_role": None,
            "doll_role": None,
            "privileges": {
                "NameChanges": {
                    "cost": 200,
                    "role": None,
                    "duration": 600,  # Default duration in seconds (10 minutes)
                    "description": "Allows changing your nickname."
                },
                "Cursing": {
                    "cost": 100,
                    "role": None,
                    "duration": 86400,  # Default duration in seconds (24 hours)
                    "description": "Allows curse words."
                }
            },
            "emoji_only_mode": {}
        }
        self.config.register_guild(**default_guild)
        self._check_privileges.start()
        self._check_emoji_only_mode.start()

    def cog_unload(self):
        self._check_privileges.cancel()
        self._check_emoji_only_mode.cancel()

    @tasks.loop(minutes=10)
    async def _check_privileges(self):
        for guild in self.bot.guilds:
            async with self.config.guild(guild).privileges() as privileges:
                for privilege, data in privileges.items():
                    if "expires" in data:
                        for user_id, expire_time in list(data["expires"].items()):
                            if datetime.utcnow().timestamp() >= expire_time:
                                member = guild.get_member(int(user_id))
                                role = guild.get_role(data["role"])
                                if member and role:
                                    try:
                                        await member.remove_roles(role)
                                    except discord.Forbidden:
                                        pass
                                del data["expires"][user_id]

    @tasks.loop(minutes=1)
    async def _check_emoji_only_mode(self):
        for guild in self.bot.guilds:
            async with self.config.guild(guild).emoji_only_mode() as emoji_only_mode:
                for user_id, expire_time in list(emoji_only_mode.items()):
                    if datetime.utcnow().timestamp() >= expire_time:
                        del emoji_only_mode[user_id]

    @commands.group()
    @commands.has_permissions(administrator=True)
    async def misoroleset(self, ctx):
        """Settings for MisoSoup roles"""
        pass

    @misoroleset.command()
    async def sirs(self, ctx, role: discord.Role):
        """Set the role for 'sir' label."""
        await self.config.guild(ctx.guild).sir_role.set(role.id)
        await ctx.send(f"Role for 'sir' set to {role.name}")

    @misoroleset.command()
    async def dolls(self, ctx, role: discord.Role):
        """Set the role for 'doll' label."""
        await self.config.guild(ctx.guild).doll_role.set(role.id)
        await ctx.send(f"Role for 'doll' set to {role.name}")

    @commands.group()
    async def doll(self, ctx):
        """Commands for playing with the dolls."""
        pass

    @doll.command()
    async def name(self, ctx, member: discord.Member, *, nickname: str):
        """Change the name of a doll."""
        guild = ctx.guild
        sir_role_id = await self.config.guild(guild).sir_role()
        doll_role_id = await self.config.guild(guild).doll_role()

        if not sir_role_id or not doll_role_id:
            return await ctx.send("Roles for 'sir' and 'doll' have not been set.")

        sir_role = guild.get_role(sir_role_id)
        doll_role = guild.get_role(doll_role_id)

        if not sir_role or not doll_role:
            return await ctx.send("Roles for 'sir' and 'doll' are not valid.")

        if sir_role not in ctx.author.roles:
            return await ctx.send("You must be a Sir to use this command.")

        if doll_role not in member.roles:
            return await ctx.send("The specified member does not have the doll role.")

        try:
            await member.edit(nick=nickname)
            await ctx.send(f"Dollname for {member.mention} has been changed to {nickname}.")
        except discord.Forbidden:
            await ctx.send("I do not have permission to change the dollname of this member.")

    @doll.command()
    async def gag(self, ctx, member: discord.Member, minutes: int):
        """Set a user to emoji only mode for a specified time."""
        guild = ctx.guild
        sir_role = guild.get_role(await self.config.guild(guild).sir_role())
        doll_role = guild.get_role(await self.config.guild(guild).doll_role())

        if sir_role in ctx.author.roles:
            if doll_role in member.roles:
                async with self.config.guild(guild).emoji_only_mode() as emoji_only_mode:
                    emoji_only_mode[member.id] = datetime.utcnow().timestamp() + minutes * 60
                    await ctx.send(f"{member.mention} has been set to emoji only mode for {minutes} minutes.")
            else:
                await ctx.send(f"{member.mention} does not have the doll role.")
        else:
            await ctx.send("You do not have the required role to use this command.")

    @doll.command()
    async def ungag(self, ctx, member: discord.Member):
        """Remove emoji only mode from a user."""
        guild = ctx.guild
        sir_role = guild.get_role(await self.config.guild(guild).sir_role())

        if sir_role in ctx.author.roles:
            async with self.config.guild(guild).emoji_only_mode() as emoji_only_mode:
                if member.id in emoji_only_mode:
                    del emoji_only_mode[member.id]
                    await ctx.send(f"{member.mention} has been removed from emoji only mode.")
                else:
                    await ctx.send(f"{member.mention} is not in emoji only mode.")
        else:
            await ctx.send("You do not have the required role to use this command.")

    @doll.group(aliases=["privilege"])
    async def privileges(self, ctx):
        """Commands for managing privileges"""
        pass

    @privileges.command()
    @commands.has_permissions(administrator=True)
    async def setcost(self, ctx, privilege: str, cost: int):
        """Set the cost of a privilege."""
        async with self.config.guild(ctx.guild).privileges() as privileges:
            if privilege not in privileges:
                return await ctx.send(f"Privilege '{privilege}' does not exist.")
            privileges[privilege]["cost"] = cost
        await ctx.send(f"Cost for '{privilege}' set to {cost}.")

    @privileges.command()
    @commands.has_permissions(administrator=True)
    async def setrole(self, ctx, privilege: str, role: discord.Role):
        """Set the role for a privilege."""
        async with self.config.guild(ctx.guild).privileges() as privileges:
            if privilege not in privileges:
                return await ctx.send(f"Privilege '{privilege}' does not exist.")
            privileges[privilege]["role"] = role.id
        await ctx.send(f"Role for '{privilege}' set to {role.name}.")

    @privileges.command()
    @commands.has_permissions(administrator=True)
    async def setduration(self, ctx, privilege: str, duration: int):
        """Set the duration (in seconds) for a privilege."""
        async with self.config.guild(ctx.guild).privileges() as privileges:
            if privilege not in privileges:
                return await ctx.send(f"Privilege '{privilege}' does not exist.")
            privileges[privilege]["duration"] = duration
        await ctx.send(f"Duration for '{privilege}' set to {duration} seconds.")

    @privileges.command()
    async def buy(self, ctx, privilege: str):
        """~~Buy~~ Rent a privilege."""
        guild = ctx.guild
        doll_role_id = await self.config.guild(guild).doll_role()
        doll_role = guild.get_role(doll_role_id)

        if not doll_role:
            return await ctx.send("Role for 'doll' is not valid.")

        if doll_role not in ctx.author.roles:
            return await ctx.send("Only fuckdolls need to buy (rent) privileges.")

        async with self.config.guild(guild).privileges() as privileges:
            if privilege not in privileges:
                return await ctx.send(f"Privilege '{privilege}' does not exist.")
            cost = privileges[privilege]["cost"]
            role_id = privileges[privilege]["role"]
            duration = privileges[privilege]["duration"]

        if role_id is None:
            return await ctx.send(f"Role for '{privilege}' has not been set.")

        role = guild.get_role(role_id)
        if not role:
            return await ctx.send(f"Role for '{privilege}' is not valid.")

        balance = await bank.get_balance(ctx.author)
        if balance < cost:
            return await ctx.send(f"You do not have enough funds to buy '{privilege}'. Cost: {cost}")

        await bank.withdraw_credits(ctx.author, cost)
        await ctx.author.add_roles(role)
        expire_time = datetime.utcnow() + timedelta(seconds=duration)
        async with self.config.guild(guild).privileges() as privileges:
            if "expires" not in privileges[privilege]:
                privileges[privilege]["expires"] = {}
            privileges[privilege]["expires"][str(ctx.author.id)] = expire_time.timestamp()
        await ctx.send(f"You have successfully rented the '{privilege}' for {duration} seconds.")

    @privileges.command()
    async def list(self, ctx):
        """List all privileges with desc, cost, and duration."""
        guild = ctx.guild
        async with self.config.guild(guild).privileges() as privileges:
            if not privileges:
                return await ctx.send("There are no privileges set.")
            embed = discord.Embed(title="Privileges", color=discord.Color.blue())
            for privilege, data in privileges.items():
                role = guild.get_role(data["role"])
                role_mention = role.mention if role else "Not set"
                embed.add_field(
                    name=privilege,
                    value=(
                        f"**Description:** {data.get('description', 'No description')}\n"
                        f"**Cost:** {data['cost']}\n"
                        f"**Role:** {role_mention}\n"
                        f"**Duration:** {data['duration']} seconds\n"
                        f"---------------------------------"
                    ),
                    inline=False
                )
            await ctx.send(embed=embed)

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return

        guild = message.guild
        if guild:
            async with self.config.guild(guild).emoji_only_mode() as emoji_only_mode:
                if message.author.id in emoji_only_mode:
                    if not self.is_emoji_only(message.content):
                        try:
                            await message.delete()
                        except discord.Forbidden:
                            pass

    def is_emoji_only(self, content):
        custom_emoji_pattern = r'<a?:\w+:\d+>'
        unicode_emoji_pattern = r'[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F700-\U0001F77F\U0001F780-\U0001F7FF\U0001F800-\U0001F8FF\U0001F900-\U0001F9FF\U0001FA00-\U0001FA6F\U0001FA70-\U0001FAFF\U00002702-\U000027B0\U000024C2-\U0001F251]'
        combined_pattern = f'({custom_emoji_pattern}|{unicode_emoji_pattern})+'
        return bool(re.fullmatch(combined_pattern, content))

async def setup(bot):
    await bot.add_cog(MisoSoup(bot))
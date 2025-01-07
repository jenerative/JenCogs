from redbot.core import commands, Config, checks, bank
import discord
from datetime import datetime, timedelta
from discord.ext import tasks

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
                    "cost": 100,
                    "role": None,
                    "duration": 86400,  # Default duration in seconds (24 hours)
                    "description": "Allows changing your nickname."
                }
            }
        }
        self.config.register_guild(**default_guild)
        self._check_privileges.start()

    def cog_unload(self):
        self._check_privileges.cancel()

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
        """Commands for managing doll roles"""
        pass

    @doll.command()
    async def name(self, ctx, member: discord.Member, *, nickname: str):
        """Change the nickname of a member with the doll role."""
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
            return await ctx.send("You do not have the required role to use this command.")

        if doll_role not in member.roles:
            return await ctx.send("The specified member does not have the doll role.")

        try:
            await member.edit(nick=nickname)
            await ctx.send(f"Nickname for {member.mention} has been changed to {nickname}.")
        except discord.Forbidden:
            await ctx.send("I do not have permission to change the nickname of this member.")

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
        """Buy a privilege."""
        guild = ctx.guild
        doll_role_id = await self.config.guild(guild).doll_role()
        doll_role = guild.get_role(doll_role_id)

        if not doll_role:
            return await ctx.send("Role for 'doll' is not valid.")

        if doll_role not in ctx.author.roles:
            return await ctx.send("You do not have the required role to buy privileges.")

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
        await ctx.send(f"You have successfully bought the '{privilege}' privilege and have been assigned the {role.name} role for {duration} seconds.")

    @privileges.command()
    async def list(self, ctx):
        """List all privileges with their description, cost, and duration."""
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
            await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(MisoSoup(bot))
import discord
from discord.ext import commands, tasks
from redbot.core import commands, Config
import datetime

class NameChanger(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=1234567890)
        default_guild = {
            "allowed_role_name": "Nickname Changer",
            "locked_nicknames": {}
        }
        self.config.register_guild(**default_guild)
        self.check_locked_nicknames.start()

    async def has_allowed_role(ctx):
        role_name = await ctx.cog.config.guild(ctx.guild).allowed_role_name()
        role = discord.utils.find(lambda r: r.name == role_name, ctx.author.roles)
        return role is not None

    @commands.command(name="namechangerrole")
    @commands.has_permissions(administrator=True)
    async def set_nickname_changer_role(self, ctx, *, role_name: str):
        """Set the role name that can change nicknames."""
        await self.config.guild(ctx.guild).allowed_role_name.set(role_name)
        await ctx.send(f"Role name for changing nicknames set to {role_name}.")

    @commands.command(name="dollname")
    @commands.check(has_allowed_role)
    async def change_nick(self, ctx, member: discord.Member, new_nickname: str, duration: int = None):
        """Change the nickname of a member and optionally lock it for a duration (up to 48 hours)."""
        old_nickname = member.display_name
        await member.edit(nick=new_nickname)
        await ctx.send(f"Renamed {old_nickname} to {new_nickname}.")

        if duration is not None:
            if duration > 48 * 60:
                await ctx.send("Duration cannot be more than 48 hours.")
                return

            end_time = datetime.datetime.now() + datetime.timedelta(minutes=duration)
            async with self.config.guild(ctx.guild).locked_nicknames() as locked_nicknames:
                locked_nicknames[str(member.id)] = {
                    "nickname": new_nickname,
                    "end_time": end_time.timestamp()
                }
            await ctx.send(f"Nickname locked for {duration} minutes.")

    @commands.command(name="dollnamereset")
    @commands.check(has_allowed_role)
    async def reset_nick(self, ctx, member: discord.Member):
        """Reset the nickname of a member."""
        old_nickname = member.display_name
        await member.edit(nick=None)
        await ctx.send(f"Reset nickname for {old_nickname}.")

        async with self.config.guild(ctx.guild).locked_nicknames() as locked_nicknames:
            if str(member.id) in locked_nicknames:
                del locked_nicknames[str(member.id)]

    @tasks.loop(minutes=1)
    async def check_locked_nicknames(self):
        """Check and unlock nicknames if the duration has expired."""
        now = datetime.datetime.now().timestamp()
        async with self.config.all_guilds() as all_guilds:
            for guild_id, guild_data in all_guilds.items():
                locked_nicknames = guild_data.get("locked_nicknames", {})
                for member_id, data in list(locked_nicknames.items()):
                    if data["end_time"] <= now:
                        guild = self.bot.get_guild(int(guild_id))
                        if guild:
                            member = guild.get_member(int(member_id))
                            if member:
                                await member.edit(nick=None)
                        del locked_nicknames[member_id]

    @check_locked_nicknames.before_loop
    async def before_check_locked_nicknames(self):
        await self.bot.wait_until_ready()

async def setup(bot):
    await bot.add_cog(NameChanger(bot))
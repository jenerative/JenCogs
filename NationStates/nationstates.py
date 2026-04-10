import aiohttp
import asyncio
import time
import xml.etree.ElementTree as ET
import discord # type: ignore
from redbot.core import commands, Config, checks
from discord.ext import tasks # type: ignore

NS_API = "https://www.nationstates.net/cgi-bin/api.cgi"

class NationStatesIssues(commands.Cog):
    """Integrate NationStates issues and community voting into Discord."""

    def __init__(self, bot):
        self.bot = bot
        # Register the configuration schema
        self.config = Config.get_conf(self, identifier=8234892348, force_registration=True)
        self.config.register_guild(
            channel_id=None,
            nation_name=None,
            password=None, 
            user_agent="Red-DiscordBot JenCogs/NationStates",
            poll_duration_hours=24,
            handled_issues=[],
            active_polls={} # Structure: {"issue_id": {"channel_id": int, "message_id": int, "end_time": float}}
        )
        self.session = aiohttp.ClientSession()
        
        # Start the background tasks
        self.check_issues.start()
        self.check_active_polls.start()

    def cog_unload(self):
        self.check_issues.cancel()
        self.check_active_polls.cancel()
        asyncio.create_task(self.session.close())

    # --- Configuration Commands ---

    @commands.group()
    @checks.admin_or_permissions(manage_guild=True)
    async def nssys(self, ctx):
        """Configure the NationStates Integration."""
        pass

    @nssys.command()
    async def setchannel(self, ctx, channel: discord.TextChannel):
        """Set the channel where new issues will be posted."""
        await self.config.guild(ctx.guild).channel_id.set(channel.id)
        await ctx.send(f"New issues will now be posted as threads in {channel.mention}.")

    @nssys.command()
    async def setnation(self, ctx, nation_name: str, password: str):
        """Set your Nation name and password. (Run this in a private channel)"""
        await self.config.guild(ctx.guild).nation_name.set(nation_name.replace(" ", "_"))
        await self.config.guild(ctx.guild).password.set(password)
        try:
            await ctx.message.delete()
        except discord.Forbidden:
            pass
        await ctx.send("Nation and password set! (I've attempted to delete your message to hide the password).")

    @nssys.command()
    async def setagent(self, ctx, *, user_agent: str):
        """Set the API User-Agent. NS requires this to include your contact info."""
        await self.config.guild(ctx.guild).user_agent.set(user_agent)
        await ctx.send(f"User-Agent updated to: `{user_agent}`")

    @nssys.command()
    async def setduration(self, ctx, hours: int):
        """Set the number of hours polls should remain open."""
        if hours < 1:
            return await ctx.send("Duration must be at least 1 hour.")
        await self.config.guild(ctx.guild).poll_duration_hours.set(hours)
        await ctx.send(f"Polls will now last for {hours} hour(s).")

    @nssys.command()
    async def info(self, ctx):
        """View the current configuration."""
        data = await self.config.guild(ctx.guild).all()
        channel = ctx.guild.get_channel(data["channel_id"]) if data["channel_id"] else None
        
        embed = discord.Embed(title="NationStates Config", color=discord.Color.blue())
        embed.add_field(name="Target Channel", value=channel.mention if channel else "Not set", inline=False)
        embed.add_field(name="Nation Name", value=data["nation_name"] or "Not set", inline=True)
        embed.add_field(name="Poll Duration", value=f"{data['poll_duration_hours']} hour(s)", inline=True)
        embed.add_field(name="User-Agent", value=f"`{data['user_agent']}`", inline=False)
        embed.add_field(name="Active Polls", value=str(len(data["active_polls"])), inline=True)
        await ctx.send(embed=embed)


    # --- Background Tasks & Logic ---

    @tasks.loop(hours=1)
    async def check_issues(self):
        """Hourly loop to fetch new issues from the API."""
        for guild_id, data in (await self.config.all_guilds()).items():
            guild = self.bot.get_guild(guild_id)
            if not guild or not data.get("channel_id"): continue

            channel = guild.get_channel(data["channel_id"])
            if not channel: continue

            issues_xml = await self.fetch_api(guild, {"q": "issues"})
            if issues_xml is None: continue

            handled_issues = await self.config.guild(guild).handled_issues()
            
            for issue in issues_xml.findall(".//ISSUE"):
                issue_id = issue.get("id")
                if issue_id in handled_issues:
                    continue
                
                handled_issues.append(issue_id)
                await self.config.guild(guild).handled_issues.set(handled_issues)
                
                # Create the thread and poll
                self.bot.loop.create_task(self.create_poll(guild, channel, issue))

    @tasks.loop(minutes=5)
    async def check_active_polls(self):
        """Frequent loop to check if any active polls have expired across reboots."""
        for guild_id, data in (await self.config.all_guilds()).items():
            guild = self.bot.get_guild(guild_id)
            if not guild: continue

            active_polls = data.get("active_polls", {})
            if not active_polls: continue

            now = time.time()
            to_remove = []

            for issue_id, poll_data in active_polls.items():
                if now >= poll_data["end_time"]:
                    # Tally votes and submit to API
                    await self.tally_and_submit(guild, issue_id, poll_data)
                    to_remove.append(issue_id)

            # Clean up resolved polls from Config
            if to_remove:
                async with self.config.guild(guild).active_polls() as active:
                    for i_id in to_remove:
                        if i_id in active:
                            del active[i_id]

    @check_issues.before_loop
    @check_active_polls.before_loop
    async def before_loops(self):
        await self.bot.wait_until_red_ready()


    # --- API and Execution Helpers ---

    async def fetch_api(self, guild, params: dict):
        """Helper to safely make authorized NationStates API calls."""
        nation = await self.config.guild(guild).nation_name()
        password = await self.config.guild(guild).password()
        user_agent = await self.config.guild(guild).user_agent()

        if not nation or not password: return None

        headers = {"User-Agent": user_agent, "X-Password": password}
        params["nation"] = nation

        async with self.session.get(NS_API, params=params, headers=headers) as resp:
            if resp.status == 200:
                text = await resp.text()
                return ET.fromstring(text)
            return None

    async def create_poll(self, guild, channel, issue):
        """Creates the thread and registers the poll in Config."""
        issue_id = issue.get("id")
        title = issue.find("TITLE").text
        text_desc = issue.find("TEXT").text
        options = issue.findall("OPTION")

        # 1. Base message and thread
        embed = discord.Embed(title=f"Issue #{issue_id}: {title}", description=text_desc[:4000], color=discord.Color.green())
        msg = await channel.send(embed=embed)
        
        thread_name = f"Issue {issue_id}: {title}"[:100]
        thread = await msg.create_thread(name=thread_name, auto_archive_duration=1440)

        # 2. Setup poll
        number_emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣"]
        poll_msg = await thread.send("**Vote for your preferred action by reacting below!**")
        
        for idx, option in enumerate(options):
            if idx < len(number_emojis):
                await thread.send(f"{number_emojis[idx]} **Option {idx+1}:**\n> {option.text}")
                await poll_msg.add_reaction(number_emojis[idx])

        # 3. Calculate end time and save to Config
        duration_hours = await self.config.guild(guild).poll_duration_hours()
        end_time = time.time() + (duration_hours * 3600)

        async with self.config.guild(guild).active_polls() as active_polls:
            active_polls[issue_id] = {
                "channel_id": thread.id, 
                "message_id": poll_msg.id,
                "end_time": end_time
            }
        
        await thread.send(f"*Voting will conclude <t:{int(end_time)}:R>.*")

    async def tally_and_submit(self, guild, issue_id, poll_data):
        """Counts reactions, submits to NS, and posts the detailed results."""
        try:
            thread = guild.get_channel(poll_data["channel_id"]) or await guild.fetch_channel(poll_data["channel_id"])
            poll_msg = await thread.fetch_message(poll_data["message_id"])
        except (discord.NotFound, discord.Forbidden):
            return # Channel or message was deleted

        # Map the vote back to an API ID
        issues_xml = await self.fetch_api(guild, {"q": "issues"})
        if issues_xml is None: return
        
        target_issue = None
        for issue in issues_xml.findall(".//ISSUE"):
            if issue.get("id") == str(issue_id):
                target_issue = issue
                break
                
        if target_issue is None:
            await thread.send("This issue is no longer available on NationStates (it may have expired).")
            return

        options = target_issue.findall("OPTION")
        number_emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣"]
        best_reaction, max_votes = None, -1

        for reaction in poll_msg.reactions:
            if str(reaction.emoji) in number_emojis and reaction.me:
                votes = reaction.count - 1 # Ignore bot's own reaction
                if votes > max_votes:
                    max_votes = votes
                    best_reaction = str(reaction.emoji)

        selected_index = number_emojis.index(best_reaction) if best_reaction in number_emojis else 0
        if selected_index >= len(options): selected_index = 0

        chosen_option_id = options[selected_index].get("id")

        # Submit answer to API
        params = {"c": "issue", "issue": issue_id, "option": chosen_option_id}
        result_tree = await self.fetch_api(guild, params)

        if result_tree is not None:
            # The result is wrapped in an <ISSUE> tag, which is usually inside <NATION>
            issue_result = result_tree.find(".//ISSUE")
            if issue_result is None:
                issue_result = result_tree # Fallback if it's the root

            # 1. Paragraph / Description
            desc_element = issue_result.find(".//DESC")
            result_text = desc_element.text if desc_element is not None else "Issue resolved."
            
            result_embed = discord.Embed(
                title=f"Voting Concluded: Option {selected_index+1} Selected", 
                description=f"**With {max_votes} votes, the government has acted!**\n\n*The Results:*\n{result_text[:4000]}",
                color=discord.Color.gold()
            )

            # 2. Reclassifications (Civil Rights, Economy, Political Freedoms)
            reclassifications = []
            for reclass in issue_result.findall(".//RECLASSIFICATION"):
                r_type = reclass.get("type", "Classification").title()
                reclassifications.append(f"**{r_type}:** {reclass.text}")
            if reclassifications:
                result_embed.add_field(name="Classifications Changed", value="\n".join(reclassifications), inline=False)

            # 3. Policies Enacted & Abolished
            new_policies = [p.text for p in issue_result.findall(".//NEWPOLICIES/POLICY")]
            if new_policies:
                result_embed.add_field(name="Policies Enacted", value="\n".join(f"🟢 {p}" for p in new_policies), inline=True)
                
            removed_policies = [p.text for p in issue_result.findall(".//REMOVEDPOLICIES/POLICY")]
            if removed_policies:
                result_embed.add_field(name="Policies Abolished", value="\n".join(f"🔴 {p}" for p in removed_policies), inline=True)

            # 4. National Headings
            headings = [h.text for h in issue_result.findall(".//HEADINGS/HEADING")]
            if headings:
                result_embed.add_field(name="National Headings", value="\n".join(f"📰 {h}" for h in headings), inline=False)

            # 5. Unlocks (Pictures, Banners, Easter Eggs)
            unlocks = [u.text for u in issue_result.findall(".//UNLOCKS/UNLOCK")]
            if unlocks:
                result_embed.add_field(name="New Unlocks", value="\n".join(f"🎉 {u}" for u in unlocks), inline=False)

            # 6. Statistical Attributes Changed
            rankings = issue_result.findall(".//RANKINGS/RANK")
            if rankings:
                positive = 0
                negative = 0
                for r in rankings:
                    pchange_elem = r.find("PCHANGE")
                    if pchange_elem is not None and pchange_elem.text:
                        try:
                            change = float(pchange_elem.text)
                            if change > 0: positive += 1
                            elif change < 0: negative += 1
                        except ValueError:
                            pass
                
                if positive > 0 or negative > 0:
                    result_embed.add_field(
                        name="Statistical Attributes Changed", 
                        value=f"📈 {positive} national metrics increased.\n📉 {negative} national metrics decreased.", 
                        inline=False
                    )

            await thread.send(embed=result_embed)
        else:
            await thread.send("Failed to submit the final decision to NationStates (API Error).")
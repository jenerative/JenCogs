import aiohttp
import asyncio
import time
import datetime
import random
import xml.etree.ElementTree as ET
import discord # type: ignore
from redbot.core import commands, Config, checks
from discord.ext import tasks # type: ignore

NS_API = "https://www.nationstates.net/cgi-bin/api.cgi"

def clean_ns_text(text: str) -> str:
    """Helper to convert NationStates HTML formatting to Discord Markdown."""
    if not text: return ""
    return text.replace("<i>", "*").replace("</i>", "*").replace("<b>", "**").replace("</b>", "**")

class NationStatesIssues(commands.Cog):
    """Integrate NationStates issues and community voting into Discord using Native Polls."""

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
        """Set the number of hours polls should remain open (Max 768)."""
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
        
        active_polls = list(data["active_polls"].keys())
        active_str = ", ".join(f"#{i}" for i in active_polls) if active_polls else "None"
        embed.add_field(name="Active Polls", value=active_str, inline=False)
        
        await ctx.send(embed=embed)

    @nssys.command()
    async def forcecheck(self, ctx):
        """Manually force the bot to check for new issues immediately."""
        data = await self.config.guild(ctx.guild).all()
        channel_id = data.get("channel_id")
        
        if not channel_id:
            return await ctx.send("Please set a channel first using `[p]nssys setchannel`.")
            
        channel = ctx.guild.get_channel(channel_id)
        if not channel:
            return await ctx.send("The configured channel could not be found.")

        await ctx.send("Checking NationStates API for new issues...")
        
        async with ctx.typing():
            issues_xml = await self.fetch_api(ctx.guild, {"q": "issues"})
            if issues_xml is None:
                return await ctx.send("Failed to fetch issues. Check your nation name, password, and user-agent.")

            handled_issues = data.get("handled_issues", [])
            found_new = False
            
            for issue in issues_xml.findall(".//ISSUE"):
                issue_id = issue.get("id")
                if issue_id in handled_issues:
                    continue
                
                found_new = True
                handled_issues.append(issue_id)
                await self.config.guild(ctx.guild).handled_issues.set(handled_issues)
                
                self.bot.loop.create_task(self.create_poll(ctx.guild, channel, issue))
                
            if found_new:
                await ctx.send("Found and posted new issues!")
            else:
                await ctx.send("No new issues found at this time.")

    @nssys.command()
    async def clearpolls(self, ctx):
        """Cancel all active polls and wipe them from the bot's memory without submitting."""
        active = await self.config.guild(ctx.guild).active_polls()
        
        if not active:
            return await ctx.send("There are no active polls to clear.")

        for issue_id, poll_data in active.items():
            thread = ctx.guild.get_channel(poll_data["channel_id"])
            if thread:
                try:
                    await thread.send("⚠️ *This poll has been forcefully cancelled by a server administrator and will not be submitted to NationStates.*")
                except discord.Forbidden:
                    pass

        await self.config.guild(ctx.guild).active_polls.clear()
        await ctx.send(f"Successfully cancelled and cleared {len(active)} active poll(s).")

    @nssys.command()
    async def endpoll(self, ctx, issue_id: str):
        """End an active poll early, tally the current votes, and submit to NationStates."""
        async with self.config.guild(ctx.guild).active_polls() as active:
            if issue_id not in active:
                return await ctx.send(f"Issue #{issue_id} is not currently an active poll.")

            poll_data = active[issue_id]
            await ctx.send(f"Ending the poll for Issue #{issue_id} early and tallying votes...")
            
            # Fire the tally and submit logic
            await self.tally_and_submit(ctx.guild, issue_id, poll_data)
            
            # Remove from active polls so it isn't processed again
            del active[issue_id]
            
            await ctx.send(f"Successfully finalized and submitted Issue #{issue_id}.")


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
                    await self.tally_and_submit(guild, issue_id, poll_data)
                    to_remove.append(issue_id)

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
        """Creates the thread and uses Discord's native poll feature."""
        issue_id = issue.get("id")
        title = clean_ns_text(issue.find("TITLE").text)
        text_desc = clean_ns_text(issue.find("TEXT").text)
        options = issue.findall("OPTION")

        # 1. Base message and thread
        embed = discord.Embed(title=f"Issue #{issue_id}: {title}", description=text_desc[:4000], color=discord.Color.green())
        msg = await channel.send(embed=embed)
        
        thread_name = f"Issue {issue_id}: {title}"[:100]
        thread = await msg.create_thread(name=thread_name, auto_archive_duration=1440)

        # 2. Setup options text (Bypassing 55 char limit of native polls)
        number_emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣"]
        for idx, option in enumerate(options):
            if idx < len(number_emojis):
                option_text = clean_ns_text(option.text)
                await thread.send(f"{number_emojis[idx]} **Option {idx+1}:**\n> {option_text}")

        # 3. Create and send the Native Poll
        duration_hours = await self.config.guild(guild).poll_duration_hours()
        
        poll = discord.Poll(
            question="Which action should the government take?",
            duration=datetime.timedelta(hours=duration_hours),
            multiple=False
        )

        for idx in range(min(len(options), len(number_emojis))):
            poll.add_answer(text=f"Option {idx+1}", emoji=number_emojis[idx])

        poll_msg = await thread.send(poll=poll)

        # 4. Calculate end time and save to Config
        end_time = time.time() + (duration_hours * 3600)
        async with self.config.guild(guild).active_polls() as active_polls:
            active_polls[issue_id] = {
                "channel_id": thread.id, 
                "message_id": poll_msg.id,
                "end_time": end_time
            }

    async def tally_and_submit(self, guild, issue_id, poll_data):
        """Reads the native poll answers, handles ties, submits to NS, and posts results."""
        try:
            thread = guild.get_channel(poll_data["channel_id"]) or await guild.fetch_channel(poll_data["channel_id"])
            poll_msg = await thread.fetch_message(poll_data["message_id"])
        except (discord.NotFound, discord.Forbidden):
            return 

        # If poll hasn't naturally expired in UI yet, force it to end
        if poll_msg.poll and not poll_msg.poll.is_finished():
            try:
                await poll_msg.end_poll()
            except Exception:
                pass

        # Parse Native Poll Votes with Random Tie-Breaker
        if not poll_msg.poll:
            await thread.send("Could not retrieve poll data for this issue.")
            return

        best_indices = []
        max_votes = -1

        for idx, answer in enumerate(poll_msg.poll.answers):
            if answer.vote_count > max_votes:
                max_votes = answer.vote_count
                best_indices = [idx]
            elif answer.vote_count == max_votes:
                best_indices.append(idx)

        # Randomly select a winner if there is a tie
        best_index = random.choice(best_indices)
        
        tie_message = ""
        if len(best_indices) > 1:
            tie_message = f"\n*A tie between {len(best_indices)} options was resolved randomly.*"

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
        if best_index >= len(options): best_index = 0
        chosen_option_id = options[best_index].get("id")

        # Submit answer to API
        params = {"c": "issue", "issue": issue_id, "option": chosen_option_id}
        result_tree = await self.fetch_api(guild, params)

        if result_tree is not None:
            issue_result = result_tree.find(".//ISSUE")
            if issue_result is None:
                issue_result = result_tree 

            desc_element = issue_result.find(".//DESC")
            result_text = clean_ns_text(desc_element.text) if desc_element is not None else "Issue resolved."
            
            result_embed = discord.Embed(
                title=f"Voting Concluded: Option {best_index+1} Selected", 
                description=f"**With {max_votes} votes, the government has acted!**{tie_message}\n\n*The Results:*\n{result_text[:4000]}",
                color=discord.Color.gold()
            )

            # Reclassifications
            reclassifications = []
            for reclass in issue_result.findall(".//RECLASSIFICATION"):
                r_type = reclass.get("type", "Classification").title()
                reclassifications.append(f"**{r_type}:** {reclass.text}")
            if reclassifications:
                result_embed.add_field(name="Classifications Changed", value="\n".join(reclassifications), inline=False)

            # Policies
            new_policies = [p.text for p in issue_result.findall(".//NEWPOLICIES/POLICY")]
            if new_policies:
                result_embed.add_field(name="Policies Enacted", value="\n".join(f"🟢 {p}" for p in new_policies), inline=True)
                
            removed_policies = [p.text for p in issue_result.findall(".//REMOVEDPOLICIES/POLICY")]
            if removed_policies:
                result_embed.add_field(name="Policies Abolished", value="\n".join(f"🔴 {p}" for p in removed_policies), inline=True)

            # Headings
            headings = [h.text for h in issue_result.findall(".//HEADINGS/HEADING")]
            if headings:
                result_embed.add_field(name="National Headings", value="\n".join(f"📰 {h}" for h in headings), inline=False)

            # Unlocks
            unlocks = [u.text for u in issue_result.findall(".//UNLOCKS/UNLOCK")]
            if unlocks:
                result_embed.add_field(name="New Unlocks", value="\n".join(f"🎉 {u}" for u in unlocks), inline=False)

            # Stats
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
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

# Hardcoded dictionary for instant, API-free translation of all NationStates statistics.
# Includes all current census scales up to the 140s.
CENSUS_SCALES = {
    "0": "Civil Rights", "1": "Economy", "2": "Political Freedoms", "3": "Population",
    "4": "Wealth Gaps", "5": "Death Rate", "6": "Compassion", "7": "Eco-Friendliness",
    "8": "Social Conservatism", "9": "Nudity", "10": "Industry: Automobile Manufacturing",
    "11": "Industry: Cheese Exports", "12": "Industry: Basket Weaving", 
    "13": "Industry: Information Technology", "14": "Industry: Pizza Delivery", 
    "15": "Industry: Trout Fishing", "16": "Industry: Arms Manufacturing", 
    "17": "Sector: Agriculture", "18": "Cheerfulness", "19": "Weather", 
    "20": "Compliance", "21": "Safety", "22": "Lifespan", "23": "Ideological Radicality", 
    "24": "Defense Forces", "25": "Pacifism", "26": "Economic Freedom", "27": "Taxation", 
    "28": "Freedom from Taxation", "29": "Corruption", "30": "Integrity", 
    "31": "Authoritarianism", "32": "Rebelliousness", "33": "Employment", 
    "34": "Public Healthcare", "35": "Law Enforcement", "36": "Business Subsidization",
    "37": "Religiousness", "38": "Income Equality", "39": "Niceness", "40": "Rudeness",
    "41": "Intelligence", "42": "Ignorance", "43": "Toxicity", "44": "Averageness",
    "45": "Human Development Index", "46": "Primitiveness", "47": "Scientific Advancement", 
    "48": "Lifespan", "49": "Sector: Manufacturing", "50": "Sector: Services", 
    "51": "Sector: Government", "52": "Public Education", "53": "Economic Output", 
    "54": "Crime", "55": "Foreign Aid", "56": "Black Market", "57": "Quality of Life", 
    "58": "Weaponization", "59": "Recreational Drug Use", "60": "Obesity", 
    "61": "Secularism", "62": "Environmental Beauty", "63": "Charmlessness", "64": "Influence",
    "65": "World Assembly Endorsements", "66": "Tourism", "67": "Public Transport", 
    "68": "Industry: Book Publishing", "69": "Industry: Gambling", "70": "Industry: Insurance", 
    "71": "Industry: Mining", "72": "Industry: Retail", "73": "Industry: Timber Woodchipping", 
    "74": "Industry: Furniture Restoration", "75": "Industry: Beverage Sales", 
    "76": "Industry: Space Program", "77": "Industry: Consumer Electronics", 
    "78": "Industry: Bodyguard Manufacture", "79": "Industry: Beef-Based Agriculture",
    "80": "Culture", "81": "Art Funding", "82": "Sector: Agriculture", "83": "Sector: Manufacturing", 
    "84": "Sector: Services", "85": "Belief", "86": "Safety", "87": "Toxicity", 
    "88": "Average Income", "89": "Economic Freedom", "90": "Taxation", "91": "Freedom from Taxation", 
    "92": "Employment", "93": "Business Subsidization", "94": "Income Equality", 
    "95": "Economic Output", "96": "Primitiveness", "97": "Scientific Advancement", 
    "98": "Civil Rights", "99": "Political Freedoms", "100": "Corruption", "101": "Integrity", 
    "102": "Authoritarianism", "103": "Rebelliousness", "104": "Law Enforcement",
    "105": "Human Development Index", "106": "Compassion", "107": "Public Healthcare", 
    "108": "Life Expectancy", "109": "Quality of Life", "110": "Foreign Aid", 
    "111": "World Assembly Endorsements", "112": "Population", "113": "Safety", "114": "Nudity",
    "115": "Tourism", "116": "Weaponization", "117": "Black Market", "118": "Influence", 
    "119": "Ideological Radicality", "120": "Defense Forces", "121": "Pacifism", "122": "Militarism", 
    "123": "Liberty", "124": "Happiness", "125": "Eco-Friendliness", "126": "Environmental Beauty", 
    "127": "Obesity", "128": "Secularism", "129": "Wealth Gaps", "130": "Cheerfulness", 
    "131": "Public Education", "132": "Public Transport", "133": "Social Conservatism", 
    "134": "Death Rate", "135": "Charmlessness", "136": "Recreational Drug Use", 
    "137": "Religiousness", "138": "Niceness", "139": "Rudeness", "140": "Intelligence", 
    "141": "Ignorance", "142": "Averageness", "143": "Weather", "144": "Compliance", "145": "Toxicity"
}

def clean_ns_text(text: str) -> str:
    """Helper to convert NationStates HTML formatting to Discord Markdown."""
    if not text: return ""
    return text.replace("<i>", "*").replace("</i>", "*").replace("<b>", "**").replace("</b>", "**")

class NationStatesIssues(commands.Cog):
    """Integrate NationStates issues and community voting into Discord using Native Polls."""

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=8234892348, force_registration=True)
        self.config.register_guild(
            channel_id=None,
            nation_name=None,
            password=None, 
            pin=None,
            user_agent="Red-DiscordBot JenCogs/NationStates",
            poll_duration_hours=24,
            handled_issues=[],
            ping_role_id=None,
            active_polls={} 
        )
        self.session = aiohttp.ClientSession()
        
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
    async def setrole(self, ctx, role: discord.Role = None):
        """Set a role to ping when a new issue opens. Leave blank to disable."""
        if role is None:
            await self.config.guild(ctx.guild).ping_role_id.set(None)
            await ctx.send("Issue ping role has been disabled.")
        else:
            await self.config.guild(ctx.guild).ping_role_id.set(role.id)
            await ctx.send(f"Will now ping **{role.name}** when new issues are posted.")

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
        
        role_id = data.get("ping_role_id")
        role_str = f"<@&{role_id}>" if role_id else "None"
        embed.add_field(name="Ping Role", value=role_str, inline=True)
        
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
            issues_xml, err_msg = await self.fetch_api(ctx.guild, {"q": "issues"})
            if issues_xml is None:
                return await ctx.send(f"**Failed to fetch issues.**\nReason: `{err_msg}`")

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

        handled = await self.config.guild(ctx.guild).handled_issues()
        new_handled = [issue_id for issue_id in handled if issue_id not in active]
        await self.config.guild(ctx.guild).handled_issues.set(new_handled)

        for issue_id, poll_data in active.items():
            thread = ctx.guild.get_channel(poll_data["channel_id"])
            if thread:
                try:
                    await thread.send("⚠️ *This poll has been forcefully cancelled by a server administrator and will not be submitted to NationStates.*")
                except discord.Forbidden:
                    pass

        await self.config.guild(ctx.guild).active_polls.clear()
        await ctx.send(f"Successfully cancelled and cleared {len(active)} active poll(s). You can now run `[p]nssys forcecheck` to re-pull them.")

    @nssys.command()
    async def endpoll(self, ctx, issue_id: str):
        """End an active poll early, tally the current votes, and submit to NationStates."""
        async with self.config.guild(ctx.guild).active_polls() as active:
            if issue_id not in active:
                return await ctx.send(f"Issue #{issue_id} is not currently an active poll.")

            poll_data = active[issue_id]
            await ctx.send(f"Ending the poll for Issue #{issue_id} early and tallying votes...")
            
            success = await self.tally_and_submit(ctx.guild, issue_id, poll_data, ctx)
            
            if success:
                del active[issue_id]
                await ctx.send(f"✅ Successfully finalized and submitted Issue #{issue_id}.")
            else:
                await ctx.send(f"❌ Failed to process Issue #{issue_id}. The poll remains active in memory. See error messages above.")


    # --- Background Tasks & Logic ---

    @tasks.loop(hours=1)
    async def check_issues(self):
        """Hourly loop to fetch new issues from the API."""
        for guild_id, data in (await self.config.all_guilds()).items():
            guild = self.bot.get_guild(guild_id)
            if not guild or not data.get("channel_id"): continue

            channel = guild.get_channel(data["channel_id"])
            if not channel: continue

            issues_xml, err_msg = await self.fetch_api(guild, {"q": "issues"})
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
                    success = await self.tally_and_submit(guild, issue_id, poll_data)
                    if success:
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

    async def fetch_api(self, guild, params: dict, is_retry=False):
        """
        Helper to safely make authorized NationStates API calls using X-Pin caching.
        Returns a tuple: (XML_Tree, Error_Message_String)
        """
        nation = await self.config.guild(guild).nation_name()
        password = await self.config.guild(guild).password()
        pin = await self.config.guild(guild).pin()
        user_agent = await self.config.guild(guild).user_agent()

        if not nation or not password: 
            return None, "Nation name or password not configured."

        headers = {"User-Agent": user_agent}
        
        if pin:
            headers["X-Pin"] = pin
        else:
            headers["X-Password"] = password

        params["nation"] = nation

        async with self.session.get(NS_API, params=params, headers=headers) as resp:
            new_pin = resp.headers.get("X-Pin")
            if new_pin and new_pin != pin:
                await self.config.guild(guild).pin.set(new_pin)

            text = await resp.text()
            
            if resp.status == 200:
                try:
                    return ET.fromstring(text), None
                except ET.ParseError:
                    return None, "NationStates returned invalid XML."
            else:
                if resp.status in (409, 403) and pin and not is_retry:
                    await self.config.guild(guild).pin.set(None)
                    await asyncio.sleep(2) 
                    return await self.fetch_api(guild, params, is_retry=True)

                clean_err = text.strip()[:200].replace('\n', ' ')
                
                if resp.status == 429:
                    return None, f"HTTP 429 Rate Limited. Too many requests to NationStates."
                elif resp.status == 409:
                    return None, f"HTTP 409 Conflict. (NS says: {clean_err})"
                elif resp.status == 403:
                    return None, f"HTTP 403 Forbidden. Is the password correct? (NS says: {clean_err})"
                elif resp.status == 400:
                    return None, f"HTTP 400 Bad Request. (NS says: {clean_err})"
                elif resp.status == 404:
                    return None, f"HTTP 404 Not Found. Unknown nation? (NS says: {clean_err})"
                else:
                    return None, f"HTTP {resp.status} Error: {clean_err}"

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

        # 4. Announce and Ping Role if configured (WITH ALLOWED MENTIONS OVERRIDE)
        role_id = await self.config.guild(guild).ping_role_id()
        if role_id:
            role = guild.get_role(role_id)
            if role:
                await thread.send(
                    f"{role.mention} A new issue is available for voting!", 
                    allowed_mentions=discord.AllowedMentions(roles=[role])
                )

        # 5. Calculate end time and save to Config
        end_time = time.time() + (duration_hours * 3600)
        async with self.config.guild(guild).active_polls() as active_polls:
            active_polls[issue_id] = {
                "channel_id": thread.id, 
                "message_id": poll_msg.id,
                "end_time": end_time
            }

    async def tally_and_submit(self, guild, issue_id, poll_data, ctx=None):
        """Reads the native poll answers, handles ties, submits to NS, and posts results."""
        notification_dest = ctx or guild.get_thread(poll_data["channel_id"]) or guild.get_channel(poll_data["channel_id"])

        try:
            thread = guild.get_thread(poll_data["channel_id"]) or await guild.fetch_channel(poll_data["channel_id"])
            poll_msg = await thread.fetch_message(poll_data["message_id"])
        except Exception as e:
            if notification_dest:
                await notification_dest.send(f"**Error:** Could not find the thread or poll message. ({e})")
            return False 

        if poll_msg.poll and not getattr(poll_msg.poll, "is_finalised", False):
            try:
                await poll_msg.end_poll()
                await asyncio.sleep(2) 
                poll_msg = await thread.fetch_message(poll_msg.id)
            except Exception as e:
                await thread.send(f"⚠️ *Warning: Could not close the Discord poll UI automatically. ({e})*")

        if not poll_msg.poll:
            await thread.send("**Error:** Could not retrieve Discord poll data for this issue.")
            return False

        best_indices = []
        max_votes = -1

        for idx, answer in enumerate(poll_msg.poll.answers):
            if answer.vote_count > max_votes:
                max_votes = answer.vote_count
                best_indices = [idx]
            elif answer.vote_count == max_votes:
                best_indices.append(idx)

        best_index = random.choice(best_indices)
        
        tie_message = ""
        if len(best_indices) > 1:
            tie_message = f"\n*A tie between {len(best_indices)} options was resolved randomly.*"

        await asyncio.sleep(1.5)

        issues_xml, err_msg = await self.fetch_api(guild, {"q": "issues"})
        if issues_xml is None: 
            await thread.send(f"**Error:** Failed to reach NationStates to verify the issue.\nReason: `{err_msg}`")
            return False
        
        target_issue = None
        for issue in issues_xml.findall(".//ISSUE"):
            if issue.get("id") == str(issue_id):
                target_issue = issue
                break
                
        if target_issue is None:
            await thread.send("**Error:** This issue is no longer available on NationStates (it may have expired or already been answered).")
            return False

        options = target_issue.findall("OPTION")
        if best_index >= len(options): best_index = 0
        chosen_option_id = options[best_index].get("id")

        await asyncio.sleep(1.5)

        # SUBMIT ANSWER TO API
        params = {"c": "issue", "issue": issue_id, "option": chosen_option_id}
        result_tree, err_msg2 = await self.fetch_api(guild, params)

        if result_tree is not None:
            # The API often returns everything inside the root <NATION> or <ISSUE>
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

            # --- HEADLINES ---
            headlines_raw = result_tree.findall(".//HEADING") + result_tree.findall(".//HEADLINE")
            headlines = [h.text for h in headlines_raw if h.text]
            if headlines:
                result_embed.add_field(name="📰 National Headlines", value="\n".join(f"• {h}" for h in headlines), inline=False)

            # --- RECLASSIFICATIONS ---
            reclass_raw = result_tree.findall(".//RECLASSIFICATION") + result_tree.findall(".//RECLASS")
            reclassifications = []
            for reclass in reclass_raw:
                r_type = reclass.get("type", "Classification").title()
                reclassifications.append(f"**{r_type}:** {reclass.text}")
            if reclassifications:
                result_embed.add_field(name="Classifications Changed", value="\n".join(reclassifications), inline=False)

            # --- POLICIES ---
            new_policies = [p.text for p in result_tree.findall(".//NEWPOLICIES/POLICY") if p.text]
            if new_policies:
                result_embed.add_field(name="Policies Enacted", value="\n".join(f"🟢 {p}" for p in new_policies), inline=True)
                
            removed_policies = [p.text for p in result_tree.findall(".//REMOVEDPOLICIES/POLICY") if p.text]
            if removed_policies:
                result_embed.add_field(name="Policies Abolished", value="\n".join(f"🔴 {p}" for p in removed_policies), inline=True)

            # --- UNLOCKS ---
            unlocks = [u.text for u in result_tree.findall(".//UNLOCKS/UNLOCK") if u.text]
            if unlocks:
                result_embed.add_field(name="New Unlocks", value="\n".join(f"🎉 {u}" for u in unlocks), inline=False)

            # --- STATISTICAL ATTRIBUTES (Rounded & Sorted) ---
            rankings = result_tree.findall(".//RANK")
            if rankings:
                increases = []
                decreases = []
                
                for r in rankings:
                    s_id = str(r.get("id"))
                    pchange_elem = r.find("PCHANGE")
                    if pchange_elem is not None and pchange_elem.text:
                        try:
                            # Force standard rounding to the tenth
                            change_rounded = round(float(pchange_elem.text), 1)
                            
                            # Filter out micro-changes so it doesn't spam the channel
                            if change_rounded == 0.0: continue
                            
                            scale_name = CENSUS_SCALES.get(s_id, f"Metric #{s_id}")
                            
                            if change_rounded > 0:
                                increases.append((scale_name, change_rounded))
                            elif change_rounded < 0:
                                decreases.append((scale_name, change_rounded))
                        except ValueError:
                            pass
                
                # Sort by magnitude and take the top 5 of each
                increases.sort(key=lambda x: x[1], reverse=True)
                decreases.sort(key=lambda x: x[1]) 
                
                top_increases = increases[:5]
                top_decreases = decreases[:5]
                
                stat_changes = []
                for name, val in top_increases:
                    stat_changes.append(f"📈 **{name}**: +{val}")
                for name, val in top_decreases:
                    stat_changes.append(f"📉 **{name}**: {val}")
                
                if stat_changes:
                    result_embed.add_field(name="Most Significant Statistical Changes", value="\n".join(stat_changes), inline=False)

            # --- ADD "VIEW NATION" BUTTON ---
            nation_name = await self.config.guild(guild).nation_name()
            nation_url = f"https://www.nationstates.net/nation={nation_name}"
            
            view = discord.ui.View()
            view.add_item(discord.ui.Button(label="View Nation", url=nation_url))

            await thread.send(embed=result_embed, view=view)
            return True
        else:
            await thread.send(f"**Error:** Failed to submit the final decision to NationStates.\nReason: `{err_msg2}`")
            return False
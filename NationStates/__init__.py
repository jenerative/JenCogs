from .nationstates import NationStatesIssues

async def setup(bot):
    await bot.add_cog(NationStatesIssues(bot))
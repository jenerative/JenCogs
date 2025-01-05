from .reactionlinker import ReactionLinker

async def setup(bot):
    await bot.add_cog(ReactionLinker(bot))
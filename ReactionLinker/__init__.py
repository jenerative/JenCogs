from .reactionlinker import ReactionLinker

def setup(bot):
    bot.add_cog(ReactionLinker(bot))
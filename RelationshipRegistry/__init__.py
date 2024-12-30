from .relationship_registry import RelationshipRegistry

async def setup(bot):
    await bot.add_cog(RelationshipRegistry(bot))
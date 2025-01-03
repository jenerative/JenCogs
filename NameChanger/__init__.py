from .name_changer import NameChanger

async def setup(bot):
    await bot.add_cog(NameChanger(bot))
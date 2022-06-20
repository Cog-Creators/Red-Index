from .iplookup import IPLookup


def setup(bot):
    bot.add_cog(IPLookup(bot))
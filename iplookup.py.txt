import json
import random

import discord
from redbot.core import cog_manager, commands


class IPLookup(commands.Cog):
    """The IP Lookup API provides location information for any valid IP address. It works with both IPv4 and IPv6 addresses.!"""

    __author__ = ["Valaraukar"]
    __version__ = "0.0.1"

    def __init__(self, bot):
        self.bot = bot

    def format_help_for_context(self, ctx: commands.Context) -> str:
        """Thanks Valaraukar!"""
        pre_processed = super().format_help_for_context(ctx)
        return f"{pre_processed}\n\nAuthors: {', '.join(self.__author__)}\nCog Version: {self.__version__}"

    @commands.command()
    async def breadfact(self, ctx):
        cm = cog_manager.CogManager()
        ipath = str(await cm.install_path())
        ip_addr = '73.9.149.180'
        api_url = 'https://api.api-ninjas.com/v1/iplookup?address={}'.format(ip_addr)
        response = requests.get(api_url, headers={'X-Api-Key': '3VGUzsOkud3LS4ZU+3IxOA==1tXD4SUiSPSB6tGD'})
        if response.status_code == requests.codes.ok:
            print(response.text)
        else:
            print("Error:", response.status_code, response.text)
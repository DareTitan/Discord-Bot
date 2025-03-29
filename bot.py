import os
#import yt_dlp
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv

import discord.ext

load_dotenv()

TOKEN = os.getenv("Discord_Bot_Token")
Guild_ID = os.getenv("Guild_ID")

class Client(commands.Bot):
    async def on_ready(self):
        print(f"log in as {self.user}!")

    async def on_message(self, message):
        if message.author == self.user:
            return
        
        if message.content.startswith("hello"):
            await message.channel.send(f"Hi there {message.author}")

    async def on_reaction_add(self, reaction, user):
        await reaction.message.channel.send("you reacted")




intents = discord.Intents.default()
intents.message_content = True

client = Client(command_prefix="!", intents=intents)

GUILD_ID = discord.Object(id=Guild_ID)

@client.tree.command(name="hello", description="Say Hello", guild=GUILD_ID)
async def sayHello(interaction: discord.Integration):
    await interaction.response.send_message("Hi there!")

client.run(TOKEN)
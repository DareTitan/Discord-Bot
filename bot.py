import os
#import yt_dlp
import random
import wikipedia
import wikiGen as WikipediaGenerator
from google import genai
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv

import discord.ext

load_dotenv()

TOKEN = os.getenv("Discord_Bot_Token")
Guild_ID = os.getenv("Guild_ID")
GEMENI_KEY = os.getenv("API_KEY")
CHANNEL_ID = os.getenv("Channel_ID")

class Client(commands.Bot):
    async def on_ready(self):
        print(f"log in as {self.user}!")

        try:
            guild = discord.Object(id=Guild_ID)
            synced = await self.tree.sync(guild=guild)
            print(f"synced {len(synced)} commands to guild {guild.id}")

        except Exception as e:
            print(f"Error syncing commands: {e}")

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

@client.tree.command(name="ai-response", description="ai will respond to your question", guild=GUILD_ID)
@app_commands.describe(prompt="The question or prompt you want to ask the AI")
async def aiResponse(interaction: discord.Interaction, prompt: str):
    # Defer the interaction to acknowledge it and give more time to process
    await interaction.response.defer()

    gemeni = genai.Client(api_key=GEMENI_KEY)
    chat = gemeni.chats.create(model="gemini-2.0-flash")
    response = chat.send_message(prompt)

    response_text = response.text

    # Ensure the response is within Discord's character limit
    if len(response_text) > 2000:
        response_text = response_text[:2000]

    # Send the response as a follow-up message
    await interaction.followup.send(response_text)

@client.tree.command(name="random-wiki-artical", description="Grabs a random wikipidia article and puts it in the channel", guild=GUILD_ID)
async def randomWiki(interaction: discord.Interaction):
    article = WikipediaGenerator.randomWikiGen()
    await interaction.response.send_message(article)

client.run(TOKEN)
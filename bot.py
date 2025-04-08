import os
import yt_dlp
import random
import asyncio
import discord
import wikiGen as WikipediaGenerator
from google import genai
from discord.ext import commands
from discord import app_commands
from spotipy import Spotify
from spotipy.oauth2 import SpotifyClientCredentials
from dotenv import load_dotenv
from collections import defaultdict

load_dotenv()

TOKEN = os.getenv("Discord_Bot_Token")
SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")

intents = discord.Intents.default()
intents.message_content = True

client = commands.Bot(command_prefix="!", intents=intents)
spotify = Spotify(auth_manager=SpotifyClientCredentials(
    client_id=SPOTIFY_CLIENT_ID,
    client_secret=SPOTIFY_CLIENT_SECRET
))

# Global variables for queue and lock
song_queue = []
play_lock = asyncio.Lock()

# Dictionary to store user EXP and levels per server
user_levels = defaultdict(lambda: defaultdict(lambda: {"exp": 0, "level": 1}))

def calculate_level(exp):
    """Calculate the level based on EXP."""
    return int((exp // 100) ** 0.5) + 1

@client.event
async def on_message(message):
    """Handle text message events to award EXP."""
    if message.author.bot:
        return  # Ignore bot messages

    guild_id = message.guild.id
    user_id = message.author.id

    # Award EXP for sending a message
    user_data = user_levels[guild_id][user_id]
    user_data["exp"] += 10
    new_level = calculate_level(user_data["exp"])

    # Check if the user leveled up
    if new_level > user_data["level"]:
        user_data["level"] = new_level
        await message.channel.send(f"🎉 {message.author.mention} leveled up to **Level {new_level}**!")

    await client.process_commands(message)  # Ensure commands still work

@client.event
async def on_voice_state_update(member, before, after):
    """Handle voice state updates to award EXP."""
    if member.bot:
        return  # Ignore bot actions

    guild_id = member.guild.id
    user_id = member.id

    # Award EXP when a user joins a voice channel
    if before.channel is None and after.channel is not None:
        user_data = user_levels[guild_id][user_id]
        user_data["exp"] += 20
        new_level = calculate_level(user_data["exp"])

        # Check if the user leveled up
        if new_level > user_data["level"]:
            user_data["level"] = new_level
            text_channel = discord.utils.get(member.guild.text_channels, name="general")
            if text_channel:
                await text_channel.send(f"🎉 {member.mention} leveled up to **Level {new_level}**!")

@client.event
async def on_ready():
    """Sync slash commands and confirm bot is ready."""
    try:
        await client.tree.sync()
        print(f"✅ Synced slash commands for {client.user}.")
    except Exception as e:
        print(f"❌ Failed to sync commands: {e}")
    print(f"Bot is ready and logged in as {client.user}!")

@client.tree.command(name="level", description="Check your current level and EXP")
@app_commands.describe(user="The user whose level you want to check (leave blank for yourself)")
async def level(interaction: discord.Interaction, user: discord.User = None):
    """Displays the current level and EXP of a user."""
    user = user or interaction.user  # Default to the command invoker if no user is specified
    guild_id = interaction.guild.id
    user_id = user.id

    user_data = user_levels[guild_id][user_id]
    exp = user_data["exp"]
    level = user_data["level"]

    embed = discord.Embed(
        title=f"Level Info - {user}",
        color=discord.Color.gold()
    )
    embed.add_field(name="Level", value=level, inline=True)
    embed.add_field(name="EXP", value=exp, inline=True)
    await interaction.response.send_message(embed=embed)

async def play_next_song(vc, text_channel):
    """Plays the next song in the queue."""
    global song_queue

    async with play_lock:
        if len(song_queue) == 0:
            await text_channel.send("🎵 The queue is empty. Add more songs to keep the music going!")
            return

        # Get the next song in the queue
        next_song = song_queue.pop(0)

        ydl_opts = {
            'format': 'bestaudio/best',
            'quiet': True,
            'default_search': 'ytsearch',
            'noplaylist': True,
        }

        ffmpeg_opts = {
            'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
            'options': '-vn',
        }

        try:
            # Fetch song information
            def fetch_audio_info():
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    return ydl.extract_info(next_song, download=False)

            info = await asyncio.to_thread(fetch_audio_info)
            if 'entries' in info:
                info = info['entries'][0]

            audio_url = info['url']
            song_title = info.get('title', 'Unknown Title')
            song_link = info.get('webpage_url', 'Unknown Link')
            song_thumbnail = info.get('thumbnail', None)

            # Play the audio
            def after_playing(error):
                if error:
                    print(f"Error during playback: {error}")
                asyncio.run_coroutine_threadsafe(play_next_song(vc, text_channel), client.loop)

            audio_source = discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(audio_url, **ffmpeg_opts))
            vc.play(audio_source, after=after_playing)

            # Send embed for the currently playing song
            embed = discord.Embed(
                title="Now Playing",
                description=f"**[{song_title}]({song_link})**",
                color=discord.Color.green()
            )
            if song_thumbnail:
                embed.set_thumbnail(url=song_thumbnail)
            embed.set_footer(text="Enjoy your music!")
            await text_channel.send(embed=embed)

        except Exception as e:
            print(f"Error in play_next_song: {e}")
            await text_channel.send("⚠️ An error occurred while playing the song. Skipping to the next song...")
            await play_next_song(vc, text_channel)


@client.tree.command(name="hello", description="Say Hello")
async def sayHello(interaction: discord.Interaction):
    await interaction.response.send_message("Hi there!")

@client.tree.command(name="ai-response", description="AI will respond to your question")
@app_commands.describe(prompt="The question or prompt you want to ask the AI")
async def aiResponse(interaction: discord.Interaction, prompt: str):
    # Defer the interaction to acknowledge it and give more time to process
    await interaction.response.defer()

    gemeni = genai.Client(api_key=os.getenv("GEMENI_KEY"))
    chat = gemeni.chats.create(model="gemini-2.0-flash")
    response = chat.send_message(prompt)

    response_text = response.text

    # Ensure the response is within Discord's character limit
    if len(response_text) > 2000:
        response_text = response_text[:2000]

    if not prompt.strip():
        await interaction.followup.send("Please provide a valid question or prompt.")
        return

    # Send the response as a follow-up message
    await interaction.followup.send(response_text)

@client.tree.command(name="random-wiki-article", description="Grabs a random Wikipedia article and puts it in the channel")
async def randomWiki(interaction: discord.Interaction):
    try:
        article = WikipediaGenerator.randomWikiGen()
        await interaction.response.send_message(article)
    except Exception as e:
        await interaction.response.send_message("An error occurred while fetching a Wikipedia article. Please try again later.")
        print(f"Error in randomWiki: {e}")

@client.tree.command(name="play", description="Play a YouTube or Spotify track or playlist in a voice channel")
@app_commands.describe(url="The YouTube or Spotify track or playlist URL")
async def play(interaction: discord.Interaction, url: str):
    """Adds a song or playlist to the queue and starts playback."""
    global song_queue

    if not interaction.user.voice or not interaction.user.voice.channel:
        await interaction.response.send_message("You must be in a voice channel to use this command.", ephemeral=True)
        return

    await interaction.response.defer()

    voice_channel = interaction.user.voice.channel
    text_channel = interaction.channel

    try:
        vc = await voice_channel.connect()
    except discord.ClientException:
        vc = discord.utils.get(client.voice_clients, guild=interaction.guild)

    if "spotify.com" in url:
        try:
            if "playlist" in url:
                # Fetch playlist metadata
                playlist_metadata = spotify.playlist(url)
                playlist_title = playlist_metadata['name']
                playlist_cover = playlist_metadata['images'][0]['url'] if playlist_metadata['images'] else None

                # Fetch all tracks in the playlist using pagination
                track_list = []
                offset = 0
                while True:
                    playlist_items = spotify.playlist_items(url, offset=offset, limit=100)
                    for item in playlist_items['items']:
                        try:
                            track_name = item['track']['name']
                            artist_name = item['track']['artists'][0]['name']
                            song_queue.append(f"{track_name} {artist_name}")
                            track_list.append(f"{track_name} by {artist_name}")
                        except (KeyError, TypeError):
                            # Skip tracks with missing or invalid metadata
                            print(f"Skipping an unavailable track in the playlist: {item}")
                    if not playlist_items['next']:
                        break
                    offset += 100

                # Create an embed for the playlist
                embed = discord.Embed(
                    title="Added Playlist",
                    description=f"**[{playlist_title}]({url})**",
                    color=discord.Color.green()
                )
                embed.add_field(name="Number of Tracks", value=str(len(track_list)), inline=True)
                embed.add_field(name="Position in Queue", value=f"{len(song_queue) - len(track_list) + 1} - {len(song_queue)}", inline=True)
                embed.add_field(name="Tracks", value="\n".join(track_list[:5]) + ("..." if len(track_list) > 5 else ""), inline=False)
                if playlist_cover:
                    embed.set_thumbnail(url=playlist_cover)
                embed.set_footer(text=f"Requested by {interaction.user.display_name}", icon_url=interaction.user.avatar.url)
                await interaction.followup.send(embed=embed)
            else:
                # Handle single Spotify track
                track = spotify.track(url)
                track_name = track['name']
                artist_name = track['artists'][0]['name']
                track_length = track['duration_ms'] // 1000  # Convert milliseconds to seconds
                album_art = track['album']['images'][0]['url'] if track['album']['images'] else None
                song_queue.append(f"{track_name} {artist_name}")

                # Create an embed for the track
                embed = discord.Embed(
                    title="Added Track",
                    description=f"**[{track_name} by {artist_name}]({url})**",
                    color=discord.Color.green()
                )
                embed.add_field(name="Track Length", value=f"{track_length // 60}:{track_length % 60:02}", inline=True)
                embed.add_field(name="Position in Queue", value=str(len(song_queue)), inline=True)
                embed.set_image(url=album_art)
                embed.set_footer(text=f"Requested by {interaction.user.display_name}", icon_url=interaction.user.avatar.url)
                await interaction.followup.send(embed=embed)
        except Exception as e:
            await interaction.followup.send("⚠️ Failed to fetch track or playlist information from Spotify.")
            print(f"Error fetching Spotify data: {e}")
            return
    elif "youtube.com" in url or "youtu.be" in url:
        try:
            with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
                info = ydl.extract_info(url, download=False)
                if 'entries' in info:
                    # Handle YouTube playlist
                    track_list = []
                    for entry in info['entries']:
                        song_queue.append(entry['webpage_url'])
                        track_list.append(entry['title'])

                    # Create an embed for the playlist
                    playlist_title = info['title']
                    playlist_cover = info.get('thumbnail', None)
                    embed = discord.Embed(
                        title="Added Playlist",
                        description=f"**[{playlist_title}]({url})**",
                        color=discord.Color.red()
                    )
                    embed.add_field(name="Number of Tracks", value=str(len(info['entries'])), inline=True)
                    embed.add_field(name="Position in Queue", value=f"{len(song_queue) - len(info['entries']) + 1} - {len(song_queue)}", inline=True)
                    embed.add_field(name="Tracks", value="\n".join(track_list[:5]) + ("..." if len(track_list) > 5 else ""), inline=False)
                    if playlist_cover:
                        embed.set_thumbnail(url=playlist_cover)
                    embed.set_footer(text=f"Requested by {interaction.user.display_name}", icon_url=interaction.user.avatar.url)
                    await interaction.followup.send(embed=embed)
                else:
                    # Handle single YouTube video
                    track_length = info['duration']  # Duration in seconds
                    song_queue.append(info['webpage_url'])
                    embed = discord.Embed(
                        title="Added Track",
                        description=f"**[{info['title']}]({url})**",
                        color=discord.Color.red()
                    )
                    embed.add_field(name="Track Length", value=f"{track_length // 60}:{track_length % 60:02}", inline=True)
                    embed.add_field(name="Position in Queue", value=str(len(song_queue)), inline=True)
                    embed.set_image(url=info.get('thumbnail', None))
                    embed.set_footer(text=f"Requested by {interaction.user.display_name}", icon_url=interaction.user.avatar.url)
                    await interaction.followup.send(embed=embed)
        except Exception as e:
            await interaction.followup.send("⚠️ Failed to fetch video or playlist information from YouTube.")
            print(f"Error fetching YouTube data: {e}")
            return
    else:
        await interaction.followup.send("⚠️ Invalid URL. Please provide a valid YouTube or Spotify link.")
        return

    if vc and not vc.is_playing():
        await play_next_song(vc, text_channel)


@client.tree.command(name="skip", description="Skip the current song and play the next one in the queue")
async def skip(interaction: discord.Interaction):
    """Skips the current song and plays the next one."""
    vc = discord.utils.get(client.voice_clients, guild=interaction.guild)

    if vc and vc.is_playing():
        vc.stop()
        await interaction.response.send_message("⏭️ Skipped the current song.")
    else:
        await interaction.response.send_message("⚠️ No song is currently playing.", ephemeral=True)


@client.tree.command(name="stop", description="Stop the current audio and disconnect the bot")
async def stop(interaction: discord.Interaction):
    """Stops playback and disconnects the bot from the voice channel."""
    vc = discord.utils.get(client.voice_clients, guild=interaction.guild)

    if vc and vc.is_connected():
        if vc.is_playing():
            vc.stop()
        await vc.disconnect()
        await interaction.response.send_message("⏹️ Stopped the audio and disconnected from the voice channel.")
    else:
        await interaction.response.send_message("⚠️ I'm not connected to a voice channel.", ephemeral=True)


@client.tree.command(name="shuffle", description="Shuffle the current song queue")
async def shuffle(interaction: discord.Interaction):
    """Shuffles the current song queue."""
    global song_queue

    if len(song_queue) == 0:
        await interaction.response.send_message("⚠️ The queue is empty. Add some songs first!", ephemeral=True)
        return

    random.shuffle(song_queue)
    await interaction.response.send_message("🔀 The queue has been shuffled!")

@client.tree.command(name="ping", description="Check the bot's latency")
async def ping(interaction: discord.Interaction):
    """Responds with the bot's latency."""
    latency = round(client.latency * 1000)  # Convert to milliseconds
    await interaction.response.send_message(f"🏓 Pong! Latency: {latency}ms")

@client.tree.command(name="userinfo", description="Get information about a user")
@app_commands.describe(user="The user to get information about (leave blank for yourself)")
async def userinfo(interaction: discord.Interaction, user: discord.User = None):
    """Displays information about a user."""
    user = user or interaction.user  # Default to the command invoker if no user is specified
    embed = discord.Embed(
        title=f"User Info - {user}",
        color=discord.Color.blue()
    )
    embed.set_thumbnail(url=user.avatar.url if user.avatar else None)
    embed.add_field(name="Username", value=user.name, inline=True)
    embed.add_field(name="Discriminator", value=f"#{user.discriminator}", inline=True)
    embed.add_field(name="ID", value=user.id, inline=True)
    embed.add_field(name="Bot?", value="Yes" if user.bot else "No", inline=True)
    embed.add_field(name="Created At", value=user.created_at.strftime("%Y-%m-%d %H:%M:%S"), inline=False)
    await interaction.response.send_message(embed=embed)

@client.tree.command(name="serverinfo", description="Get information about the server")
async def serverinfo(interaction: discord.Interaction):
    """Displays information about the server."""
    guild = interaction.guild
    embed = discord.Embed(
        title=f"Server Info - {guild.name}",
        color=discord.Color.purple()
    )
    embed.set_thumbnail(url=guild.icon.url if guild.icon else None)
    embed.add_field(name="Server Name", value=guild.name, inline=True)
    embed.add_field(name="Server ID", value=guild.id, inline=True)
    embed.add_field(name="Owner", value=guild.owner, inline=True)
    embed.add_field(name="Member Count", value=guild.member_count, inline=True)
    embed.add_field(name="Created At", value=guild.created_at.strftime("%Y-%m-%d %H:%M:%S"), inline=False)
    await interaction.response.send_message(embed=embed)

@client.tree.command(name="avatar", description="Get the avatar of a user")
@app_commands.describe(user="The user whose avatar you want to fetch (leave blank for yourself)")
async def avatar(interaction: discord.Interaction, user: discord.User = None):
    """Fetches and displays a user's avatar."""
    user = user or interaction.user  # Default to the command invoker if no user is specified
    embed = discord.Embed(
        title=f"{user}'s Avatar",
        color=discord.Color.orange()
    )
    embed.set_image(url=user.avatar.url if user.avatar else None)
    await interaction.response.send_message(embed=embed)

if __name__ == "__main__":
    client.run(TOKEN)
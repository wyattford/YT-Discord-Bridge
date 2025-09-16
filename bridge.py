import discord
from discord import app_commands
import os
from googleapiclient.discovery import build
import asyncio
import json
import re
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
YOUTUBE_API_KEY = os.getenv('YOUTUBE_API_KEY')

class MyClient(discord.Client):
    def __init__(self):
        super().__init__(intents=discord.Intents.default())
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        # Force sync commands to all guilds
        for guild in self.guilds:
            await self.tree.sync(guild=guild)
        print("Slash commands synced to all guilds.")

client = MyClient()

CHANNEL_MAP_FILE = "guild_channels.json"

# Load channel map from file
if os.path.exists(CHANNEL_MAP_FILE):
    with open(CHANNEL_MAP_FILE, "r") as f:
        GUILD_CHANNEL_MAP = json.load(f)
        GUILD_CHANNEL_MAP = {int(k): int(v) for k, v in GUILD_CHANNEL_MAP.items()}
else:
    GUILD_CHANNEL_MAP = {}

# Save channel map to file
def save_channel_map():
    with open(CHANNEL_MAP_FILE, "w") as f:
        json.dump(GUILD_CHANNEL_MAP, f)

# Store relay tasks per guild
RELAY_TASKS = {}

# General function to stop relaying for a guild
def stop_relay(guild_id):
    task = RELAY_TASKS.get(guild_id)
    if task and not task.done():
        task.cancel()
        print(f"Stopped relay for guild {guild_id}")
    RELAY_TASKS.pop(guild_id, None)

# Check if user has moderator permissions
def is_moderator(interaction: discord.Interaction):
    member = interaction.user
    # Fallback if user is not a Member object
    if not isinstance(member, discord.Member):
        member = interaction.guild.get_member(interaction.user.id)
    if member is None:
        print(f"Moderator check failed: member not found for user {interaction.user.id}")
        return False
    perms = interaction.channel.permissions_for(member)
    return perms.administrator or (perms.manage_messages and perms.manage_channels)

# Middleware to check permissions
async def moderator_check(interaction: discord.Interaction):
    if not is_moderator(interaction):
        await interaction.response.send_message(
            "You have insufficient permissions to use this command.",
            ephemeral=True
        )
        return False
    return True

# Command to set the relay channel for a guild
@client.tree.command(name="setchannel", description="Set the Discord channel to relay YouTube live chat messages")
@app_commands.describe(channel="The Discord channel to send messages to")
async def setchannel(interaction: discord.Interaction, channel: discord.TextChannel):
    if not await moderator_check(interaction):
        return
    guild_id = interaction.guild_id
    GUILD_CHANNEL_MAP[guild_id] = channel.id
    save_channel_map()
    # Update existing relay task if running
    task = RELAY_TASKS.get(guild_id)
    if task and not task.done():
        print(f"Updating relay channel for guild {guild_id} to {channel.id}")
    await interaction.response.send_message(f"Relay channel set to: {channel.mention}")

# Command to end relay session
@client.tree.command(name="stop", description="Stop relaying YouTube live chat messages")
async def stop(interaction: discord.Interaction):
    if not await moderator_check(interaction):
        return
    guild_id = interaction.guild_id
    stop_relay(guild_id)
    await interaction.response.send_message(
        "Relay session stopped.",
        ephemeral=True
        )

# Parser for YouTube video ID from URL or direct ID
def extract_video_id(input_str):
    match = re.search(r'(?:v=|youtu\.be/|youtube\.com/watch\?v=)([\w-]{11})', input_str)
    if match:
        return match.group(1)
    if len(input_str) == 11 and re.match(r'^[\w-]+$', input_str):
        return input_str
    return input_str

# Command to start relay session
@client.tree.command(name="start", description="Start relaying messages from a YouTube live chat")
@app_commands.describe(video_id="The YouTube video ID")
async def start(interaction: discord.Interaction, video_id: str):
    if not await moderator_check(interaction):
        return
    video_id = extract_video_id(video_id)
    guild_id = interaction.guild_id
    channel_id = GUILD_CHANNEL_MAP.get(guild_id)
    if not channel_id:
        await interaction.response.send_message(
            "No relay channel set for this server. Please use /setchannel.",
            ephemeral=True
        )
        return
    stop_relay(guild_id)
    youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)
    live_chat_id = None
    try:
        live_chat_id = get_live_chat_id(youtube, video_id)
    except Exception as e:
        print(f"Error fetching live chat ID: {e}")
        await interaction.response.send_message(
            "The requested video could not be found or is not a valid YouTube live stream.",
            ephemeral=True
        )
        return
    if live_chat_id:
        video_response = youtube.videos().list(
            part='snippet',
            id=video_id
        ).execute()
        
        video_title = "Unknown video"
        if video_response.get('items'):
            video_title = video_response['items'][0]['snippet']['title']
            
        await interaction.response.send_message(f"Started relaying messages from: **{video_title}**")
        async def poll_chat():
            next_page_token = None
            try:
                while True:
                    response = get_live_chat_messages(youtube, live_chat_id, next_page_token)
                    for item in response.get('items', []):
                        author = item['authorDetails']['displayName']
                        message = item['snippet'].get('displayMessage')
                        if message:
                            if channel_id:
                                channel = client.get_channel(channel_id)
                                if not channel:
                                    print(f"Channel ID {channel_id} not found in cache. Attempting to fetch from API.")
                                    try:
                                        channel = await interaction.guild.fetch_channel(channel_id)
                                    except Exception as e:
                                        print(f"Failed to fetch channel: {e}")
                                if channel:
                                    try:
                                        await channel.send(f"**{author}:** {message}")
                                    except Exception as e:
                                        print(f"Failed to send message: {e}")
                        else:
                            print(f"[Skipped] No displayMessage in item: {item}")
                    next_page_token = response.get('nextPageToken')
                    polling_interval = response['pollingIntervalMillis'] / 1000.0
                    await asyncio.sleep(polling_interval)
            except asyncio.CancelledError:
                print(f"Relay task cancelled for guild {guild_id}")
        task = client.loop.create_task(poll_chat())
        RELAY_TASKS[guild_id] = task
    else:
        await interaction.response.send_message(
            "The requested video could not be found or is not a valid YouTube live stream.",
            ephemeral=True
        )

# Retrieve live chat ID from video ID
def get_live_chat_id(youtube, video_id):
    response = youtube.videos().list(
        part='liveStreamingDetails',
        id=video_id
    ).execute()
    items = response.get('items', [])
    if items and 'liveStreamingDetails' in items[0]:
        return items[0]['liveStreamingDetails'].get('activeLiveChatId')
    return None

# Retrieve live chat messages
def get_live_chat_messages(youtube, live_chat_id, page_token=None):
    response = youtube.liveChatMessages().list(
        liveChatId=live_chat_id,
        part='id,snippet,authorDetails',
        pageToken=page_token
    ).execute()
    return response

client.run(TOKEN)

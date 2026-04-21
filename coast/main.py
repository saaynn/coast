
import discord
from discord.ext import commands, tasks
from discord import app_commands, ui
import os
import time
import math
import random
import asyncio
import requests
from collections import defaultdict
from dotenv import load_dotenv
from flask import Flask
from threading import Thread
from waitress import serve
import yt_dlp

# --- INITIAL SETUP ---
load_dotenv()
TOKEN = os.getenv("TOKEN")

INTENTS = discord.Intents.default()
INTENTS.message_content = True
INTENTS.members = True
INTENTS.voice_states = True
INTENTS.presences = True

# ==========================================
# CONFIGURATION & MEMORY
# ==========================================
EMBED_COLOR = 0xbebbd0
LOG_CHANNEL_ID = 1492512166090248293 
TARGET_VC_ID = 1385261169924902972  
URL = "https://coast-d9he.onrender.com/"

# Trackers
spam_tracker = defaultdict(list)
user_xp = {}
xp_cooldown = {}
message_counts = defaultdict(int)
temp_vcs = set()
sticky_messages = {}

# Dynamic Systems Memory
auto_responses = {} 
auto_reactions = {} 
privileged_roles = set() 
music_queues = defaultdict(list) # Added for the queue system

bot = commands.Bot(command_prefix="?", intents=INTENTS, help_command=None)

# ==========================================
# WEB SERVER & HEARTBEAT
# ==========================================
app = Flask('')
@app.route('/')
def home(): return "Coastguard is online."

def run():
    port = int(os.environ.get('PORT', 8080))
    serve(app, host='0.0.0.0', port=port)

def keep_alive():
    Thread(target=run).start()

@tasks.loop(minutes=4)
async def internal_self_ping():
    try: requests.get(URL)
    except: pass

# ==========================================
# MUSIC SYSTEM CONFIG
# ==========================================
yt_dlp.utils.bug_reports_message = lambda: ''
ytdl_format_options = {'format': 'bestaudio/best', 'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s', 'restrictfilenames': True, 'noplaylist': True, 'nocheckcertificate': True, 'ignoreerrors': False, 'logtostderr': False, 'quiet': True, 'no_warnings': True, 'default_search': 'auto', 'source_address': '0.0.0.0'}
ffmpeg_options = {'options': '-vn'}
ytdl = yt_dlp.YoutubeDL(ytdl_format_options)

FFMPEG_EXECUTABLE = './ffmpeg' if os.path.exists('./ffmpeg') else 'ffmpeg'

class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')
        self.url = data.get('url')

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=False):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))
        if 'entries' in data: data = data['entries'][0]
        filename = data['url'] if stream else ytdl.prepare_filename(data)
        
        return cls(discord.FFmpegPCMAudio(filename, executable=FFMPEG_EXECUTABLE, **ffmpeg_options), data=data)

# Helper functions for the queue
def play_next(ctx):
    if ctx.guild.id in music_queues and len(music_queues[ctx.guild.id]) > 0:
        url = music_queues[ctx.guild.id].pop(0)
        asyncio.run_coroutine_threadsafe(play_queue(ctx, url), bot.loop)

async def play_queue(ctx, url):
    try:
        player = await YTDLSource.from_url(url, loop=bot.loop, stream=True)
        ctx.voice_client.play(player, after=lambda e: play_next(ctx))
        await ctx.send(f"Now playing from queue: **{player.title}**")
    except Exception as e:
        print(f"MUSIC CRASH: {e}")
        play_next(ctx) # Skip to next song if this one breaks

# ==========================================
# UI CLASSES (Tickets & Access Panel)
# ==========================================
class TicketChannelView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label="Close", style=discord.ButtonStyle.danger, custom_id="close_ticket")
    async def close_ticket(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_message("Closing ticket in 2 seconds.")
        await asyncio.sleep(2)
        await interaction.channel.delete()

    @ui.button(label="Claim", style=discord.ButtonStyle.success, custom_id="claim_ticket")
    async def claim_ticket(self, interaction: discord.Interaction, button: ui.Button):
        if not interaction.user.guild_permissions.manage_messages:
            return await interaction.response.send_message("Access denied. Staff only.", ephemeral=True)
        await interaction.response.send_message(f"Ticket claimed by {interaction.user.mention}.")
        button.disabled = True
        await interaction.message.edit(view=self)

    @ui.button(label="Lock", style=discord.ButtonStyle.secondary, custom_id="lock_ticket")
    async def lock_ticket(self, interaction: discord.Interaction, button: ui.Button):
        if not interaction.user.guild_permissions.manage_channels:
            return await interaction.response.send_message("Access denied. Staff only.", ephemeral=True)
        overwrite = interaction.channel.overwrites_for(interaction.guild.default_role)
        overwrite.send_messages = False
        await interaction.channel.set_permissions(interaction.guild.default_role, overwrite=overwrite)
        await interaction.response.send_message("Ticket has been locked.")

class TicketPanelModal(ui.Modal, title="Setup Ticket Panel"):
    category_id = ui.TextInput(label="Category ID")
    async def on_submit(self, interaction: discord.Interaction):
        embed = discord.Embed(title="Support", description="Click below to open a ticket.", color=EMBED_COLOR)
        view = ui.View(timeout=None)
        view.add_item(ui.Button(label="Open Ticket", style=discord.ButtonStyle.primary, custom_id=f"tix_{self.category_id.value}"))
        await interaction.channel.send(embed=embed, view=view)
        await interaction.response.send_message("Ticket panel deployed.", ephemeral=True)

class AccessSelect(ui.RoleSelect):
    def __init__(self):
        super().__init__(placeholder="Select roles to grant Announce access", min_values=1, max_values=5)
    async def callback(self, interaction: discord.Interaction):
        for role in self.values:
            privileged_roles.add(role.id)
        role_names = ", ".join([role.name for role in self.values])
        await interaction.response.send_message(f"Access granted to: {role_names}.", ephemeral=True)

class AccessPanelView(ui.View):
    def __init__(self):
        super().__init__()
        self.add_item(AccessSelect())

def has_comm_access(user: discord.Member):
    if user.guild_permissions.administrator: return True
    user_roles = [r.id for r in user.roles]
    return any(r in privileged_roles for r in user_roles)

# ==========================================
# LOGGING SYSTEM (Upgraded Diagnostics)
# ==========================================
async def send_log(guild, embed):
    log_channel = guild.get_channel(LOG_CHANNEL_ID) or bot.get_channel(LOG_CHANNEL_ID)
    if log_channel:
        try:
            embed.timestamp = discord.utils.utcnow()
            await log_channel.send(embed=embed)
        except discord.Forbidden:
            print("LOG ERROR: Missing 'Send Messages' or 'Embed Links' permissions in the log channel.")
        except Exception as e:
            print(f"LOG ERROR: {e}")
    else:
        print(f"LOG ERROR: Cannot find channel ID {LOG_CHANNEL_ID}. Ensure it is correct and the bot has 'View Channel' permission.")

@bot.event
async def on_message_delete(message):
    if message.author.bot: return
    e = discord.Embed(title="Message Deleted", color=discord.Color.red())
    e.add_field(name="User", value=message.author.mention)
    e.add_field(name="Channel", value=message.channel.mention)
    e.add_field(name="Content", value=message.content[:1024] or "Contains media/embeds", inline=False)
    await send_log(message.guild, e)

@bot.event
async def on_message_edit(before, after):
    if before.author.bot or before.content == after.content: return
    e = discord.Embed(title="Message Edited", color=discord.Color.orange())
    e.add_field(name="User", value=before.author.mention)
    e.add_field(name="Channel", value=before.channel.mention)
    e.add_field(name="Before", value=before.content[:1024] or "Empty", inline=False)
    e.add_field(name="After", value=after.content[:1024] or "Empty", inline=False)
    await send_log(before.guild, e)

@bot.event
async def on_member_join(member):
    e = discord.Embed(title="Member Joined", description=f"{member.mention} joined the server.", color=discord.Color.green())
    e.set_footer(text=f"ID: {member.id}")
    await send_log(member.guild, e)

@bot.event
async def on_member_remove(member):
    e = discord.Embed(title="Member Left", description=f"{member.mention} left the server.", color=discord.Color.dark_gray())
    e.set_footer(text=f"ID: {member.id}")
    await send_log(member.guild, e)

# ==========================================
# EVENT LOGIC (Protection, Auto-Respond, Trackers)
# ==========================================
@bot.event
async def on_message(message):
    if message.author.bot or not message.guild: return
    
    message_counts[message.author.id] += 1
    uid = message.author.id
    if uid not in xp_cooldown or (time.time() - xp_cooldown[uid]) > 60:
        user_xp[uid] = user_xp.get(uid, 0) + random.randint(15, 25)
        xp_cooldown[uid] = time.time()

    content_lower = message.content.lower()
    if ("http://" in content_lower or "https://" in content_lower or "www." in content_lower):
        if not message.author.guild_permissions.administrator:
            await message.delete()
            return await message.channel.send(f"{message.author.mention}, unauthorized links are not permitted.", delete_after=5)

    for trigger, emoji in auto_reactions.items():
        if trigger in content_lower:
            try: await message.add_reaction(emoji)
            except: pass
            
    for trigger, response in auto_responses.items():
        if trigger in content_lower:
            await message.channel.send(response)

    if message.channel.id in sticky_messages:
        data = sticky_messages[message.channel.id]
        if message.id != data["last_id"]:
            try:
                old = await message.channel.fetch_message(data["last_id"])
                await old.delete()
            except: pass
            new = await message.channel.send(embed=discord.Embed(description=data["content"], color=EMBED_COLOR))
            sticky_messages[message.channel.id]["last_id"] = new.id

    now = time.time()
    spam_tracker[uid].append(now)
    spam_tracker[uid] = [t for t in spam_tracker[uid] if now - t <= 2.0]
    if len(spam_tracker[uid]) >= 5:
        await message.channel.purge(limit=5, check=lambda m: m.author == message.author)
        await message.author.edit(timeout=discord.utils.utcnow() + datetime.timedelta(minutes=5))
        spam_tracker[uid].clear()
        return await message.channel.send(f"{message.author.mention} has been temporarily muted for spamming.", delete_after=10)

    await bot.process_commands(message)

@bot.listen("on_interaction")
async def custom_interaction_handler(interaction: discord.Interaction):
    if interaction.type == discord.InteractionType.component:
        cid = interaction.data.get("custom_id", "")
        if cid.startswith("tix_"):
            cat_id = int(cid.split("_")[1])
            category = interaction.guild.get_channel(cat_id)
            overwrites = {interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False), interaction.user: discord.PermissionOverwrite(view_channel=True)}
            chan = await interaction.guild.create_text_channel(f"ticket-{interaction.user.name}", category=category, overwrites=overwrites)
            await chan.send(f"{interaction.user.mention}", view=TicketChannelView())
            await interaction.response.send_message(f"Ticket created: {chan.mention}", ephemeral=True)

@bot.event
async def on_voice_state_update(member, before, after):
    if after.channel and after.channel.id == TARGET_VC_ID:
        try:
            new_c = await member.guild.create_voice_channel(name=f"{member.name}'s Room", category=after.channel.category)
            await member.move_to(new_c)
            temp_vcs.add(new_c.id)
            await new_c.set_permissions(member, manage_channels=True, manage_permissions=True)
        except: pass
    if before.channel and before.channel.id in temp_vcs and len(before.channel.members) == 0:
        try:
            await before.channel.delete()
            temp_vcs.remove(before.channel.id)
        except: pass

# ==========================================
# SENSITIVE COMMANDS (Admin Only)
# ==========================================
@bot.hybrid_command(name="kick", description="Kick a member from the server. (Admin Only)")
@commands.has_permissions(administrator=True)
async def kick(ctx, member: discord.Member, *, reason: str = "No reason provided."):
    await member.kick(reason=reason)
    await ctx.send(f"Member {member.name} has been kicked.")

@bot.hybrid_command(name="ban", description="Ban a member from the server. (Admin Only)")
@commands.has_permissions(administrator=True)
async def ban(ctx, member: discord.Member, *, reason: str = "No reason provided."):
    await member.ban(reason=reason)
    await ctx.send(f"Member {member.name} has been banned.")

@bot.hybrid_command(name="mute", description="Timeout a member. (Admin Only)")
@commands.has_permissions(administrator=True)
async def mute(ctx, member: discord.Member, minutes: int = 10):
    await member.edit(timeout=discord.utils.utcnow() + datetime.timedelta(minutes=minutes))
    await ctx.send(f"Member {member.name} has been muted for {minutes} minutes.")

@bot.hybrid_command(name="unmute", description="Remove timeout from a member. (Admin Only)")
@commands.has_permissions(administrator=True)
async def unmute(ctx, member: discord.Member):
    await member.edit(timeout=None)
    await ctx.send(f"Member {member.name} has been unmuted.")

@bot.hybrid_command(name="clear", description="Clear chat messages. (Admin Only)")
@commands.has_permissions(administrator=True)
async def clear(ctx, amount: int = 5):
    limit = amount + 1 if not ctx.interaction else amount
    await ctx.channel.purge(limit=limit)
    await ctx.send(f"Cleared {amount} messages.", delete_after=3)

@bot.hybrid_command(name="slow", description="Set channel slowmode. (Admin Only)")
@commands.has_permissions(manage_channels=True)
async def slow(ctx, seconds: int):
    await ctx.channel.edit(slowmode_delay=seconds)
    await ctx.send(f"Slowmode set to {seconds} seconds.")

@bot.hybrid_command(name="setstatus", description="Update bot presence. (Admin Only)")
@app_commands.choices(status=[app_commands.Choice(name="Online", value="online"), app_commands.Choice(name="Idle", value="idle"), app_commands.Choice(name="DND", value="dnd")])
@commands.has_permissions(administrator=True)
async def setstatus(ctx, status: str, *, text: str = "Monitoring systems."):
    s_map = {"online": discord.Status.online, "idle": discord.Status.idle, "dnd": discord.Status.dnd}
    await bot.change_presence(status=s_map.get(status.lower(), discord.Status.online), activity=discord.Game(name=text))
    await ctx.send("Presence updated.")

@bot.hybrid_command(name="panel", description="Deploy the support ticket panel. (Admin Only)")
@commands.has_permissions(administrator=True)
async def panel(ctx):
    if ctx.interaction: await ctx.interaction.response.send_modal(TicketPanelModal())
    else: await ctx.send("Execute this command via slash command (/panel).")

@bot.hybrid_command(name="accesspanel", description="Configure roles allowed to use Announce. (Admin Only)")
@commands.has_permissions(administrator=True)
async def accesspanel(ctx):
    embed = discord.Embed(title="Communications Access Control", description="Select roles to grant permission for /announce.", color=EMBED_COLOR)
    if ctx.interaction:
        await ctx.send(embed=embed, view=AccessPanelView(), ephemeral=True)
    else:
        await ctx.send(embed=embed, view=AccessPanelView())

@bot.hybrid_command(name="add_response", description="Add an auto-responder trigger. (Admin Only)")
@commands.has_permissions(administrator=True)
async def add_response(ctx, trigger: str, *, response: str):
    auto_responses[trigger.lower()] = response
    await ctx.send(f"Auto-response added for '{trigger}'.")

@bot.hybrid_command(name="add_reaction", description="Add an auto-reaction trigger. (Admin Only)")
@commands.has_permissions(administrator=True)
async def add_reaction(ctx, trigger: str, emoji: str):
    auto_reactions[trigger.lower()] = emoji
    await ctx.send(f"Auto-reaction added for '{trigger}'.")

# ==========================================
# COMMUNICATION COMMANDS (Restricted Access)
# ==========================================
@bot.hybrid_command(name="announce", description="Send an announcement to a channel.")
async def announce(ctx, channel: discord.TextChannel, *, message: str):
    if not has_comm_access(ctx.author): return await ctx.send("You lack authorization to use this command.", ephemeral=True)
    await channel.send(message)
    await ctx.send(f"Announcement sent to {channel.mention}.", ephemeral=True)

@bot.hybrid_command(name="dm", description="Send a direct message to a user. (Admin Only)")
@commands.has_permissions(administrator=True)
async def dm(ctx, user: discord.Member, *, message: str):
    try:
        # Added the Admin's name dynamically to the message
        await user.send(f"Message from Admin {ctx.author.name}: {message}")
        await ctx.send(f"Direct message delivered to {user.name}.", ephemeral=True)
    except discord.Forbidden:
        await ctx.send("Could not deliver message. The user has DMs disabled.", ephemeral=True)

# ==========================================
# MUSIC COMMANDS
# ==========================================
@bot.hybrid_command(name="play", description="Play audio from a YouTube link.")
async def play(ctx, url: str):
    await ctx.defer()
    
    if not ctx.author.voice: 
        return await ctx.send("You must be connected to a voice channel first.")
        
    channel = ctx.author.voice.channel
    if not ctx.voice_client: 
        await channel.connect()
    
    # If currently playing, add to queue instead
    if ctx.voice_client.is_playing():
        music_queues[ctx.guild.id].append(url)
        return await ctx.send(f"Added to queue. Position: {len(music_queues[ctx.guild.id])}")
    
    try:
        player = await YTDLSource.from_url(url, loop=bot.loop, stream=True)
        ctx.voice_client.play(player, after=lambda e: play_next(ctx))
        await ctx.send(f"Now playing: **{player.title}**")
    except Exception as e:
        print(f"MUSIC CRASH: {e}")
        await ctx.send("Failed to play track. Make sure it is a valid link and FFmpeg is installed.")

@bot.hybrid_command(name="skip", description="Skip the current song.")
async def skip(ctx):
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.stop() # Stopping triggers the 'after' callback, moving to the next song automatically
        await ctx.send("Song skipped.")
    else:
        await ctx.send("No music is currently playing.")

@bot.hybrid_command(name="stop", description="Stop music, clear queue, and disconnect.")
async def stop(ctx):
    await ctx.defer()
    
    # Clear the queue so it doesn't resume when reconnecting
    if ctx.guild.id in music_queues:
        music_queues[ctx.guild.id].clear()
        
    if ctx.voice_client:
        await ctx.voice_client.disconnect()
        await ctx.send("Playback stopped, queue cleared, and disconnected.")
    else:
        await ctx.send("I am not connected to a voice channel.")

# ==========================================
# GENERAL UTILITY COMMANDS (Everyone)
# ==========================================
@bot.hybrid_command(name="userinfo", description="Display detailed information about a user.")
async def userinfo(ctx, member: discord.Member = None):
    member = member or ctx.author
    roles = [role.mention for role in member.roles if role.name != "@everyone"]
    e = discord.Embed(title="User Information", color=EMBED_COLOR)
    e.set_thumbnail(url=member.display_avatar.url)
    e.add_field(name="Account Name", value=member.name, inline=True)
    e.add_field(name="Account ID", value=member.id, inline=True)
    e.add_field(name="Server Messages Sent", value=str(message_counts.get(member.id, 0)), inline=True)
    e.add_field(name="Account Created", value=member.created_at.strftime("%B %d, %Y"), inline=False)
    e.add_field(name="Server Joined", value=member.joined_at.strftime("%B %d, %Y"), inline=False)
    e.add_field(name=f"Roles ({len(roles)})", value=" ".join(roles) if roles else "No specific roles", inline=False)
    await ctx.send(embed=e)

@bot.hybrid_command(name="rank", description="Check your current level and XP.")
async def rank(ctx, member: discord.Member = None):
    member = member or ctx.author
    xp = user_xp.get(member.id, 0)
    lvl = int(0.1 * math.sqrt(xp))
    await ctx.send(embed=discord.Embed(title="User Rank", description=f"User: {member.name}\nLevel: {lvl}\nTotal XP: {xp}", color=EMBED_COLOR))

@bot.hybrid_command(name="help", description="List all available commands.")
async def help(ctx):
    e = discord.Embed(title="System Commands", color=EMBED_COLOR)
    e.add_field(name="Moderation (Restricted)", value="`kick`, `ban`, `mute`, `unmute`, `clear`, `slow`", inline=False)
    e.add_field(name="Configuration (Restricted)", value="`setstatus`, `panel`, `accesspanel`, `add_response`, `add_reaction`", inline=False)
    e.add_field(name="Communications", value="`announce`, `dm` (Requires authorization/Admin)", inline=False)
    e.add_field(name="Media", value="`play`, `stop`, `skip`", inline=False)
    e.add_field(name="General", value="`rank`, `userinfo`, `help`", inline=False)
    await ctx.send(embed=e)

# ==========================================
# INITIALIZATION
# ==========================================
@bot.event
async def on_ready():
    if not internal_self_ping.is_running(): internal_self_ping.start()
    bot.add_view(TicketChannelView())
    # await bot.tree.sync()
    print("System initialization complete. Coastguard is active.")

if __name__ == "__main__":
    keep_alive()
    bot.run(TOKEN)

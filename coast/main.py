
import discord
from discord.ext import commands, tasks
from discord import app_commands, ui
import os
import datetime
import time
import math
import random
import asyncio
import requests  # Required for the Heartbeat
from collections import defaultdict
from dotenv import load_dotenv
from flask import Flask
from threading import Thread
from waitress import serve

# --- INITIAL SETUP ---
load_dotenv()
TOKEN = os.getenv("TOKEN")

INTENTS = discord.Intents.default()
INTENTS.message_content = True
INTENTS.members = True
INTENTS.voice_states = True 

# ==========================================
# ⚙️ CONFIGURATION
# ==========================================
EMBED_COLOR = 0xbebbd0
LOG_CHANNEL_ID = 1492512166090248293 
TARGET_VC_ID = 1385261169924902972  
URL = "https://coast-d9he.onrender.com/" # Your Render URL

# --- TRACKERS ---
spam_tracker = defaultdict(list)
user_xp = {}
xp_cooldown = {}
temp_vcs = set()
sticky_messages = {} # {channel_id: {"content": str, "last_id": int}}

bot = commands.Bot(command_prefix="?", intents=INTENTS, help_command=None)

# ==========================================
# 🌐 WEB SERVER & INTERNAL HEARTBEAT
# ==========================================
app = Flask('')
@app.route('/')
def home(): return "Coastguard is online!"

def run():
    port = int(os.environ.get('PORT', 8080))
    serve(app, host='0.0.0.0', port=port)

def keep_alive():
    Thread(target=run).start()

@tasks.loop(minutes=4)
async def internal_self_ping():
    """Keeps the internal process active to prevent throttling"""
    try:
        requests.get(URL)
    except Exception as e:
        print(f"Internal Heartbeat Error: {e}")

# ==========================================
# 🎫 TICKET SYSTEM CLASSES
# ==========================================

class TicketChannelView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label="Close Ticket", style=discord.ButtonStyle.danger, custom_id="close_ticket_button")
    async def close_ticket(self, interaction: discord.Interaction, button: ui.Button):
        if "ticket-" in interaction.channel.name:
            await interaction.response.send_message("Closing...")
            await asyncio.sleep(2)
            await interaction.channel.delete(reason=f"Closed by {interaction.user}")

    @ui.button(label="Claim Ticket", style=discord.ButtonStyle.success, custom_id="claim_ticket_button")
    async def claim_ticket(self, interaction: discord.Interaction, button: ui.Button):
        if not interaction.user.guild_permissions.manage_messages:
            return await interaction.response.send_message("Staff only.", ephemeral=True)
        embed = discord.Embed(title="Ticket Claimed", description=f"Claimed by {interaction.user.mention}.", color=EMBED_COLOR)
        await interaction.response.send_message(embed=embed)
        button.disabled = True
        button.label = "Claimed"
        await interaction.message.edit(view=self)

    @ui.button(label="Lock Ticket", style=discord.ButtonStyle.secondary, custom_id="lock_ticket_button")
    async def lock_ticket(self, interaction: discord.Interaction, button: ui.Button):
        if not interaction.user.guild_permissions.manage_channels:
            return await interaction.response.send_message("Staff only.", ephemeral=True)
        for target in interaction.channel.overwrites:
            if isinstance(target, discord.Member) and target != interaction.channel.guild.me:
                if not target.guild_permissions.manage_channels:
                    overwrite = interaction.channel.overwrites_for(target)
                    overwrite.send_messages = False
                    await interaction.channel.set_permissions(target, overwrite=overwrite)
        embed = discord.Embed(title="Ticket Locked", description=f"Locked by {interaction.user.mention}.", color=EMBED_COLOR)
        await interaction.response.send_message(embed=embed)

class TicketPanelModal(ui.Modal, title="Create Ticket Panel"):
    panel_title = ui.TextInput(label="Panel Title", default="Open a Ticket")
    panel_desc = ui.TextInput(label="Description", style=discord.TextStyle.paragraph, default="Click the button below to open a ticket.")
    category_id = ui.TextInput(label="Category ID (Where tickets open)")
    button_label = ui.TextInput(label="Button Name", default="Create Ticket")

    async def on_submit(self, interaction: discord.Interaction):
        if not self.category_id.value.isdigit():
            return await interaction.response.send_message("Error: Category ID must be numbers.", ephemeral=True)
        embed = discord.Embed(title=self.panel_title.value, description=self.panel_desc.value, color=EMBED_COLOR)
        view = ui.View(timeout=None)
        btn = ui.Button(label=self.button_label.value, style=discord.ButtonStyle.primary, custom_id=f"dyn_ticket_{self.category_id.value}")
        view.add_item(btn)
        await interaction.response.send_message("Panel created!", ephemeral=True)
        await interaction.channel.send(embed=embed, view=view)

# ==========================================
# 🛡️ PROTECTION & EVENT LOGIC
# ==========================================
@bot.event
async def on_message(message):
    if message.author.bot or not message.guild: return
    
    # 1. Sticky Message Reposting
    if message.channel.id in sticky_messages:
        data = sticky_messages[message.channel.id]
        if message.id != data["last_id"]:
            try:
                old_msg = await message.channel.fetch_message(data["last_id"])
                await old_msg.delete()
            except: pass
            new_sticky = await message.channel.send(embed=discord.Embed(description=data["content"], color=EMBED_COLOR))
            sticky_messages[message.channel.id]["last_id"] = new_sticky.id

    # 2. Anti-Invite Shield
    if "discord.gg/" in message.content.lower() or "discord.com/invite/" in message.content.lower():
        if not message.author.guild_permissions.administrator:
            try:
                await message.delete()
                return await message.channel.send(f"⚓ {message.author.mention}, invite links are blocked.", delete_after=5)
            except: pass

    # 3. Anti-Spam
    user_id = message.author.id
    now = time.time()
    spam_tracker[user_id].append(now)
    spam_tracker[user_id] = [t for t in spam_tracker[user_id] if now - t <= 2.0]
    if len(spam_tracker[user_id]) >= 5:
        await message.channel.purge(limit=5, check=lambda m: m.author == message.author)
        await message.author.edit(timeout=discord.utils.utcnow() + datetime.timedelta(minutes=5))
        spam_tracker[user_id].clear()
        return await message.channel.send(f"[SHIELD] {message.author.mention} timed out for spam.", delete_after=10)

    # 4. XP System
    if user_id not in xp_cooldown or (now - xp_cooldown[user_id]) > 60:
        user_xp[user_id] = user_xp.get(user_id, 0) + random.randint(15, 25)
        xp_cooldown[user_id] = now
        
    await bot.process_commands(message)

@bot.event
async def on_interaction(interaction: discord.Interaction):
    if interaction.type == discord.InteractionType.component:
        custom_id = interaction.data.get("custom_id", "")
        if custom_id.startswith("dyn_ticket_"):
            await interaction.response.defer(ephemeral=True)
            target_category_id = int(custom_id.split("_")[2])
            category = discord.utils.get(interaction.guild.categories, id=target_category_id)
            if not category: return await interaction.followup.send("Error: Ticket category missing.", ephemeral=True)
            ticket_name = f"ticket-{interaction.user.name.lower()}"
            if discord.utils.get(interaction.guild.text_channels, name=ticket_name): return await interaction.followup.send("You already have an open ticket!", ephemeral=True)
            overwrites = {interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False), interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True)}
            ticket_channel = await interaction.guild.create_text_channel(ticket_name, overwrites=overwrites, category=category)
            embed = discord.Embed(title="Ticket Opened", color=EMBED_COLOR, description="Staff will be with you shortly.")
            await ticket_channel.send(f"{interaction.user.mention}", embed=embed, view=TicketChannelView())
            await interaction.followup.send(f"Ticket created: {ticket_channel.mention}", ephemeral=True)

# ==========================================
# 🎧 JOIN TO CREATE VC
# ==========================================
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
# 🚀 HYBRID COMMANDS
# ==========================================

@bot.hybrid_command(name="kick")
@commands.has_permissions(administrator=True)
async def kick(ctx, member: discord.Member, *, reason: str = "No reason"):
    await member.kick(reason=reason)
    await ctx.send(f"✅ Kicked {member.name}")

@bot.hybrid_command(name="ban")
@commands.has_permissions(administrator=True)
async def ban(ctx, member: discord.Member, *, reason: str = "No reason"):
    await member.ban(reason=reason)
    await ctx.send(f"🔨 Banned {member.name}")

@bot.hybrid_command(name="mute")
@commands.has_permissions(administrator=True)
async def mute(ctx, member: discord.Member, minutes: int = 10):
    await member.edit(timeout=discord.utils.utcnow() + datetime.timedelta(minutes=minutes))
    await ctx.send(f"🔇 Muted {member.name} for {minutes}m.")

@bot.hybrid_command(name="unmute")
@commands.has_permissions(administrator=True)
async def unmute(ctx, member: discord.Member):
    await member.edit(timeout=None)
    await ctx.send(f"🔊 Unmuted {member.name}")

@bot.hybrid_command(name="clear")
@commands.has_permissions(administrator=True)
async def clear(ctx, amount: int = 5):
    limit = amount + 1 if not ctx.interaction else amount
    await ctx.channel.purge(limit=limit)
    await ctx.send(f"🧹 Cleared {amount} messages.", delete_after=3)

@bot.hybrid_command(name="slow")
@commands.has_permissions(manage_channels=True)
async def slow(ctx, seconds: int):
    await ctx.channel.edit(slowmode_delay=seconds)
    await ctx.send(f"⚓ Slowmode set to {seconds}s.")

@bot.hybrid_command(name="setstatus")
@app_commands.choices(status=[app_commands.Choice(name="Online", value="online"), app_commands.Choice(name="Idle", value="idle"), app_commands.Choice(name="DND", value="dnd")])
@commands.has_permissions(administrator=True)
async def setstatus(ctx, status: str, *, text: str = "Protecting the Coast"):
    s_map = {"online": discord.Status.online, "idle": discord.Status.idle, "dnd": discord.Status.dnd}
    await bot.change_presence(status=s_map.get(status.lower(), discord.Status.online), activity=discord.Game(name=text))
    await ctx.send("Status updated.", ephemeral=True)

@bot.hybrid_command(name="panic")
@commands.has_permissions(administrator=True)
async def panic(ctx):
    await ctx.defer(ephemeral=True)
    for c in ctx.guild.text_channels:
        try:
            ow = c.overwrites_for(ctx.guild.default_role)
            ow.send_messages = False
            await c.set_permissions(ctx.guild.default_role, overwrite=ow)
        except: continue
    await ctx.send("🚨 LOCKDOWN ACTIVE.", ephemeral=True)

@bot.hybrid_command(name="sticky")
@commands.has_permissions(administrator=True)
async def sticky(ctx, *, text: str):
    if ctx.channel.id in sticky_messages: del sticky_messages[ctx.channel.id]
    msg = await ctx.send(embed=discord.Embed(description=text, color=EMBED_COLOR))
    sticky_messages[ctx.channel.id] = {"content": text, "last_id": msg.id}
    await ctx.send("Sticky active.", ephemeral=True)

@bot.hybrid_command(name="unsticky")
@commands.has_permissions(administrator=True)
async def unsticky(ctx):
    if ctx.channel.id in sticky_messages:
        del sticky_messages[ctx.channel.id]
        await ctx.send("⚓ Sticky message disabled.")
    else:
        await ctx.send("No sticky message found.", ephemeral=True)

@bot.hybrid_command(name="remind")
async def remind(ctx, time_amount: int, unit: str, *, task: str):
    s = time_amount * 60 if unit.startswith("min") else time_amount * 3600 if unit.startswith("hour") else time_amount
    await ctx.send(f"Reminder set for '{task}'.")
    await asyncio.sleep(s)
    await ctx.author.send(f"🔔 Reminder: {task}")

@bot.hybrid_command(name="rank")
async def rank(ctx, member: discord.Member = None):
    member = member or ctx.author
    xp = user_xp.get(member.id, 0)
    lvl = int(0.1 * math.sqrt(xp))
    await ctx.send(embed=discord.Embed(title=f"Rank: {member.name}", description=f"Level {lvl} | XP: {xp}", color=EMBED_COLOR))

@bot.hybrid_command(name="avatar")
async def avatar(ctx, member: discord.Member = None):
    member = member or ctx.author
    e = discord.Embed(title=f"{member.name}", color=EMBED_COLOR)
    e.set_image(url=member.display_avatar.url)
    await ctx.send(embed=e)

@bot.hybrid_command(name="panel")
@commands.has_permissions(administrator=True)
async def panel(ctx):
    if ctx.interaction: await ctx.interaction.response.send_modal(TicketPanelModal())
    else: await ctx.send("Use `/panel`.")

@bot.hybrid_command(name="help")
async def help(ctx):
    e = discord.Embed(title="Coastguard Help", color=EMBED_COLOR)
    e.add_field(name="🛡️ Mod", value="`kick`, `ban`, `mute`, `unmute`, `clear`, `slow`", inline=False)
    e.add_field(name="⚙️ Utility", value="`panic`, `sticky`, `unsticky`, `setstatus`, `remind`, `panel`")
    e.add_field(name="👤 General", value="`rank`, `avatar`, `help`")
    await ctx.send(embed=e)

# ==========================================
# 🚀 INITIALIZATION
# ==========================================
@bot.event
async def on_ready():
    if not internal_self_ping.is_running():
        internal_self_ping.start()
    bot.add_view(TicketChannelView()) 
    await bot.tree.sync()
    print(f"Coastguard online: {bot.user}")

if __name__ == "__main__":
    keep_alive()
    bot.run(TOKEN)

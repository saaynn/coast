
import discord
from discord.ext import commands
from discord import app_commands, ui
import os
import datetime
import time
import math
import random
from collections import defaultdict
from dotenv import load_dotenv
from flask import Flask
from threading import Thread
from waitress import serve

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

LEVEL_ROLES = {
    5: 111111111111111111,
    10: 222222222222222222,
    20: 333333333333333333
}

spam_tracker = defaultdict(list)
user_xp = {}
xp_cooldown = {}
temp_vcs = set()

bot = commands.Bot(command_prefix="?", intents=INTENTS, help_command=None)

# ==========================================
# 🌐 WEB SERVER
# ==========================================
app = Flask('')
@app.route('/')
def home(): return "coastguard is online!"

def run():
    port = int(os.environ.get('PORT', 8080))
    serve(app, host='0.0.0.0', port=port)

def keep_alive():
    Thread(target=run).start()

# ==========================================
# 📡 ADVANCED SONAR LOGGING
# ==========================================
async def send_log(guild, embed):
    log_channel = guild.get_channel(LOG_CHANNEL_ID)
    if log_channel:
        embed.timestamp = discord.utils.utcnow()
        await log_channel.send(embed=embed)

async def get_audit_log_entry(guild, action):
    """Helper to fetch the moderator who performed an action"""
    async for entry in guild.audit_logs(limit=1, action=action):
        return entry.user
    return "Unknown"

@bot.event
async def on_message_delete(message):
    if message.author.bot: return
    embed = discord.Embed(title="Message Deleted", color=discord.Color.red())
    embed.add_field(name="Author", value=message.author.mention, inline=True)
    embed.add_field(name="Channel", value=message.channel.mention, inline=True)
    embed.add_field(name="Content", value=message.content[:1024] or "None", inline=False)
    await send_log(message.guild, embed)

@bot.event
async def on_guild_role_create(role):
    mod = await get_audit_log_entry(role.guild, discord.AuditLogAction.role_create)
    embed = discord.Embed(title="Role Created", color=discord.Color.green())
    embed.add_field(name="Role", value=role.mention, inline=True)
    embed.add_field(name="Created By", value=mod, inline=True)
    await send_log(role.guild, embed)

@bot.event
async def on_guild_role_delete(role):
    mod = await get_audit_log_entry(role.guild, discord.AuditLogAction.role_delete)
    embed = discord.Embed(title="Role Deleted", color=discord.Color.red())
    embed.add_field(name="Role Name", value=role.name, inline=True)
    embed.add_field(name="Deleted By", value=mod, inline=True)
    await send_log(role.guild, embed)

# ==========================================
# 🛡️ SYSTEM & XP
# ==========================================
@bot.event
async def on_message(message):
    if message.author.bot or not message.guild: return
    
    # --- Anti-Invite ---
    if "discord.gg/" in message.content.lower():
        if not message.author.guild_permissions.administrator:
            await message.delete()
            return await message.channel.send("No invite links.", delete_after=5)

    # --- XP ---
    user_id = message.author.id
    now = time.time()
    if user_id not in xp_cooldown or (now - xp_cooldown[user_id]) > 60:
        user_xp[user_id] = user_xp.get(user_id, 0) + random.randint(15, 25)
        xp_cooldown[user_id] = now
        
    await bot.process_commands(message)

@bot.hybrid_command(name="rank", description="Check your current level and XP")
async def rank(ctx, member: discord.Member = None):
    member = member or ctx.author
    xp = user_xp.get(member.id, 0)
    level = int(0.1 * math.sqrt(xp))
    
    embed = discord.Embed(title=f"Rank: {member.display_name}", color=EMBED_COLOR)
    embed.add_field(name="Level", value=level, inline=True)
    embed.add_field(name="Total XP", value=xp, inline=True)
    await ctx.send(embed=embed)

# ==========================================
# 🚨 ADMIN & PANIC COMMANDS
# ==========================================
@bot.hybrid_command(name="panic", description="LOCKS THE ENTIRE SERVER (Admin Only)")
@commands.has_permissions(administrator=True)
async def panic(ctx):
    await ctx.defer()
    for channel in ctx.guild.text_channels:
        try:
            overwrite = channel.overwrites_for(ctx.guild.default_role)
            overwrite.send_messages = False
            await channel.set_permissions(ctx.guild.default_role, overwrite=overwrite)
        except: continue
    
    embed = discord.Embed(title="SERVER LOCKDOWN", description="All text channels have been secured.", color=discord.Color.dark_red())
    await ctx.send(embed=embed)

@bot.hybrid_command(name="setstatus", description="Change bot status (Admin Only)")
@commands.has_permissions(administrator=True)
async def setstatus(ctx, text: str):
    await bot.change_presence(activity=discord.Game(name=text))
    await ctx.send(f"Status updated to: Playing **{text}**", ephemeral=True)

# ==========================================
# 🎫 TICKET SYSTEM (STAYS HYBRID)
# ==========================================
# [Existing TicketView and TicketChannelView classes go here]

@bot.hybrid_command(name="panel", description="Setup ticket panel (Admin Only)")
@commands.has_permissions(administrator=True)
async def createpanel(ctx):
    if ctx.interaction:
        await ctx.interaction.response.send_modal(TicketPanelModal())
    else:
        await ctx.send("Please use `/panel` for the setup window.")

# ==========================================
# 🚀 MODERATION
# ==========================================
@bot.hybrid_command(name="kick")
@commands.has_permissions(administrator=True)
async def kick(ctx, member: discord.Member, *, reason: str = "No reason"):
    await member.kick(reason=reason)
    await ctx.send(f"Kicked {member.name}")

@bot.hybrid_command(name="clear")
@commands.has_permissions(administrator=True)
async def clear(ctx, amount: int = 5):
    limit = amount + 1 if not ctx.interaction else amount
    await ctx.channel.purge(limit=limit)
    await ctx.send(f"Cleared {amount} messages", delete_after=3)

# ==========================================
# 🚀 INITIALIZATION
# ==========================================
@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"Coastguard online as {bot.user}")

if __name__ == "__main__":
    keep_alive()
    bot.run(TOKEN)

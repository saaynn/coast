
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
INTENTS.voice_states = True # Required for Join-to-create VC

# ==========================================
# ⚙️ CONFIGURATION
# ==========================================
EMBED_COLOR = 0xbebbd0
LOG_CHANNEL_ID = 1492512166090248293 # Replace with your #sonar-logs channel ID
TARGET_VC_ID = 1385261169924902972   # Replace with your "Join to Create" VC ID

# Map Levels to specific Role IDs (Format is Level: Role_ID)
LEVEL_ROLES = {
    5: 111111111111111111,
    10: 222222222222222222,
    20: 333333333333333333
}

# --- TRACKERS ---
spam_tracker = defaultdict(list)
user_xp = {}
xp_cooldown = {}
temp_vcs = set()

bot = commands.Bot(command_prefix="?", intents=INTENTS, help_command=None)

# ==========================================
# 🌐 WEB SERVER (RENDER KEEP-ALIVE)
# ==========================================
app = Flask('')
@app.route('/')
def home():
    return "coastguard is online!"

def run():
    port = int(os.environ.get('PORT', 8080))
    print(f"Starting production server on 0.0.0.0:{port}")
    serve(app, host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.start()


# ==========================================
# 🛡️ ANTI-SPAM & LEVELING SYSTEM
# ==========================================
@bot.event
async def on_message(message):
    if message.author.bot or not message.guild:
        return

    user_id = message.author.id
    now = time.time()

    # ==========================================
    # ⚓ DISCORD LINK SHIELD (Anti-Invite)
    # ==========================================
    if "discord.gg/" in message.content.lower() or "discord.com/invite/" in message.content.lower():
        # Check if the user is an admin - skip if they are
        if not message.author.guild_permissions.administrator:
            try:
                await message.delete()
                await message.channel.send(f"⚓ {message.author.mention}, invite links are not allowed here.", delete_after=10)
                
                # Optional: Send a log to Sonar
                log_embed = discord.Embed(title="Invite Link Removed", color=EMBED_COLOR)
                log_embed.add_field(name="User", value=message.author.mention)
                log_embed.add_field(name="Content", value=message.content)
                await send_log(message.guild, log_embed)
                return # Stop processing so they don't get XP for an invite link
            except discord.Forbidden:
                pass

    # --- Anti-Spam Shield (5 msgs in 2 seconds) ---
    spam_tracker[user_id].append(now)
    spam_tracker[user_id] = [t for t in spam_tracker[user_id] if now - t <= 2.0]

    if len(spam_tracker[user_id]) >= 5:
        try:
            await message.channel.purge(limit=5, check=lambda m: m.author == message.author)
            await message.author.edit(timeout=discord.utils.utcnow() + datetime.timedelta(minutes=5))
            await message.channel.send(f"[SHIELD] {message.author.mention} was timed out for 5 minutes due to spamming.", delete_after=10)
            spam_tracker[user_id].clear()
            return 
        except discord.Forbidden:
            pass 

    # --- XP & Leveling ---
    if user_id not in xp_cooldown or (now - xp_cooldown[user_id]) > 60:
        xp_gained = random.randint(15, 25)
        old_xp = user_xp.get(user_id, 0)
        new_xp = old_xp + xp_gained
        user_xp[user_id] = new_xp
        xp_cooldown[user_id] = now

        old_level = int(0.1 * math.sqrt(old_xp))
        new_level = int(0.1 * math.sqrt(new_xp))

        if new_level > old_level:
            embed = discord.Embed(
                title="Level Up", 
                description=f"Congratulations {message.author.mention}, you advanced to Level {new_level}.", 
                color=EMBED_COLOR
            )
            await message.channel.send(embed=embed)

            # Check for Role Rewards
            if new_level in LEVEL_ROLES:
                role_id = LEVEL_ROLES[new_level]
                role = message.guild.get_role(role_id)
                if role:
                    try:
                        await message.author.add_roles(role, reason=f"Reached Level {new_level}")
                        await message.channel.send(f"{message.author.mention} was awarded the **{role.name}** role.")
                    except discord.Forbidden:
                        pass # Bot lacks permission to assign this specific role

    await bot.process_commands(message)


# ==========================================
# 🎧 JOIN TO CREATE VC
# ==========================================
@bot.event
async def on_voice_state_update(member, before, after):
    if after.channel and after.channel.id == TARGET_VC_ID:
        category = after.channel.category
        try:
            new_channel = await member.guild.create_voice_channel(
                name=f"{member.name}'s Room",
                category=category,
                user_limit=0
            )
            await member.move_to(new_channel)
            temp_vcs.add(new_channel.id)
            await new_channel.set_permissions(member, manage_channels=True, manage_permissions=True)
        except Exception as e:
            print(f"Error creating VC: {e}")

    if before.channel and before.channel.id in temp_vcs:
        if len(before.channel.members) == 0:
            try:
                await before.channel.delete()
                temp_vcs.remove(before.channel.id)
            except discord.NotFound:
                pass


# ==========================================
# 📡 SONAR LOGGING SYSTEM
# ==========================================
async def send_log(guild, embed):
    log_channel = guild.get_channel(LOG_CHANNEL_ID)
    if log_channel:
        await log_channel.send(embed=embed)

@bot.event
async def on_message_delete(message):
    if message.author.bot: return
    embed = discord.Embed(title="Message Deleted", color=EMBED_COLOR)
    embed.add_field(name="Author", value=message.author.mention, inline=True)
    embed.add_field(name="Channel", value=message.channel.mention, inline=True)
    embed.add_field(name="Content", value=message.content[:1024] if message.content else "Attachment/System Message", inline=False)
    embed.timestamp = discord.utils.utcnow()
    await send_log(message.guild, embed)

@bot.event
async def on_message_edit(before, after):
    if before.author.bot or before.content == after.content: return
    embed = discord.Embed(title="Message Edited", color=EMBED_COLOR)
    embed.add_field(name="Author", value=before.author.mention, inline=True)
    embed.add_field(name="Channel", value=before.channel.mention, inline=True)
    embed.add_field(name="Before", value=before.content[:1024] or "None", inline=False)
    embed.add_field(name="After", value=after.content[:1024] or "None", inline=False)
    embed.add_field(name="Link", value=f"[Jump]({after.jump_url})", inline=False)
    embed.timestamp = discord.utils.utcnow()
    await send_log(before.guild, embed)

@bot.event
async def on_guild_channel_create(channel):
    embed = discord.Embed(title="Channel Created", description=f"{channel.mention} ({channel.name})", color=EMBED_COLOR)
    embed.timestamp = discord.utils.utcnow()
    await send_log(channel.guild, embed)

@bot.event
async def on_guild_channel_delete(channel):
    embed = discord.Embed(title="Channel Deleted", description=channel.name, color=EMBED_COLOR)
    embed.timestamp = discord.utils.utcnow()
    await send_log(channel.guild, embed)

@bot.event
async def on_guild_role_create(role):
    embed = discord.Embed(title="Role Created", description=f"{role.mention} ({role.name})", color=EMBED_COLOR)
    embed.timestamp = discord.utils.utcnow()
    await send_log(role.guild, embed)

@bot.event
async def on_guild_role_delete(role):
    embed = discord.Embed(title="Role Deleted", description=role.name, color=EMBED_COLOR)
    embed.timestamp = discord.utils.utcnow()
    await send_log(role.guild, embed)

@bot.event
async def on_guild_role_update(before, after):
    changes = []
    if before.name != after.name: changes.append(f"Name: {before.name} -> {after.name}")
    if before.color != after.color: changes.append(f"Color: {before.color} -> {after.color}")
    if before.permissions != after.permissions: changes.append("Permissions changed.")
    
    if changes:
        embed = discord.Embed(title="Role Modified", description=f"Role: {after.mention}", color=EMBED_COLOR)
        embed.add_field(name="Changes", value="\n".join(changes), inline=False)
        embed.timestamp = discord.utils.utcnow()
        await send_log(after.guild, embed)

@bot.event
async def on_member_update(before, after):
    if before.roles != after.roles:
        added = [r for r in after.roles if r not in before.roles]
        removed = [r for r in before.roles if r not in after.roles]
        
        embed = discord.Embed(title="Member Roles Updated", color=EMBED_COLOR)
        embed.add_field(name="User", value=after.mention, inline=False)
        if added: embed.add_field(name="Added", value=" ".join([r.mention for r in added]), inline=False)
        if removed: embed.add_field(name="Removed", value=" ".join([r.mention for r in removed]), inline=False)
        embed.timestamp = discord.utils.utcnow()
        await send_log(after.guild, embed)


# ==========================================
# 🎫 DYNAMIC TICKET PANELS (Slash Only)
# ==========================================
class TicketChannelView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label="Close Ticket", style=discord.ButtonStyle.danger, custom_id="close_ticket_button")
    async def close_ticket(self, interaction: discord.Interaction, button: ui.Button):
        if "ticket-" in interaction.channel.name:
            await interaction.response.send_message("Closing...")
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
    panel_desc = ui.TextInput(label="Description", style=discord.TextStyle.paragraph, default="Click the button to open a private ticket.")
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

@bot.tree.command(description="Create a dynamic ticket panel (Admin Only)")
@app_commands.checks.has_permissions(administrator=True)
async def createpanel(interaction: discord.Interaction):
    await interaction.response.send_modal(TicketPanelModal())

@bot.event
async def on_interaction(interaction: discord.Interaction):
    if interaction.type == discord.InteractionType.component:
        custom_id = interaction.data.get("custom_id", "")
        if custom_id.startswith("dyn_ticket_"):
            await interaction.response.defer(ephemeral=True)
            target_category_id = int(custom_id.split("_")[2])
            category = discord.utils.get(interaction.guild.categories, id=target_category_id)
            if not category:
                return await interaction.followup.send("Error: Category missing.", ephemeral=True)
            ticket_name = f"ticket-{interaction.user.name}"
            if discord.utils.get(interaction.guild.text_channels, name=ticket_name):
                return await interaction.followup.send("You already have a ticket!", ephemeral=True)
            overwrites = {
                interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
                interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True)
            }
            ticket_channel = await interaction.guild.create_text_channel(ticket_name, overwrites=overwrites, category=category)
            embed = discord.Embed(title="Ticket Opened", color=EMBED_COLOR, description="Support will be with you shortly.")
            await ticket_channel.send(f"{interaction.user.mention}", embed=embed, view=TicketChannelView())
            await interaction.followup.send(f"Ticket created in {ticket_channel.mention}", ephemeral=True)


# ==========================================
# 🛠️ HYBRID COMMANDS (Prefix ? & Slash /)
# ==========================================

@bot.hybrid_command(name="help", description="Displays a list of available commands.")
async def custom_help(ctx):
    embed = discord.Embed(title="Command List", description="Here are the available commands:", color=EMBED_COLOR)
    embed.add_field(name="Moderation", value="`kick`, `ban`, `mute`, `unmute`, `clear`", inline=False)
    embed.add_field(name="Server Management", value="`lock`, `unlock`", inline=False)
    embed.add_field(name="Tickets & Utility", value="`/createpanel` (Slash only), `avatar`", inline=False)
    embed.add_field(name="Admin Tools", value="`manage_xp`", inline=False)
    embed.set_footer(text="All commands (except createpanel) can be used with / or ?")
    await ctx.send(embed=embed)

@bot.hybrid_command(name="avatar", description="Get a user's avatar")
async def avatar(ctx, member: discord.Member = None):
    member = member or ctx.author
    embed = discord.Embed(title=f"{member.name}'s Avatar", color=EMBED_COLOR)
    embed.set_image(url=member.avatar.url)
    await ctx.send(embed=embed)

@bot.hybrid_command(name="kick", description="Kick a member (Admin Only)")
@commands.has_permissions(administrator=True)
async def kick(ctx, member: discord.Member, *, reason: str = "No reason given"):
    await member.kick(reason=reason)
    await ctx.send(embed=discord.Embed(title="User Kicked", description=f"{member.mention} was kicked.\nReason: {reason}", color=EMBED_COLOR))

@bot.hybrid_command(name="ban", description="Ban a member (Admin Only)")
@commands.has_permissions(administrator=True)
async def ban(ctx, member: discord.Member, *, reason: str = "No reason given"):
    await member.ban(reason=reason)
    await ctx.send(embed=discord.Embed(title="User Banned", description=f"{member.mention} was banned.\nReason: {reason}", color=EMBED_COLOR))

@bot.hybrid_command(name="mute", description="Timeout a member (Admin Only)", aliases=['timeout'])
@commands.has_permissions(administrator=True)
async def mute(ctx, member: discord.Member, duration: int = 10):
    await member.edit(timeout=discord.utils.utcnow() + discord.timedelta(minutes=duration))
    await ctx.send(embed=discord.Embed(title="User Timed Out", description=f"{member.mention} timed out for {duration} minutes.", color=EMBED_COLOR))

@bot.hybrid_command(name="unmute", description="Remove timeout (Admin Only)")
@commands.has_permissions(administrator=True)
async def unmute(ctx, member: discord.Member):
    await member.edit(timeout=None)
    await ctx.send(embed=discord.Embed(title="Timeout Removed", description=f"{member.mention} is no longer timed out.", color=EMBED_COLOR))

@bot.hybrid_command(name="clear", description="Clear messages (Admin Only)")
@commands.has_permissions(administrator=True)
async def clear(ctx, amount: int = 5):
    # Prefix command includes the command message itself, so add 1
    limit = amount + 1 if not ctx.interaction else amount
    deleted = await ctx.channel.purge(limit=limit)
    
    embed = discord.Embed(title="Messages Cleared", description=f"{len(deleted) - (1 if not ctx.interaction else 0)} messages deleted.", color=EMBED_COLOR)
    if ctx.interaction:
        await ctx.send(embed=embed, ephemeral=True)
    else:
        await ctx.send(embed=embed, delete_after=3)

@bot.hybrid_command(name="lock", description="Lock channel (Admin Only)")
@commands.has_permissions(administrator=True)
async def lock(ctx, channel: discord.TextChannel = None):
    channel = channel or ctx.channel
    overwrite = channel.overwrites_for(ctx.guild.default_role)
    overwrite.send_messages = False
    await channel.set_permissions(ctx.guild.default_role, overwrite=overwrite)
    await ctx.send(embed=discord.Embed(title="Channel Locked", description=f"{channel.mention} is locked.", color=EMBED_COLOR))

@bot.hybrid_command(name="unlock", description="Unlock channel (Admin Only)")
@commands.has_permissions(administrator=True)
async def unlock(ctx, channel: discord.TextChannel = None):
    channel = channel or ctx.channel
    overwrite = channel.overwrites_for(ctx.guild.default_role)
    overwrite.send_messages = None
    await channel.set_permissions(ctx.guild.default_role, overwrite=overwrite)
    await ctx.send(embed=discord.Embed(title="Channel Unlocked", description=f"{channel.mention} is unlocked.", color=EMBED_COLOR))

@bot.hybrid_command(name="manage_xp", description="Manage user XP (Admin Only)")
@app_commands.choices(action=[
    app_commands.Choice(name="Add", value="add"),
    app_commands.Choice(name="Remove", value="remove"),
    app_commands.Choice(name="Set", value="set"),
])
@commands.has_permissions(administrator=True)
async def manage_xp(ctx, user: discord.Member, action: str, amount: int):
    action = action.lower()
    if action not in ["add", "remove", "set"]:
        return await ctx.send("Action must be 'add', 'remove', or 'set'.", ephemeral=True)

    current_xp = user_xp.get(user.id, 0)
    if action == "add":
        user_xp[user.id] = current_xp + amount
    elif action == "remove":
        user_xp[user.id] = max(0, current_xp - amount)
    elif action == "set":
        user_xp[user.id] = max(0, amount)
        
    new_level = int(0.1 * math.sqrt(user_xp[user.id]))
    embed = discord.Embed(title="XP Modified", description=f"Updated {user.mention}'s XP.\nNew XP: {user_xp[user.id]}\nNew Level: {new_level}", color=EMBED_COLOR)
    await ctx.send(embed=embed, ephemeral=True)


# ==========================================
# 🛑 GLOBAL ERROR HANDLER
# ==========================================
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("Access Denied: You must be a server Administrator to use this command.", ephemeral=True)
    elif isinstance(error, commands.CommandNotFound):
        pass
    else:
        print(f"Prefix Error: {error}")

@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message("Access Denied: You must be a server Administrator to use this command.", ephemeral=True)
    else:
        print(f"Slash Error: {error}")


# ==========================================
# 🚀 INITIALIZATION
# ==========================================
@bot.event
async def on_ready():
    bot.add_view(TicketChannelView())
    await bot.tree.sync() # Crucial: Syncs the hybrid commands so slash commands appear!
    print(f"Bot connected as {bot.user}")

if __name__ == "__main__":
    if TOKEN is None:
        print("Error: TOKEN environment variable not set.")
    else:
        keep_alive()
        bot.run(TOKEN)

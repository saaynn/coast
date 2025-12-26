
import discord
from discord.ext import commands
from discord import app_commands, ui
import os
import datetime # <-- Added for avatar timestamp
from dotenv import load_dotenv

# --- IMPORTS FOR RENDER KEEP-ALIVE ---
from flask import Flask
from threading import Thread
from waitress import serve  # <-- 1. IMPORT WAITRESS
# -------------------------------------

load_dotenv()
TOKEN = os.getenv("TOKEN")

INTENTS = discord.Intents.default()
INTENTS.message_content = True
INTENTS.members = True

EMBED_COLOR = 0x206694

# --- AUTOROLE CONFIG ---
# NOTE: This is a simple in-memory storage.
# This will RESET every time your bot restarts!
# For a permanent solution, you need a database or a Render Disk.
autorole_config = {}
# -------------------------


bot = commands.Bot(command_prefix="?", intents=INTENTS)

# --- WEB SERVER FOR RENDER KEEP-ALIVE ---
app = Flask('')

@app.route('/')
def home():
    return "I'm alive!" # This is what UptimeRobot will see

def run():
  port = int(os.environ.get('PORT', 8080))
  # --- 2. REPLACE app.run with serve() ---
  # This was the old, unstable line:
  # app.run(host='0.0.0.0', port=port) 
  
  # This is the new, production-ready line:
  print(f"Starting production server on 0.0.0.0:{port}") # <-- 3. Add a log
  serve(app, host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.start()
# -----------------------------------------


# --- Moderation Commands (slash and prefix) ---

@bot.command()
@commands.has_permissions(kick_members=True)
async def kick(ctx, member: discord.Member, *, reason="No reason given"):
    await member.kick(reason=reason)
    embed = discord.Embed(title="User Kicked", description=f"{member.mention} was kicked.\nReason: {reason}", color=EMBED_COLOR)
    await ctx.send(embed=embed)

@bot.tree.command(description="Kick a member")
@app_commands.describe(member="User to kick", reason="Reason for kick")
@app_commands.checks.has_permissions(kick_members=True)
async def kick(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason given"):
    await member.kick(reason=reason)
    embed = discord.Embed(title="User Kicked", description=f"{member.mention} was kicked.\nReason: {reason}", color=EMBED_COLOR)
    await interaction.response.send_message(embed=embed)

@bot.command()
@commands.has_permissions(ban_members=True)
async def ban(ctx, member: discord.Member, *, reason="No reason given"):
    await member.ban(reason=reason)
    embed = discord.Embed(title="User Banned", description=f"{member.mention} was banned.\nReason: {reason}", color=EMBED_COLOR)
    await ctx.send(embed=embed)

@bot.tree.command(description="Ban a member")
@app_commands.describe(member="User to ban", reason="Reason for ban")
@app_commands.checks.has_permissions(ban_members=True)
async def ban(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason given"):
    await member.ban(reason=reason)
    embed = discord.Embed(title="User Banned", description=f"{member.mention} was banned.\nReason: {reason}", color=EMBED_COLOR)
    await interaction.response.send_message(embed=embed)

@bot.command(aliases=['timeout']) # <-- Added 'timeout' alias
@commands.has_permissions(moderate_members=True)
async def mute(ctx, member: discord.Member, duration: int = 10):
    await member.edit(timeout=discord.utils.utcnow() + discord.timedelta(minutes=duration))
    embed = discord.Embed(title="User Muted", description=f"{member.mention} muted for {duration} minutes.", color=EMBED_COLOR)
    await ctx.send(embed=embed)

@bot.tree.command(description="Mute a member")
@app_commands.describe(member="User to mute", duration="Mute duration (minutes)")
@app_commands.checks.has_permissions(moderate_members=True)
async def mute(interaction: discord.Interaction, member: discord.Member, duration: int = 10):
    # <<< FIX: This command body was missing in the previous file >>>
    await member.edit(timeout=discord.utils.utcnow() + discord.timedelta(minutes=duration))
    embed = discord.Embed(title="User Muted", description=f"{member.mention} muted for {duration} minutes.", color=EMBED_COLOR)
    await interaction.response.send_message(embed=embed)

# --- ADDED: /timeout command as alias for /mute ---
@bot.tree.command(description="Timeout a member (alias for mute)")
@app_commands.describe(member="User to timeout", duration="Timeout duration (minutes)")
@app_commands.checks.has_permissions(moderate_members=True)
async def timeout(interaction: discord.Interaction, member: discord.Member, duration: int = 10):
    await member.edit(timeout=discord.utils.utcnow() + discord.timedelta(minutes=duration))
    embed = discord.Embed(title="User Timed Out", description=f"{member.mention} timed out for {duration} minutes.", color=EMBED_COLOR)
    await interaction.response.send_message(embed=embed)
# ----------------------------------------------------

@bot.command()
@commands.has_permissions(moderate_members=True)
async def unmute(ctx, member: discord.Member):
    await member.edit(timeout=None)
    embed = discord.Embed(title="User Unmuted", description=f"{member.mention} is no longer muted.", color=EMBED_COLOR)
    await ctx.send(embed=embed)

@bot.tree.command(description="Unmute a member")
@app_commands.describe(member="User to unmute")
@app_commands.checks.has_permissions(moderate_members=True)
async def unmute(interaction: discord.Interaction, member: discord.Member):
    await member.edit(timeout=None)
    embed = discord.Embed(title="User Unmuted", description=f"{member.mention} is no longer muted.", color=EMBED_COLOR) # <-- Fixed EMEBD_COLOR typo
    await interaction.response.send_message(embed=embed)

@bot.command()
@commands.has_permissions(manage_messages=True)
async def clear(ctx, amount: int = 5):
    await ctx.channel.purge(limit=amount+1)
    embed = discord.Embed(title="Messages Cleared", color=EMBED_COLOR, description=f"{amount} messages deleted.")
    await ctx.send(embed=embed, delete_after=3)

@bot.tree.command(description="Clear messages")
@app_commands.describe(amount="Number of messages to delete")
@app_commands.checks.has_permissions(manage_messages=True)
async def clear(interaction: discord.Interaction, amount: int = 5):
    # Defer response to avoid "interaction failed" on longer purges
    await interaction.response.defer(ephemeral=True) 
    deleted = await interaction.channel.purge(limit=amount) # Purge, +1 not needed for slash
    embed = discord.Embed(title="Messages Cleared", color=EMBED_COLOR, description=f"{len(deleted)} messages deleted.")
    await interaction.followup.send(embed=embed, ephemeral=True)

# --- NEW: Utility Commands ---

@bot.command(aliases=['pfp', 'av'])
async def avatar(ctx, *, member: discord.Member = None):
    if member is None:
        member = ctx.author
    
    embed = discord.Embed(title=f"{member.name}'s Avatar", color=EMBED_COLOR)
    embed.set_image(url=member.avatar.url)
    embed.timestamp = datetime.datetime.now()
    await ctx.send(embed=embed)

@bot.tree.command(description="Get a user's avatar")
@app_commands.describe(member="The user whose avatar you want")
async def avatar(interaction: discord.Interaction, member: discord.Member = None):
    if member is None:
        member = interaction.user

    embed = discord.Embed(title=f"{member.name}'s Avatar", color=EMBED_COLOR)
    embed.set_image(url=member.avatar.url)
    embed.timestamp = datetime.datetime.now()
    await interaction.response.send_message(embed=embed)

# --- NEW: Admin Commands ---

@bot.command()
@commands.has_permissions(manage_channels=True)
async def lock(ctx, channel: discord.TextChannel = None):
    if channel is None:
        channel = ctx.channel
    
    overwrite = channel.overwrites_for(ctx.guild.default_role)
    overwrite.send_messages = False
    await channel.set_permissions(ctx.guild.default_role, overwrite=overwrite)
    await ctx.send(embed=discord.Embed(title="Channel Locked", description=f"{channel.mention} has been locked.", color=EMBED_COLOR))

@bot.tree.command(description="Lock a channel")
@app_commands.describe(channel="The channel to lock (defaults to current)")
@app_commands.checks.has_permissions(manage_channels=True)
async def lock(interaction: discord.Interaction, channel: discord.TextChannel = None):
    if channel is None:
        channel = interaction.channel

    overwrite = channel.overwrites_for(interaction.guild.default_role)
    overwrite.send_messages = False
    await channel.set_permissions(interaction.guild.default_role, overwrite=overwrite)
    await interaction.response.send_message(embed=discord.Embed(title="Channel Locked", description=f"{channel.mention} has been locked.", color=EMBED_COLOR))

@bot.command()
@commands.has_permissions(manage_channels=True)
async def unlock(ctx, channel: discord.TextChannel = None):
    if channel is None:
        channel = ctx.channel
    
    overwrite = channel.overwrites_for(ctx.guild.default_role)
    overwrite.send_messages = None # Reverts to default
    await channel.set_permissions(ctx.guild.default_role, overwrite=overwrite)
    await ctx.send(embed=discord.Embed(title="Channel Unlocked", description=f"{channel.mention} has been unlocked.", color=EMBED_COLOR))

@bot.tree.command(description="Unlock a channel")
@app_commands.describe(channel="The channel to unlock (defaults to current)")
@app_commands.checks.has_permissions(manage_channels=True)
async def unlock(interaction: discord.Interaction, channel: discord.TextChannel = None):
    if channel is None:
        channel = interaction.channel

    overwrite = channel.overwrites_for(interaction.guild.default_role)
    overwrite.send_messages = None # Reverts to default
    await channel.set_permissions(interaction.guild.default_role, overwrite=overwrite)
    await interaction.response.send_message(embed=discord.Embed(title="Channel Unlocked", description=f"{channel.mention} has been unlocked.", color=EMBED_COLOR))

@bot.command()
@commands.has_permissions(administrator=True)
async def lockdown(ctx, mode: str):
    if mode.lower() not in ['on', 'off']:
        await ctx.send("Invalid mode. Use `on` or `off`.")
        return

    lock_val = False if mode.lower() == 'on' else None
    action = "Locked" if mode.lower() == 'on' else "Unlocked"
    
    embed = discord.Embed(title=f"Server Lockdown {action}", description=f"Please wait, {action.lower()} all channels...", color=EMBED_COLOR)
    msg = await ctx.send(embed=embed)
    
    for channel in ctx.guild.text_channels:
        try:
            overwrite = channel.overwrites_for(ctx.guild.default_role)
            overwrite.send_messages = lock_val
            await channel.set_permissions(ctx.guild.default_role, overwrite=overwrite, reason=f"Lockdown {action} by {ctx.author}")
        except discord.Forbidden:
            continue # Skip channels bot can't edit
            
    embed.description = f"Server {action.lower()} successfully."
    await msg.edit(embed=embed)

@bot.tree.command(description="Lock or unlock all text channels")
@app_commands.describe(mode="Lock 'on' or 'off'?")
@app_commands.choices(mode=[
    app_commands.Choice(name="On (Lock all channels)", value="on"),
    app_commands.Choice(name="Off (Unlock all channels)", value="off"),
])
@app_commands.checks.has_permissions(administrator=True)
async def lockdown(interaction: discord.Interaction, mode: str):
    lock_val = False if mode.lower() == 'on' else None
    action = "Locked" if mode.lower() == 'on' else "Unlocked"

    embed = discord.Embed(title=f"Server Lockdown {action}", description=f"Please wait, {action.lower()} all channels...", color=EMBED_COLOR)
    await interaction.response.send_message(embed=embed)

    for channel in interaction.guild.text_channels:
        try:
            overwrite = channel.overwrites_for(interaction.guild.default_role)
            overwrite.send_messages = lock_val
            await channel.set_permissions(interaction.guild.default_role, overwrite=overwrite, reason=f"Lockdown {action} by {interaction.user}")
        except discord.Forbidden:
            continue

    embed.description = f"Server {action.lower()} successfully."
    await interaction.edit_original_response(embed=embed)

@bot.group(name="ar", invoke_without_command=True)
@commands.has_permissions(manage_roles=True)
async def ar(ctx):
    await ctx.send("Use `?ar set <role>` or `?ar off`.")

@ar.command(name="set")
@commands.has_permissions(manage_roles=True)
async def ar_set(ctx, role: discord.Role):
    if role.position > ctx.guild.me.top_role.position:
        await ctx.send("I cannot manage this role. Please move my bot role higher.")
        return
        
    autorole_config[ctx.guild.id] = role.id
    await ctx.send(embed=discord.Embed(title="Autorole Set", description=f"New members will now get the {role.mention} role.", color=EMBED_COLOR))

@ar.command(name="off")
@commands.has_permissions(manage_roles=True)
async def ar_off(ctx):
    if ctx.guild.id in autorole_config:
        autorole_config.pop(ctx.guild.id)
    await ctx.send(embed=discord.Embed(title="Autorole Off", description="Autorole has been disabled.", color=EMBED_COLOR))
    
@bot.tree.command(description="Configure autorole for new members")
@app_commands.describe(role="The role to give new members (leave blank to disable)")
@app_commands.checks.has_permissions(manage_roles=True)
async def autorole(interaction: discord.Interaction, role: discord.Role = None):
    if role:
        if role.position > interaction.guild.me.top_role.position:
            await interaction.response.send_message("I cannot manage this role. Please move my bot role higher.", ephemeral=True)
            return
        
        autorole_config[interaction.guild.id] = role.id
        await interaction.response.send_message(embed=discord.Embed(title="Autorole Set", description=f"New members will now get the {role.mention} role.", color=EMBED_COLOR))
    else:
        if interaction.guild.id in autorole_config:
            autorole_config.pop(interaction.guild.id)
        await interaction.response.send_message(embed=discord.Embed(title="Autorole Off", description="Autorole has been disabled.", color=EMBED_COLOR))

# --- NEW: Set Status Command ---

@bot.command()
@commands.has_permissions(administrator=True)
async def setstatus(ctx, status: str, *, activity: str = None):
    """Changes the bot's status and activity. (Admin only)"""
    status_map = {
        'online': discord.Status.online,
        'idle': discord.Status.idle,
        'dnd': discord.Status.dnd,
        'invisible': discord.Status.invisible
    }
    
    new_status = status_map.get(status.lower())
    if not new_status:
        await ctx.send("Invalid status. Use 'online', 'idle', 'dnd', or 'invisible'.")
        return

    new_activity = None
    if activity:
        new_activity = discord.Game(name=activity) # You can change discord.Game to .Listening or .Watching

    try:
        await bot.change_presence(status=new_status, activity=new_activity)
        await ctx.send(f"Bot status changed to {status} with activity '{activity or 'none'}'")
    except Exception as e:
        await ctx.send(f"Failed to change status: {e}")

@bot.tree.command(description="Change the bot's status and activity (Admin only)")
@app_commands.describe(status="The status (online, idle, dnd)", activity="The activity text (e.g., 'Watching tickets')")
@app_commands.choices(status=[
    app_commands.Choice(name="Online", value="online"),
    app_commands.Choice(name="Idle", value="idle"),
    app_commands.Choice(name="Do Not Disturb", value="dnd"),
    app_commands.Choice(name="Invisible", value="invisible"),
])
@app_commands.checks.has_permissions(administrator=True)
async def setstatus(interaction: discord.Interaction, status: str, activity: str = None):
    status_map = {
        'online': discord.Status.online,
        'idle': discord.Status.idle,
        'dnd': discord.Status.dnd,
        'invisible': discord.Status.invisible
    }
    
    new_status = status_map.get(status.lower())
    
    new_activity = None
    if activity:
        new_activity = discord.Game(name=activity)

    try:
        await bot.change_presence(status=new_status, activity=new_activity)
        await interaction.response.send_message(f"Bot status changed to {status} with activity '{activity or 'none'}'", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"Failed to change status: {e}", ephemeral=True)

# -----------------------------


# --- Ticket Panel System ---

class TicketView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label="Create Ticket", style=discord.ButtonStyle.primary, custom_id="create_ticket")
    async def create_ticket(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.defer(ephemeral=True) # Defer for channel creation
        guild = interaction.guild
        
        # Check if user already has a ticket
        ticket_name = f"ticket-{interaction.user.name}"
        existing_channel = discord.utils.get(guild.text_channels, name=ticket_name)
        
        if existing_channel:
            await interaction.followup.send("You already have an open ticket!", ephemeral=True)
            return

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)
        }
        
        category = discord.utils.get(guild.categories, name="Tickets")
        if not category:
            try:
                category = await guild.create_category("Tickets")
            except discord.Forbidden:
                await interaction.followup.send("Error: Bot needs 'Manage Channels' permission to create a ticket category.", ephemeral=True)
                return

        try:
            ticket_channel = await guild.create_text_channel(
                ticket_name,
                overwrites=overwrites,
                category=category
            )
        except discord.Forbidden:
            await interaction.followup.send("Error: Bot needs 'Manage Channels' permission to create a ticket.", ephemeral=True)
            return
        
        embed = discord.Embed(
            title="Ticket Opened",
            color=EMBED_COLOR,
            description="Your ticket has been created. A staff member will be with you soon.\nClick the button below to close this ticket."
        )
        # Add a close button to the new ticket channel
        await ticket_channel.send(f"{interaction.user.mention}", embed=embed, view=TicketChannelView())
        await interaction.followup.send(f"Ticket created! Check {ticket_channel.mention}", ephemeral=True)

# --- View with a "Close" button for inside the ticket ---
class TicketChannelView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label="Close Ticket", style=discord.ButtonStyle.danger, custom_id="close_ticket_button")
    async def close_ticket(self, interaction: discord.Interaction, button: ui.Button):
        if "ticket-" in interaction.channel.name:
            await interaction.response.send_message("Closing this ticket...")
            await interaction.channel.delete(reason=f"Ticket closed by {interaction.user}")
        else:
            await interaction.response.send_message("This is not a ticket channel.", ephemeral=True)

    @ui.button(label="Claim Ticket", style=discord.ButtonStyle.success, custom_id="claim_ticket_button")
    async def claim_ticket(self, interaction: discord.Interaction, button: ui.Button):
        # Check if user is staff (e.g., has 'manage_messages' perm)
        if not interaction.user.guild_permissions.manage_messages:
            await interaction.response.send_message("You must be staff to claim a ticket.", ephemeral=True)
            return

        embed = discord.Embed(title="Ticket Claimed", description=f"This ticket has been claimed by {interaction.user.mention}.", color=EMBED_COLOR)
        await interaction.response.send_message(embed=embed)
        
        # Disable the claim button after it's clicked
        button.disabled = True
        button.label = "Claimed"
        await interaction.message.edit(view=self)

    @ui.button(label="Lock Ticket", style=discord.ButtonStyle.secondary, custom_id="lock_ticket_button")
    async def lock_ticket(self, interaction: discord.Interaction, button: ui.Button):
        if not interaction.user.guild_permissions.manage_channels:
            await interaction.response.send_message("You must be staff to lock a ticket.", ephemeral=True)
            return
            
        channel = interaction.channel
        ticket_creator = None

        # Find the ticket creator from channel overwrites
        for target in channel.overwrites:
            if isinstance(target, discord.Member) and target != channel.guild.me:
                # Check if this member is NOT staff (e.g., doesn't have manage_channels)
                if not target.guild_permissions.manage_channels:
                    ticket_creator = target
                    break
        
        if ticket_creator:
             # Make channel read-only for the user who created it
            overwrite = channel.overwrites_for(ticket_creator)
            overwrite.send_messages = False
            await channel.set_permissions(ticket_creator, overwrite=overwrite, reason=f"Ticket locked by {interaction.user}")
        else:
            # Fallback if user not found (maybe they left?)
             await interaction.response.send_message("Could not find ticket creator to lock channel.", ephemeral=True)
             return
        
        embed = discord.Embed(title="Ticket Locked", description=f"This ticket has been locked by {interaction.user.mention}. Only staff can send messages.", color=EMBED_COLOR)
        await interaction.response.send_message(embed=embed)



@bot.command()
@commands.has_permissions(manage_channels=True)
async def ticket(ctx):
    embed = discord.Embed(
        title="Support Tickets",
        description="Need help? Click the button below to open a private ticket with staff.",
        color=EMBED_COLOR
    )
    await ctx.send(embed=embed, view=TicketView())

@bot.tree.command(description="Send the ticket panel")
@app_commands.checks.has_permissions(manage_channels=True)
async def ticket(interaction: discord.Interaction):
    embed = discord.Embed(
        title="Support Tickets",
        description="Need help? Click the button below to open a private ticket with staff.",
        color=EMBED_COLOR
    )
    await interaction.response.send_message(embed=embed, view=TicketView())

@bot.command()
async def close(ctx):
    if "ticket-" in ctx.channel.name:
        await ctx.channel.delete(reason=f"Ticket closed by {ctx.author}")
    else:
        await ctx.send("This is not a ticket channel.")


@bot.tree.command(description="Close a ticket")
async def close(interaction: discord.Interaction):
    if "ticket-" in interaction.channel.name:
        await interaction.response.send_message("Closing this ticket...")
        await interaction.channel.delete(reason=f"Ticket closed by {interaction.user}")
    else:
        await interaction.response.send_message("This is not a ticket channel.", ephemeral=True)

# --- Ready Event (syncs slash commands) ---

@bot.event
async def on_ready():
    bot.remove_command("help") # <-- Remove default help command
    # You only need to sync once, then you can comment this out.
    # Add the persistent view *before* the bot runs
    bot.add_view(TicketView())
    bot.add_view(TicketChannelView())
    # Leaving it un-commented is fine, but can be slow.
    await bot.tree.sync() 
    print(f"Bot connected as {bot.user}")

# --- NEW: Autorole Event ---
@bot.event
async def on_member_join(member):
    role_id = autorole_config.get(member.guild.id)
    if not role_id:
        return # No autorole set for this server
        
    role = member.guild.get_role(role_id)
    if role:
        try:
            await member.add_roles(role, reason="Autorole")
        except discord.Forbidden:
            print(f"Failed to add autorole in {member.guild.name}: Bot lacks permissions.")
        except Exception as e:
            print(f"Error during autorole: {e}")

# --- ADMIN-ONLY EMBED CREATOR ---

class EmbedModal(ui.Modal, title="Admin Embed Creator"):
    # Define the inputs for the pop-up window
    embed_title = ui.TextInput(label="Title", placeholder="Enter the heading here...", required=True)
    description = ui.TextInput(label="Description", style=discord.TextStyle.paragraph, placeholder="Enter your message here...", required=True, max_length=2000)
    image_url = ui.TextInput(label="Image URL", placeholder="Optional: https://link-to-image.png", required=False)
    footer = ui.TextInput(label="Footer", placeholder="Optional: Small text at the bottom", required=False)

    async def on_submit(self, interaction: discord.Interaction):
        # Create the embed using the inputs
        embed = discord.Embed(
            title=self.embed_title.value,
            description=self.description.value,
            color=EMBED_COLOR,
            timestamp=datetime.datetime.now()
        )
        
        if self.image_url.value:
            if self.image_url.value.startswith("http"):
                embed.set_image(url=self.image_url.value)
        
        if self.footer.value:
            embed.set_footer(text=self.footer.value)

        await interaction.response.send_message("✅ Admin embed sent!", ephemeral=True)
        await interaction.channel.send(embed=embed)

@bot.tree.command(description="Send a custom embed (Admin Only)")
@app_commands.checks.has_permissions(administrator=True) # <-- Changed to Administrator
async def embed(interaction: discord.Interaction):
    """Opens a form to create and send an embed - Only for Admins"""
    await interaction.response.send_modal(EmbedModal())

# Optional: Adding an error handler so the user gets a message if they aren't an admin
@embed.error
async def embed_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message("❌ You do not have **Administrator** permissions to use this command.", ephemeral=True)

# -----------------------------
# --- RUN THE BOT AND SERVER ---
if __name__ == "__main__":
    if TOKEN is None:
        print("Error: TOKEN environment variable not set.")
        print("Make sure you have a .env file or set it in your host's environment variables.")
    else:
        keep_alive() # Start the web server thread
        bot.run(TOKEN) # Start the bot.

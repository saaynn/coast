
import discord
from discord.ext import commands
from discord import app_commands, ui
import os
from dotenv import load_dotenv

# --- IMPORTS FOR RENDER KEEP-ALIVE ---
from flask import Flask
from threading import Thread
# -------------------------------------

load_dotenv()
TOKEN = os.getenv("TOKEN")

INTENTS = discord.Intents.default()
INTENTS.message_content = True
INTENTS.members = True

EMBED_COLOR = 0x00ff00

bot = commands.Bot(command_prefix="?", intents=INTENTS)

# --- WEB SERVER FOR RENDER KEEP-ALIVE ---
app = Flask('')

@app.route('/')
def home():
    return "I'm alive!" # This is what UptimeRobot will see

def run():
  # Render uses port 8080, but can also auto-assign with PORT env var
  port = int(os.environ.get('PORT', 8080))
  app.run(host='0.0.0.0', port=port)

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

@bot.command()
@commands.has_permissions(moderate_members=True)
async def mute(ctx, member: discord.Member, duration: int = 10):
    await member.edit(timeout=discord.utils.utcnow() + discord.timedelta(minutes=duration))
    embed = discord.Embed(title="User Muted", description=f"{member.mention} muted for {duration} minutes.", color=EMBED_COLOR)
    await ctx.send(embed=embed)

@bot.tree.command(description="Mute a member")
@app_commands.describe(member="User to mute", duration="Mute duration (minutes)")
@app_commands.checks.has_permissions(moderate_members=True)
async def mute(interaction: discord.Interaction, member: discord.Member, duration: int = 10):
    await member.edit(timeout=discord.utils.utcnow() + discord.timedelta(minutes=duration))
    embed = discord.Embed(title="User Muted", description=f"{member.mention} muted for {duration} minutes.", color=EMBED_COLOR)
    await interaction.response.send_message(embed=embed)

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
    embed = discord.Embed(title="User Unmuted", description=f"{member.mention} is no longer muted.", color=EMBED_COLOR)
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
        await ticket_channel.send(f"{interaction.user.mention}", embed=embed, view=CloseTicketView())
        await interaction.followup.send(f"Ticket created! Check {ticket_channel.mention}", ephemeral=True)

# --- View with a "Close" button for inside the ticket ---
class CloseTicketView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label="Close Ticket", style=discord.ButtonStyle.danger, custom_id="close_ticket_button")
    async def close_ticket(self, interaction: discord.Interaction, button: ui.Button):
        if "ticket-" in interaction.channel.name:
            await interaction.response.send_message("Closing this ticket...")
            await interaction.channel.delete(reason=f"Ticket closed by {interaction.user}")
        else:
            await interaction.response.send_message("This is not a ticket channel.", ephemeral=True)



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
    # You only need to sync once, then you can comment this out.
    # Add the persistent view *before* the bot runs
    bot.add_view(TicketView())
    bot.add_view(CloseTicketView())
    # Leaving it un-commented is fine, but can be slow.
    await bot.tree.sync() 
    print(f"Bot connected as {bot.user}")

# --- RUN THE BOT AND SERVER ---
if __name__ == "__main__":
    if TOKEN is None:
        print("Error: TOKEN environment variable not set.")
        print("Make sure you have a .env file or set it in your host's environment variables.")
    else:
        keep_alive() # Start the web server thread
        bot.run(TOKEN) # Start the bot

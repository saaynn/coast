
import discord
from discord.ext import commands
from discord import app_commands, ui
import os
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("TOKEN")

INTENTS = discord.Intents.default()
INTENTS.message_content = True
INTENTS.members = True

EMBED_COLOR = 0x00ff00

bot = commands.Bot(command_prefix="?", intents=INTENTS)

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
    await interaction.channel.purge(limit=amount+1)
    embed = discord.Embed(title="Messages Cleared", color=EMBED_COLOR, description=f"{amount} messages deleted.")
    await interaction.response.send_message(embed=embed, ephemeral=True)

# --- Ticket Panel System ---

class TicketView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label="Create Ticket", style=discord.ButtonStyle.primary, custom_id="create_ticket")
    async def create_ticket(self, interaction: discord.Interaction, button: ui.Button):
        guild = interaction.guild
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True)
        }
        category = discord.utils.get(guild.categories, name="Tickets")
        if not category:
            category = await guild.create_category("Tickets")
        ticket_channel = await guild.create_text_channel(f"ticket-{interaction.user.name}", overwrites=overwrites, category=category)

        embed = discord.Embed(
            title="Ticket Opened",
            color=EMBED_COLOR,
            description="Your ticket has been created. A staff member will be with you soon."
        )
        await ticket_channel.send(f"{interaction.user.mention}", embed=embed)
        await interaction.response.send_message("Ticket created! Check your new channel.", ephemeral=True)

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
        await ctx.channel.delete()

@bot.tree.command(description="Close a ticket")
async def close(interaction: discord.Interaction):
    if "ticket-" in interaction.channel.name:
        await interaction.channel.delete()
    else:
        await interaction.response.send_message("This is not a ticket channel.", ephemeral=True)

# --- Ready Event (syncs slash commands) ---

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"Bot connected as {bot.user}")

bot.run(TOKEN)

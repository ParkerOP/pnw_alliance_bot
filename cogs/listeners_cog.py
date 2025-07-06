# cogs/listeners_cog.py
import discord
from discord.ext import commands
import sys
import traceback

class ListenersCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, error: commands.CommandError):
        """A global error handler for all commands."""
        
        if hasattr(ctx.command, 'on_error'):
            # If the command has its own error handler, let it handle it.
            return

        # Get the original exception
        error = getattr(error, 'original', error)

        if isinstance(error, commands.CommandNotFound):
            # Silently ignore commands that don't exist
            return
        
        elif isinstance(error, commands.MissingPermissions):
            await ctx.send(f"⛔ You don't have permission to use the `{ctx.command.name}` command.")

        elif isinstance(error, commands.MissingRequiredArgument):
            # Provides the user with the correct command usage
            await ctx.send(f"🤔 You're missing an argument. Correct usage: `{ctx.prefix}{ctx.command.qualified_name} {ctx.command.signature}`")

        elif isinstance(error, (commands.BadArgument, commands.MemberNotFound, commands.RoleNotFound, commands.ChannelNotFound)):
            await ctx.send(f"⚠️ I couldn't find what you were looking for. Please check your spelling and try again.")
        
        elif isinstance(error, discord.Forbidden):
            await ctx.send(f"❌ **Permissions Error:** I don't have the necessary permissions to do that. Please check my role hierarchy and permissions.")

        else:
            # For all other errors, log them to the console
            print(f"Ignoring exception in command {ctx.command}:", file=sys.stderr)
            traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)
            await ctx.send("😬 An unexpected error occurred. I've logged the details for my developer.")


async def setup(bot):
    await bot.add_cog(ListenersCog(bot))
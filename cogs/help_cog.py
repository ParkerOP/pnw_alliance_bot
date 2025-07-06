# cogs/help_cog.py

import discord

from discord.ext import commands

import difflib # Used for the "did you mean?" feature

class HelpCog(commands.Cog, name="Help"):

    """A robust, dynamic, and context-aware help command."""

    def __init__(self, bot: commands.Bot):

        self.bot = bot

        # Cogs to hide from the main help menu

        self.hidden_cogs = ["Help", "ListenersCog"]

    async def send_cog_help(self, ctx: commands.Context, cog: commands.Cog):

        """Sends a detailed embed for a specific cog/category."""

        embed = discord.Embed(

            title=f"Category: {cog.qualified_name}",

            description=cog.description or "No description provided for this category.",

            color=discord.Color.blue()

        )

        embed.set_author(name=self.bot.user.name, icon_url=self.bot.user.avatar.url)

        # Filter commands to only show ones the user can run

        cog_commands = cog.get_commands()

        walkable_commands = await self.filter_commands(cog_commands, ctx)

        

        if not walkable_commands:

            embed.add_field(name="No Commands Found", value="You don't have permission to run any commands in this category.")

        else:

            for command in walkable_commands:

                embed.add_field(

                    name=f"`{ctx.prefix}{command.name} {command.signature}`",

                    value=command.brief or command.help or "No description provided.",

                    inline=False

                )

        

        await ctx.send(embed=embed)

    async def send_command_help(self, ctx: commands.Context, command: commands.Command):

        """Sends a detailed embed for a specific command."""

        embed = discord.Embed(

            title=f"Command: {command.name}",

            description=command.help or "No description provided.",

            color=discord.Color.green()

        )

        embed.set_author(name=self.bot.user.name, icon_url=self.bot.user.avatar.url)

        # Add usage/syntax

        usage = f"`{ctx.prefix}{command.qualified_name} {command.signature}`"

        embed.add_field(name="Usage", value=usage, inline=False)

        

        # Add aliases if they exist

        if command.aliases:

            alias_str = ", ".join([f"`{alias}`" for alias in command.aliases])

            embed.add_field(name="Aliases", value=alias_str, inline=False)

        

        await ctx.send(embed=embed)

    async def filter_commands(self, commands_to_filter, ctx):

        """

        Helper function to filter a list of commands, returning only the ones a user can run.

        This is the core of the context-aware functionality.

        """

        walkable = []

        for command in commands_to_filter:

            if command.hidden:

                continue

            try:

                if await command.can_run(ctx):

                    walkable.append(command)

            except commands.CommandError:

                continue

        return walkable

    @commands.command(name="help")

    async def help(self, ctx: commands.Context, *, query: str = None):

        """The main help command. Shows all commands, or details for a specific command/category."""

        if query is None:

            # --- Main Help Embed (No Query) ---

            embed = discord.Embed(

                title="Bot Help Menu",

                description=f"Use `{ctx.prefix}help [category]` or `{ctx.prefix}help [command]` for more details.",

                color=discord.Color.blurple()

            )

            embed.set_author(name=self.bot.user.name, icon_url=self.bot.user.avatar.url)

            

            # Get commands filtered by user's permissions for each cog

            for cog_name, cog in self.bot.cogs.items():

                if cog_name in self.hidden_cogs:

                    continue

                

                walkable_commands = await self.filter_commands(cog.get_commands(), ctx)

                if walkable_commands:

                    command_list = " ".join([f"`{c.name}`" for c in walkable_commands])

                    embed.add_field(name=cog_name, value=command_list, inline=False)

            await ctx.send(embed=embed)

            return

        # --- Specific Help (Query Provided) ---

        

        # Check if the query is a command

        if (command := self.bot.get_command(query.lower())):

            await self.send_command_help(ctx, command)

            return

            

        # Check if the query is a cog/category

        for cog_name, cog in self.bot.cogs.items():

            if query.lower() == cog_name.lower():

                await self.send_cog_help(ctx, cog)

                return

        # --- "Did you mean?" Feature ---

        all_command_names = [cmd.name for cmd in self.bot.commands if not cmd.hidden]

        

        # Find the best match for the user's query

        best_match = difflib.get_close_matches(query, all_command_names, n=1, cutoff=0.6)

        

        if best_match:

            suggestion = best_match[0]

            await ctx.send(f"❌ Command not found. Did you mean `{ctx.prefix}{suggestion}`?")

        else:

            await ctx.send(f"❌ Command or category not found. Use `{ctx.prefix}help` to see a list of all available categories.")

async def setup(bot):

    await bot.add_cog(HelpCog(bot))
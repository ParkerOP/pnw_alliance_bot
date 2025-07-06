# cogs/config_cog.py
import discord
from discord.ext import commands
import json

class ConfigCog(commands.Cog):
    """
    Handles all bot configuration and the initial setup of the database.
    This cog creates all necessary tables for all bot features on its first run.
    """
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # This task runs in the background to set up the database when the cog loads.
        self.bot.loop.create_task(self.setup_database())

    async def setup_database(self):
        """
        The master database setup function.
        Creates all tables required for the entire bot's functionality from scratch.
        Uses 'IF NOT EXISTS' to be safe on subsequent runs, but is designed for a fresh start.
        """
        async with self.bot.db.cursor() as cursor:
            # --- CORE TABLES ---
            
            # 1. Members Table: The central table for all user-specific stats.
            # This is the corrected version that includes all columns from the start.
            await cursor.execute("""
                CREATE TABLE IF NOT EXISTS members (
                    user_id INTEGER PRIMARY KEY,
                    join_date TEXT NOT NULL,
                    participation_count INTEGER DEFAULT 0,
                    host_count INTEGER DEFAULT 0
                )
            """)
            
            # 2. Settings Table: For simple key-value configurations like channel IDs.
            await cursor.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            """)
            
            # 3. Activity Log Table: Stores a record of every message for cyclical awards.
            await cursor.execute("""
                CREATE TABLE IF NOT EXISTS activity_log (
                    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    channel_id INTEGER NOT NULL,
                    category_id INTEGER,
                    timestamp TEXT NOT NULL
                )
            """)

            # --- FEATURE-SPECIFIC CONFIGURATION TABLES ---
            
            # 4. Tenure Roles Table: For seniority-based role awards.
            await cursor.execute("""
                CREATE TABLE IF NOT EXISTS tenure_roles (
                    days INTEGER PRIMARY KEY,
                    role_id INTEGER NOT NULL
                )
            """)

            # 5. Participation Roles Table: For event participation milestone awards.
            await cursor.execute("""
                CREATE TABLE IF NOT EXISTS participation_roles (
                    count INTEGER PRIMARY KEY,
                    role_id INTEGER NOT NULL
                )
            """)
            
            # 6. Award Configs Table: Defines the rules for cyclical awards.
            await cursor.execute("""
                CREATE TABLE IF NOT EXISTS award_configs (
                    award_name TEXT PRIMARY KEY,
                    award_type TEXT NOT NULL,
                    frequency TEXT NOT NULL,
                    role_id INTEGER NOT NULL,
                    target_id INTEGER 
                )
            """)
            
            # 7. Active Events Table: Tracks events that have been created but not closed.
            await cursor.execute("""
                CREATE TABLE IF NOT EXISTS active_events (
                    message_id INTEGER PRIMARY KEY,
                    host_id INTEGER NOT NULL,
                    title TEXT NOT NULL
                )
            """)
            
        await self.bot.db.commit()
        print("Database tables verified/created for all cogs.")

    # --- Utility Configuration Commands ---

    @commands.command(name="config-logchannel", brief="Sets the bot's logging channel.",

    help="Sets the private text channel where the bot will post detailed action logs, such as when roles are awarded or errors occur.")
    @commands.has_permissions(administrator=True)
    async def config_logchannel(self, ctx, channel: discord.TextChannel):
        """Sets the channel where the bot will post detailed action logs."""
        async with self.bot.db.cursor() as cursor:
            await cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", 
                                 ('log_channel_id', str(channel.id)))
        await self.bot.db.commit()
        await ctx.send(f"✅ Log channel has been set to {channel.mention}")

    @commands.command(name="config-announcements", brief="Sets the award announcements channel.",

    help="Sets the public channel where the bot will post the results of cyclical award cycles (e.g., Member of the Month).")
    @commands.has_permissions(administrator=True)
    async def config_announcements(self, ctx, channel: discord.TextChannel):
        """Sets the channel for award cycle announcements."""
        async with self.bot.db.cursor() as cursor:
            await cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", 
                                 ('announcement_channel_id', str(channel.id)))
        await self.bot.db.commit()
        await ctx.send(f"✅ Award announcement channel has been set to {channel.mention}")

    # --- `!accept` Command Configuration ---

    @commands.group(name="config-accept", brief="Configures the !accept command.",

    help="A group of commands for configuring which roles are added and removed when a new member is accepted with !accept." , invoke_without_command=True)
    @commands.has_permissions(administrator=True)
    async def config_accept(self, ctx):
        """Shows the current role configuration for the !accept command."""
        async with self.bot.db.cursor() as cursor:
            await cursor.execute("SELECT value FROM settings WHERE key = ?", ('accept_add_roles',))
            add_res = await cursor.fetchone()
            await cursor.execute("SELECT value FROM settings WHERE key = ?", ('accept_remove_roles',))
            remove_res = await cursor.fetchone()
        
        add_roles_ids = json.loads(add_res[0]) if add_res else []
        remove_roles_ids = json.loads(remove_res[0]) if remove_res else []
        
        add_mentions = [f"<@&{role_id}>" for role_id in add_roles_ids if ctx.guild.get_role(role_id)]
        remove_mentions = [f"<@&{role_id}>" for role_id in remove_roles_ids if ctx.guild.get_role(role_id)]

        embed = discord.Embed(title="`!accept` Command Configuration", color=discord.Color.blue())
        embed.add_field(name="Roles to Add", value=', '.join(add_mentions) if add_mentions else "None Configured", inline=False)
        embed.add_field(name="Roles to Remove", value=', '.join(remove_mentions) if remove_mentions else "None Configured", inline=False)
        await ctx.send(embed=embed)

    @config_accept.command(name="add", brief="Adds a role to give on !accept.",

    help="Specifies a role that will be GIVEN to a user when they are targeted by the !accept command.")
    @commands.has_permissions(administrator=True)
    async def accept_add(self, ctx, role: discord.Role):
        """Adds a role to be GIVEN on !accept."""
        async with self.bot.db.cursor() as cursor:
            await cursor.execute("SELECT value FROM settings WHERE key = ?", ('accept_add_roles',))
            result = await cursor.fetchone()
            roles = json.loads(result[0]) if result else []
            if role.id not in roles:
                roles.append(role.id)
                await cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", ('accept_add_roles', json.dumps(roles)))
                await self.bot.db.commit()
                await ctx.send(f"✅ {role.mention} will now be **added** on `!accept`.")
            else:
                await ctx.send(f"⚠️ {role.mention} is already in the 'add' list.")
    
    @config_accept.command(name="remove", brief="Adds a role to remove on !accept.",

    help="Specifies a role that will be REMOVED from a user when they are targeted by the !accept command.")
    @commands.has_permissions(administrator=True)
    async def accept_remove(self, ctx, role: discord.Role):
        """Adds a role to be REMOVED on !accept."""
        async with self.bot.db.cursor() as cursor:
            await cursor.execute("SELECT value FROM settings WHERE key = ?", ('accept_remove_roles',))
            result = await cursor.fetchone()
            roles = json.loads(result[0]) if result else []
            if role.id not in roles:
                roles.append(role.id)
                await cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", ('accept_remove_roles', json.dumps(roles)))
                await self.bot.db.commit()
                await ctx.send(f"✅ {role.mention} will now be **removed** on `!accept`.")
            else:
                await ctx.send(f"⚠️ {role.mention} is already in the 'remove' list.")

    # --- Tenure Role Configuration ---

    @commands.group(name="config-tenure", brief="Configures tenure (seniority) roles.",

    help="A group of commands for managing roles awarded based on how long a member has been in the alliance." ,invoke_without_command=True)
    @commands.has_permissions(administrator=True)
    async def config_tenure(self, ctx):
        """Lists the current tenure milestone roles."""
        embed = discord.Embed(title="Tenure Milestone Roles", color=discord.Color.gold())
        async with self.bot.db.cursor() as cursor:
            await cursor.execute("SELECT days, role_id FROM tenure_roles ORDER BY days ASC")
            rows = await cursor.fetchall()
            if not rows:
                embed.description = "No tenure roles configured.\nUse `!config-tenure set <days> <@role>` to add one."
            else:
                for days, role_id in rows:
                    role = ctx.guild.get_role(role_id)
                    embed.add_field(name=f"{days} Days", value=role.mention if role else f"Deleted Role (ID: {role_id})", inline=False)
        await ctx.send(embed=embed)

    @config_tenure.command(name="set", brief="Sets a tenure role for a milestone.",

    help="Creates a milestone. When a member's tenure reaches the specified number of days, they will be awarded the specified role." )
    @commands.has_permissions(administrator=True)
    async def tenure_set(self, ctx, days: int, role: discord.Role):
        """Sets a role for a tenure milestone (e.g., 100 days)."""
        async with self.bot.db.cursor() as cursor:
            await cursor.execute("INSERT OR REPLACE INTO tenure_roles (days, role_id) VALUES (?, ?)", (days, role.id))
        await self.bot.db.commit()
        await ctx.send(f"✅ Tenure role for **{days} days** set to {role.mention}.")
        
       
    @config_tenure.command(name="set-qualifier", brief="Sets the role required for tenure.",

    help="Sets a single role (e.g., @Alliance Member) that a user must have to be eligible for tenure awards. This prevents non-members from getting seniority roles.")

    @commands.has_permissions(administrator=True)

    async def tenure_set_qualifier(self, ctx, role: discord.Role):

        """Sets the single role a member must have to be eligible for tenure."""

        async with self.bot.db.cursor() as cursor:

            await cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", 

                                 ('tenure_qualifying_role_id', str(role.id)))

        await self.bot.db.commit()

        await ctx.send(f"✅ Done. Tenure checks will now only apply to members with the {role.mention} role.")

    @config_tenure.command(name="clear-qualifier", brief="Removes the tenure qualifier role.",

    help="Clears the qualifying role requirement, making all members in the database eligible for tenure awards again.")

    @commands.has_permissions(administrator=True)

    async def tenure_clear_qualifier(self, ctx):

        """Removes the qualifying role requirement. All members become eligible again."""

        async with self.bot.db.cursor() as cursor:

            await cursor.execute("DELETE FROM settings WHERE key = ?", ('tenure_qualifying_role_id',))

        await self.bot.db.commit()

        await ctx.send("✅ Done. The tenure qualifying role has been cleared. All members in the database are now eligible.")
    # --- Participation Role Configuration ---

    @commands.group(name="config-participation", brief="Configures event participation roles.",

    help="A group of commands for managing permanent roles awarded for attending a certain number of alliance events." , invoke_without_command=True)
    @commands.has_permissions(administrator=True)
    async def config_participation(self, ctx):
        """Lists the current participation milestone roles."""
        embed = discord.Embed(title="Event Participation Milestone Roles", color=discord.Color.green())
        async with self.bot.db.cursor() as cursor:
            await cursor.execute("SELECT count, role_id FROM participation_roles ORDER BY count ASC")
            rows = await cursor.fetchall()
            if not rows:
                embed.description = "No participation roles configured.\nUse `!config-participation set <count> <@role>` to add one."
            else:
                for count, role_id in rows:
                    role = ctx.guild.get_role(role_id)
                    embed.add_field(name=f"{count} Events Attended", value=role.mention if role else f"Deleted Role (ID: {role_id})", inline=False)
        await ctx.send(embed=embed)

    @config_participation.command(name="set", brief="Sets a participation role for a milestone.",

    help="Creates a milestone. When a member has participated in the specified number of events, they will be awarded the specified role.")
    @commands.has_permissions(administrator=True)
    async def participation_set(self, ctx, count: int, role: discord.Role):
        """Sets a role for an event participation milestone."""
        async with self.bot.db.cursor() as cursor:
            await cursor.execute("INSERT OR REPLACE INTO participation_roles (count, role_id) VALUES (?, ?)", (count, role.id))
        await self.bot.db.commit()
        await ctx.send(f"✅ Participation role for **{count} events** set to {role.mention}.")

    # --- Cyclical Award Configuration ---

    @commands.group(name="config-award", brief="Configures cyclical (e.g., monthly) awards.",

    help="A group of commands for creating and managing temporary, competitive awards like Member of the Month.", invoke_without_command=True)
    @commands.has_permissions(administrator=True)
    async def config_award(self, ctx):
        """Lists all configured cyclical awards."""
        embed = discord.Embed(title="Cyclical Award Configurations", color=discord.Color.purple())
        async with self.bot.db.cursor() as cursor:
            await cursor.execute("SELECT award_name, award_type, frequency, role_id, target_id FROM award_configs")
            rows = await cursor.fetchall()
            if not rows:
                embed.description = "No awards configured.\nUse `!config-award create ...` to add one."
            else:
                for name, type, freq, role_id, target_id in rows:
                    role = ctx.guild.get_role(role_id)
                    target_str = ""
                    if target_id:
                        target_obj = ctx.guild.get_channel(target_id)
                        target_mention = target_obj.mention if isinstance(target_obj, discord.TextChannel) else f"**{target_obj.name}**"
                        target_str = f" in {target_mention}" if target_obj else f" in Invalid Channel/Category"
                    
                    embed.add_field(
                        name=f"`{name}` ({freq.capitalize()})",
                        value=f"**Type:** {type.capitalize()}{target_str}\n**Role:** {role.mention if role else 'Deleted Role'}",
                        inline=False
                    )
        await ctx.send(embed=embed)

    @config_award.command(name="create", brief="Creates a new cyclical award.",

    help="Creates a new award rule. Example: `!config-award create motm server monthly @MostActive` to create a Member of the Month award based on server-wide activity.")
    @commands.has_permissions(administrator=True)
    async def award_create(self, ctx, award_name: str, award_type: str, frequency: str, role: discord.Role, target: discord.abc.GuildChannel = None):
        """
        Creates a new cyclical award.
        Types: server, channel, category
        Frequencies: monthly, quarterly
        Target: Required for channel/category type.
        """
        award_type = award_type.lower()
        frequency = frequency.lower()
        if award_type not in ['server', 'channel', 'category']:
            return await ctx.send("❌ Invalid award type. Must be `server`, `channel`, or `category`.")
        if frequency not in ['monthly', 'quarterly']:
            return await ctx.send("❌ Invalid frequency. Must be `monthly` or `quarterly`.")
        if award_type in ['channel', 'category'] and not target:
            return await ctx.send(f"❌ The `{award_type}` type requires a target channel or category.")
        
        target_id = target.id if target else None

        async with self.bot.db.cursor() as cursor:
            await cursor.execute("INSERT OR REPLACE INTO award_configs (award_name, award_type, frequency, role_id, target_id) VALUES (?, ?, ?, ?, ?)",
                                 (award_name, award_type, frequency, role.id, target_id))
        await self.bot.db.commit()
        await ctx.send(f"✅ Award `{award_name}` created successfully!")

# This function is required for the bot to load the cog.
async def setup(bot):
    await bot.add_cog(ConfigCog(bot))
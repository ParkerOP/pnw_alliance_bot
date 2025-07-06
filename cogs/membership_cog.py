# cogs/membership_cog.py (Updated with Sync and SetDate commands)
import discord
from discord.ext import commands, tasks
from datetime import datetime, timezone
import json

class MembershipCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # The database setup is now handled by the ConfigCog, so we don't need it here.
        # Start the background task to check tenure
        self.tenure_check.start()

    async def log_action(self, message: str):
        """Helper function to send a message to the configured log channel."""
        async with self.bot.db.cursor() as cursor:
            await cursor.execute("SELECT value FROM settings WHERE key = ?", ('log_channel_id',))
            result = await cursor.fetchone()
        if result:
            channel_id = int(result[0])
            log_channel = self.bot.get_channel(channel_id)
            if log_channel:
                await log_channel.send(f"[`{datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}`] {message}")

    @commands.command(name="accept",
                     brief="Accepts new members into the alliance.", # This shows up in category lists

    help="Accepts one or more new members, applying configured roles and recording their join date for tenure tracking." )
    @commands.has_permissions(manage_roles=True)
    async def accept(self, ctx, members: commands.Greedy[discord.Member]):
        """Accepts one or more new members, updating roles and tracking their join date."""
        if not members:
            return await ctx.send("Please mention at least one member to accept.")

        # Get configured roles from DB
        async with self.bot.db.cursor() as cursor:
            await cursor.execute("SELECT value FROM settings WHERE key = 'accept_add_roles'")
            add_roles_res = await cursor.fetchone()
            await cursor.execute("SELECT value FROM settings WHERE key = 'accept_remove_roles'")
            remove_roles_res = await cursor.fetchone()

        add_role_ids = json.loads(add_roles_res[0]) if add_roles_res else []
        remove_role_ids = json.loads(remove_roles_res[0]) if remove_roles_res else []

        roles_to_add = [ctx.guild.get_role(rid) for rid in add_role_ids if ctx.guild.get_role(rid)]
        roles_to_remove = [ctx.guild.get_role(rid) for rid in remove_role_ids if ctx.guild.get_role(rid)]
        
        accepted_members = []
        failed_members = []

        for member in members:
            try:
                # Perform role changes
                await member.add_roles(*roles_to_add, reason=f"Accepted by {ctx.author}")
                await member.remove_roles(*roles_to_remove, reason=f"Accepted by {ctx.author}")

                # Record their official join date in the database
                join_timestamp = datetime.utcnow().isoformat()
                async with self.bot.db.cursor() as cursor:
                    # Use INSERT OR REPLACE to handle cases where a member might already exist from a sync
                    await cursor.execute("""
                        INSERT OR REPLACE INTO members (user_id, join_date, participation_count, host_count)
                        VALUES (?, ?, (SELECT participation_count FROM members WHERE user_id = ?), (SELECT host_count FROM members WHERE user_id = ?))
                    """, (member.id, join_timestamp, member.id, member.id))
                
                accepted_members.append(member.mention)
            except discord.Forbidden:
                failed_members.append(f"{member.mention} (Missing Permissions)")
            except Exception as e:
                failed_members.append(f"{member.mention} (Error: {e})")
        
        await self.bot.db.commit()

        if accepted_members:
            await ctx.send(f"✅ Successfully accepted: {', '.join(accepted_members)}. Welcome to the alliance!")
            await self.log_action(f"**Accept**: {ctx.author.mention} accepted {', '.join(accepted_members)}.")
        if failed_members:
            await ctx.send(f"❌ Failed to accept: {', '.join(failed_members)}.")

    # --- NEW COMMANDS FOR BACKFILLING DATA ---

    @commands.command(name="sync-members", brief="(Admin) Backfills the database with all server members.",

    help="A one-time utility to add all existing server members to the bot's database. It uses their Discord server join date as a default, which can be corrected with `!set-joindate`. This will not overwrite existing entries.")
    @commands.has_permissions(administrator=True)
    async def sync_members(self, ctx):
        """
        (Run Once) Backfills the database with existing server members.
        Uses their server join date as a default. Will not overwrite existing entries.
        """
        await ctx.send("⚙️ Starting member synchronization... This may take a moment for a large server.")
        
        # Get all user IDs already in our database
        async with self.bot.db.cursor() as cursor:
            await cursor.execute("SELECT user_id FROM members")
            existing_member_ids = {row[0] for row in await cursor.fetchall()}
        
        all_server_members = ctx.guild.members
        new_members_to_add = []
        
        for member in all_server_members:
            # Skip bots and members who are already in the database
            if member.bot or member.id in existing_member_ids:
                continue
            
            # Use the server join date as the default join date
            join_date_iso = member.joined_at.isoformat()
            new_members_to_add.append((member.id, join_date_iso, 0, 0))

        if not new_members_to_add:
            return await ctx.send("✅ Synchronization complete. No new members needed to be added to the database.")

        # Use executemany for a highly efficient bulk insert
        async with self.bot.db.cursor() as cursor:
            await cursor.executemany(
                "INSERT INTO members (user_id, join_date, participation_count, host_count) VALUES (?, ?, ?, ?)",
                new_members_to_add
            )
        await self.bot.db.commit()

        await ctx.send(f"✅ Synchronization complete! Added **{len(new_members_to_add)}** new members to the database.")
        await self.log_action(f"**Member Sync**: {ctx.author.mention} ran a sync, adding {len(new_members_to_add)} members.")

    @commands.command(name="set-joindate", brief="(Admin) Manually sets a member's join date.",

    help="Manually sets or corrects a member's official alliance join date, which is used for calculating tenure. This is useful for correcting dates after a `!sync-members`.")
    @commands.has_permissions(administrator=True)
    async def set_joindate(self, ctx, member: discord.Member, date_str: str):
        """
        Manually sets or corrects a member's official join date.
        Format: YYYY-MM-DD
        """
        try:
            # Parse the date string and add a default time to make it a datetime object
            # This makes it compatible with how we store other dates
            join_date = datetime.fromisoformat(date_str + "T00:00:00")
        except ValueError:
            return await ctx.send("❌ Invalid date format. Please use `YYYY-MM-DD` (e.g., `2023-05-21`).")

        async with self.bot.db.cursor() as cursor:
            # INSERT OR REPLACE is perfect here. It creates if not present, updates if present.
            await cursor.execute("""
                INSERT OR REPLACE INTO members (user_id, join_date, participation_count, host_count)
                VALUES (?, ?, 
                    COALESCE((SELECT participation_count FROM members WHERE user_id = ?), 0), 
                    COALESCE((SELECT host_count FROM members WHERE user_id = ?), 0)
                )
            """, (member.id, join_date.isoformat(), member.id, member.id))
        await self.bot.db.commit()

        await ctx.send(f"✅ Successfully set {member.mention}'s join date to **{date_str}**.")
        await self.log_action(f"**Date Set**: {ctx.author.mention} manually set {member.mention}'s join date to {date_str}.")


    @commands.command(name="check-tenure", brief="(Admin) Manually triggers the tenure check.",

    help="Manually runs the same process that automatically runs every 24 hours to check for and award tenure roles to all eligible members.")

    @commands.has_permissions(administrator=True)

    async def manual_tenure_check(self, ctx):

        """Manually triggers the daily tenure check for all qualified members."""

        await ctx.send("⚙️ Manually starting the tenure check... This may take a moment.")

        # We directly call the background task's function

        await self.tenure_check.coro(self)

        await ctx.send("✅ Manual tenure check complete. See the log channel for details on any roles awarded.")

    # --- UPDATED BACKGROUND TASK ---

    @tasks.loop(hours=24)

    async def tenure_check(self):

        """Checks daily for members who have reached a tenure milestone."""

        await self.bot.wait_until_ready()

        print("Running daily tenure check...")

        guild = self.bot.guilds[0]

        if not guild: return

        # NEW: Fetch the qualifying role ID from the database

        qualifying_role_id = None

        async with self.bot.db.cursor() as cursor:

            await cursor.execute("SELECT value FROM settings WHERE key = ?", ('tenure_qualifying_role_id',))

            result = await cursor.fetchone()

            if result:

                qualifying_role_id = int(result[0])

        

        qualifying_role = guild.get_role(qualifying_role_id) if qualifying_role_id else None

        

        if qualifying_role_id and not qualifying_role:

            print(f"Warning: Tenure qualifying role ID {qualifying_role_id} is set but not found in the server. No tenure roles will be awarded.")

            return

        async with self.bot.db.cursor() as cursor:

            await cursor.execute("SELECT user_id, join_date FROM members")

            all_members_in_db = await cursor.fetchall()

            await cursor.execute("SELECT days, role_id FROM tenure_roles ORDER BY days DESC")

            tenure_roles = await cursor.fetchall()

        if not tenure_roles: return

        now_utc = datetime.now(timezone.utc)

        awarded_count = 0

        for user_id, join_date_str in all_members_in_db:

            member = guild.get_member(user_id)

            if not member: continue

            

            # NEW: Check if the member has the qualifying role (if one is set)

            if qualifying_role and qualifying_role not in member.roles:

                continue # Skip this member if they don't have the required role

            join_date = datetime.fromisoformat(join_date_str)

            if join_date.tzinfo is None:

                join_date = join_date.replace(tzinfo=timezone.utc)

            days_in_alliance = (now_utc - join_date).days

            for days_milestone, role_id in tenure_roles:

                if days_in_alliance >= days_milestone:

                    role_to_award = guild.get_role(role_id)

                    if role_to_award and role_to_award not in member.roles:

                        try:

                            await member.add_roles(role_to_award, reason=f"Tenure: {days_milestone} days")

                            await self.log_action(f"**Tenure Award**: Gave {role_to_award.mention} to {member.mention} for reaching {days_milestone} days.")

                            awarded_count += 1

                        except discord.Forbidden:

                            await self.log_action(f"**ERROR**: Failed to give tenure role {role_to_award.mention} to {member.mention} (Permissions).")

                    break # Move to the next member after finding their highest eligible role

        

        print(f"Tenure check complete. Awarded roles to {awarded_count} members.")
                    
async def setup(bot):
    await bot.add_cog(MembershipCog(bot))
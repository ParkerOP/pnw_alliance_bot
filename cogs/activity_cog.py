# cogs/activity_cog.py
import discord
from discord.ext import commands
from datetime import datetime, timedelta, timezone

class ActivityCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def log_action(self, message: str):
       """Helper function to send a message to the configured log channel."""
       async with self.bot.db.cursor() as cursor:
           await cursor.execute("SELECT value FROM settings WHERE key = ?", ('log_channel_id',))
           result = await cursor.fetchone()
       if result:
           channel_id = int(result[0])
           log_channel = self.bot.get_channel(channel_id)
           if log_channel:
               try:
                   await log_channel.send(f"[`{datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}`] {message}")
               except discord.Forbidden:
                   print(f"Error: Bot could not send message to log channel {channel_id}.")
       async with self.bot.db.cursor() as cursor:
           await cursor.execute("SELECT value FROM settings WHERE key = ?", ('log_channel_id',))
           result = await cursor.fetchone()
       if result:
           channel_id = int(result[0])
           log_channel = self.bot.get_channel(channel_id)
           if log_channel:
               try:
                   await log_channel.send(f"[`{datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}`] {message}")
               except discord.Forbidden:
                   print(f"Error: Bot could not send message to log channel {channel_id}.")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Logs every valid message for activity tracking."""
        # Ignore bots and commands
        if message.author.bot or message.content.startswith(self.bot.command_prefix):
            return
        
        # We only care about messages in guilds
        if not message.guild:
            return

        # FIX APPLIED HERE: Store all timestamps as aware UTC
        timestamp = datetime.now(timezone.utc).isoformat()
        category_id = message.channel.category_id if hasattr(message.channel, 'category_id') else None

        async with self.bot.db.cursor() as cursor:
            await cursor.execute("""
                INSERT INTO activity_log (user_id, channel_id, category_id, timestamp)
                VALUES (?, ?, ?, ?)
            """, (message.author.id, message.channel.id, category_id, timestamp))
        await self.bot.db.commit()

    @commands.group(name="award-cycle",brief="(Admin) Manages the cyclical award process.",

    help="Parent command for running the award cycles (e.g., monthly) and resetting activity data.", invoke_without_command=True)
    @commands.has_permissions(administrator=True)
    async def award_cycle(self, ctx):
        """Parent command for managing award cycles."""
        await ctx.send("Invalid subcommand. Use `run` or `reset`. Example: `!award-cycle run gamma`")

    @award_cycle.command(name="run", brief="Runs the award cycle for a specific tier.",

    help="Processes all configured awards for a given frequency. 'gamma' runs all 'monthly' awards, and 'beta' runs all 'quarterly' awards. This command removes old roles and assigns them to the new winners.")
    @commands.has_permissions(administrator=True)
    async def run_cycle(self, ctx, tier: str):
        """
        Runs the award cycle for a given tier.
        Tiers: gamma (monthly), beta (quarterly).
        """
        tier = tier.lower()
        if tier == 'gamma':
            frequency = 'monthly'
            days = 30
        elif tier == 'beta':
            frequency = 'quarterly'
            days = 90
        else:
            return await ctx.send("Invalid tier. Please use `gamma` (monthly) or `beta` (quarterly).")
        
        await ctx.send(f"⚙️ Running **{tier.capitalize()} ({frequency})** award cycle. This may take a moment...")
        
        async with self.bot.db.cursor() as cursor:
            await cursor.execute("SELECT award_name, award_type, role_id, target_id FROM award_configs WHERE frequency = ?", (frequency,))
            awards_to_process = await cursor.fetchall()
        
        if not awards_to_process:
            return await ctx.send(f"No {frequency} awards found in the configuration.")

        # Get announcement channel
        async with self.bot.db.cursor() as cursor:
            await cursor.execute("SELECT value FROM settings WHERE key = 'announcement_channel_id'")
            res = await cursor.fetchone()
        announcement_channel = self.bot.get_channel(int(res[0])) if res else None

        summary_log = [f"**🏆 Award Cycle Report: {tier.capitalize()} ({datetime.utcnow().strftime('%Y-%m-%d')}) 🏆**"]
        
        time_cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        for award_name, award_type, role_id, target_id in awards_to_process:
            role = ctx.guild.get_role(role_id)
            if not role:
                summary_log.append(f"⚠️ **{award_name}**: Skipped. Role with ID `{role_id}` not found.")
                continue

            # --- 1. Clear Old Winners ---
            old_winners = role.members
            for member in old_winners:
                try:
                    await member.remove_roles(role, reason="Award cycle reset.")
                except discord.Forbidden:
                    summary_log.append(f"⚠️ **{award_name}**: Could not remove role from {member.mention} (Permissions error).")
            
            # --- 2. Calculate New Winner ---
            winner_id = None
            async with self.bot.db.cursor() as cursor:
                if award_type == 'server':
                    await cursor.execute("""
                        SELECT user_id, COUNT(*) as msg_count 
                        FROM activity_log 
                        WHERE timestamp >= ?
                        GROUP BY user_id ORDER BY msg_count DESC LIMIT 1
                    """, (time_cutoff,))
                elif award_type == 'channel':
                    await cursor.execute("""
                        SELECT user_id, COUNT(*) as msg_count 
                        FROM activity_log 
                        WHERE channel_id = ? AND timestamp >= ?
                        GROUP BY user_id ORDER BY msg_count DESC LIMIT 1
                    """, (target_id, time_cutoff))
                elif award_type == 'category':
                    await cursor.execute("""
                        SELECT user_id, COUNT(*) as msg_count 
                        FROM activity_log 
                        WHERE category_id = ? AND timestamp >= ?
                        GROUP BY user_id ORDER BY msg_count DESC LIMIT 1
                    """, (target_id, time_cutoff))
                
                winner_data = await cursor.fetchone()
                if winner_data:
                    winner_id = winner_data[0]

            # --- 3. Assign Role and Announce ---
            if winner_id:
                winner_member = ctx.guild.get_member(winner_id)
                if winner_member:
                    try:
                        await winner_member.add_roles(role, reason=f"Winner of {award_name} award.")
                        summary_log.append(f"✅ **{award_name}**: Awarded {role.mention} to {winner_member.mention}.")
                    except discord.Forbidden:
                        summary_log.append(f"❌ **{award_name}**: Found winner {winner_member.mention} but failed to assign role (Permissions error).")
                else:
                    summary_log.append(f"⚠️ **{award_name}**: Found winner (ID: {winner_id}) but they are no longer in the server.")
            else:
                summary_log.append(f"ℹ️ **{award_name}**: No eligible winner found for this period.")

        # Send logs and announcements
        await self.log_action("\n".join(summary_log))
        if announcement_channel:
            try:
                await announcement_channel.send("\n".join(summary_log))
            except discord.Forbidden:
                await self.log_action(f"**ERROR**: Could not send award summary to announcement channel.")
        
        await ctx.send("✅ Award cycle finished. A detailed report has been sent to the log channel.")

    @award_cycle.command(name="reset", brief="Clears old activity data for a tier.",

    help="Deletes old message activity logs to keep the database from growing too large. 'gamma' deletes data older than 30 days, and 'beta' deletes data older than 90 days.")
    @commands.has_permissions(administrator=True)
    async def reset_cycle_data(self, ctx, tier: str):
        """Deletes activity data older than the cycle period."""
        tier = tier.lower()
        if tier == 'gamma':
            days = 30
        elif tier == 'beta':
            days = 90
        else:
            return await ctx.send("Invalid tier. Please use `gamma` (monthly) or `beta` (quarterly).")
        
        time_cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

        await ctx.send(f"🗑️ Deleting activity log data older than {days} days... This may take a moment.")
        
        async with self.bot.db.cursor() as cursor:
            await cursor.execute("DELETE FROM activity_log WHERE timestamp < ?", (time_cutoff,))
            await self.bot.db.commit()
            deleted_rows = cursor.changes()
        
        await ctx.send(f"✅ Data reset complete. Deleted {deleted_rows} old log entries.")
        await self.log_action(f"**Data Reset**: {ctx.author.mention} ran data reset for tier `{tier}`. Deleted {deleted_rows} old log entries.")

async def setup(bot):
    await bot.add_cog(ActivityCog(bot))
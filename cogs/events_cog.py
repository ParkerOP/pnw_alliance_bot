# cogs/events_cog.py
import discord
from discord.ext import commands
from datetime import datetime

class EventsCog(commands.Cog):
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

    @commands.command(name="event-create", brief="Creates a new community event.",

    help="Creates a new event embed message. Members can react to the message to sign up. The bot will track the host and all participants when the event is closed.")
    @commands.has_permissions(manage_events=True)
    async def event_create(self, ctx, *, title: str):
        """Creates a new event for members to join via reactions."""
        embed = discord.Embed(
            title=f"🎉 {title}",
            description="React with ✅ to participate!\nThe host will close entry when the event begins.",
            color=discord.Color.blue()
        )
        embed.set_footer(text=f"Hosted by {ctx.author.display_name}")
        
        try:
            event_message = await ctx.send(embed=embed)
            await event_message.add_reaction("✅")
        except discord.Forbidden:
            return await ctx.send("❌ **Error:** I don't have permissions to send messages or add reactions in this channel.")

        # Store the event in the database
        async with self.bot.db.cursor() as cursor:
            await cursor.execute("INSERT INTO active_events (message_id, host_id, title) VALUES (?, ?, ?)",
                                 (event_message.id, ctx.author.id, title))
        await self.bot.db.commit()
        await self.log_action(f"**Event Created**: {ctx.author.mention} created event '{title}' in {ctx.channel.mention}.")

    @commands.command(name="event-close", brief="Closes an active event and logs stats.",

    help="Closes an event that was created with `!event-create`. This command MUST be used as a reply to the bot's original event message. It will log stats for the host and all participants, and award milestone roles if applicable.")
    @commands.has_permissions(manage_events=True)
    async def event_close(self, ctx):
        """Closes an event. Must be used as a reply to the event message."""
        if not ctx.message.reference or not ctx.message.reference.message_id:
            return await ctx.send("❌ **Error:** You must use this command as a **reply** to the event message you want to close.")

        event_message_id = ctx.message.reference.message_id
        
        # Check if the event is in our database
        async with self.bot.db.cursor() as cursor:
            await cursor.execute("SELECT host_id, title FROM active_events WHERE message_id = ?", (event_message_id,))
            event_data = await cursor.fetchone()

        if not event_data:
            return await ctx.send("❌ **Error:** This message is not an active event that I am tracking.")
        
        host_id, title = event_data
        
        # QoL: Allow an admin to close any event, not just the host
        if ctx.author.id != host_id and not ctx.author.guild_permissions.administrator:
            host_user = self.bot.get_user(host_id)
            return await ctx.send(f"❌ **Error:** Only the event host ({host_user.mention if host_user else 'Unknown Host'}) or an Administrator can close this event.")

        # Fetch the original message to get reactions
        try:
            event_message = await ctx.channel.fetch_message(event_message_id)
        except discord.NotFound:
            return await ctx.send("❌ **Error:** The original event message seems to have been deleted.")

        participants = set()
        for reaction in event_message.reactions:
            if str(reaction.emoji) == "✅":
                async for user in reaction.users():
                    if not user.bot:
                        participants.add(user)

        # Update stats in the database
        async with self.bot.db.cursor() as cursor:
            # Increment host's count
            await cursor.execute("""
                UPDATE members SET host_count = host_count + 1 WHERE user_id = ?
            """, (host_id,))
            # Check if host exists in members table, if not, insert them.
            if cursor.rowcount == 0:
                 await cursor.execute("INSERT OR IGNORE INTO members (user_id, join_date, host_count) VALUES (?, ?, 1)", (host_id, datetime.utcnow().isoformat()))

            # Increment participants' counts
            for member in participants:
                await cursor.execute("""
                    UPDATE members SET participation_count = participation_count + 1 WHERE user_id = ?
                """, (member.id,))
                if cursor.rowcount == 0:
                    await cursor.execute("INSERT OR IGNORE INTO members (user_id, join_date, participation_count) VALUES (?, ?, 1)", (member.id, datetime.utcnow().isoformat()))

            # Remove event from active list
            await cursor.execute("DELETE FROM active_events WHERE message_id = ?", (event_message_id,))
        await self.bot.db.commit()

        # Check for and award participation roles
        await self.check_participation_milestones(ctx, participants)

        # Finalize and update the event message
        participant_mentions = [p.mention for p in participants]
        final_embed = event_message.embeds[0]
        final_embed.color = discord.Color.red()
        final_embed.title = f"[CLOSED] {title}"
        final_embed.description = f"This event is now closed. Thanks for participating!\n\n**Participants ({len(participant_mentions)}):**\n" + (', '.join(participant_mentions) if participant_mentions else 'None')
        
        await event_message.edit(embed=final_embed)
        await event_message.clear_reactions()
        await ctx.send(f"✅ Event '{title}' has been closed. Stats have been updated for {len(participants)} participants and 1 host.")
        await self.log_action(f"**Event Closed**: {ctx.author.mention} closed event '{title}'. Participants: {len(participants)}")

    async def check_participation_milestones(self, ctx, participants):
        """Check if any participants have earned a new milestone role."""
        async with self.bot.db.cursor() as cursor:
            await cursor.execute("SELECT count, role_id FROM participation_roles ORDER BY count DESC")
            milestones = await cursor.fetchall()

        if not milestones:
            return

        for member in participants:
            async with self.bot.db.cursor() as cursor:
                await cursor.execute("SELECT participation_count FROM members WHERE user_id = ?", (member.id,))
                user_data = await cursor.fetchone()
            
            if not user_data:
                continue
            
            current_count = user_data[0]

            for count_milestone, role_id in milestones:
                if current_count >= count_milestone:
                    role = ctx.guild.get_role(role_id)
                    if role and role not in member.roles:
                        try:
                            await member.add_roles(role, reason=f"Participation: {count_milestone} events")
                            await self.log_action(f"**Participation Award**: Gave {role.mention} to {member.mention} for reaching {count_milestone} events.")
                        except discord.Forbidden:
                            await self.log_action(f"**ERROR**: Failed to give participation role {role.mention} to {member.mention} (Bot role too low?).")
                        # Stop after awarding the highest qualifying role
                        break

async def setup(bot):
    await bot.add_cog(EventsCog(bot))
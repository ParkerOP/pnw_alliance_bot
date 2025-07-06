# cogs/utility_cog.py (Corrected)
import discord
from discord.ext import commands
from datetime import datetime, timedelta, timezone

class UtilityCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="profile", brief="Displays a member's alliance profile.",

    help="Shows your own (or another member's) alliance statistics, including tenure, join date, and event participation/hosting counts.")
    async def profile(self, ctx, member: discord.Member = None):
        """Displays the alliance profile of a member (or yourself)."""
        if member is None:
            member = ctx.author

        async with self.bot.db.cursor() as cursor:
            await cursor.execute("SELECT join_date, participation_count, host_count FROM members WHERE user_id = ?", (member.id,))
            user_data = await cursor.fetchone()

        embed = discord.Embed(title=f"Alliance Profile: {member.display_name}", color=member.color)
        embed.set_thumbnail(url=member.avatar.url)

        if not user_data:
            embed.description = "This member is not officially tracked in the alliance database (have they been `!accept`'ed or `!sync-members`'d?)."
        else:
            # The member's join_date from Discord is timezone-aware (UTC).
            # We must compare it with a timezone-aware "now".
            join_date = datetime.fromisoformat(user_data[0])
            now_utc = datetime.now(timezone.utc)
            
            # Ensure join_date is also aware for a safe subtraction
            if join_date.tzinfo is None:
                join_date = join_date.replace(tzinfo=timezone.utc)

            days_in_alliance = (now_utc - join_date).days
            participation_count = user_data[1]
            host_count = user_data[2]
            
            embed.add_field(name="Alliance Tenure", value=f"**{days_in_alliance}** days", inline=True)
            embed.add_field(name="Joined On", value=f"<t:{int(join_date.timestamp())}:D>", inline=True)
            embed.add_field(name="\u200b", value="\u200b", inline=True) # Spacer
            embed.add_field(name="Events Attended", value=f"**{participation_count}**", inline=True)
            embed.add_field(name="Events Hosted", value=f"**{host_count}**", inline=True)
            
        await ctx.send(embed=embed)

    @commands.command(name="leaderboard", aliases=['lb'], brief="Shows leaderboards for various stats.",

    help="Displays the top 10 members for a given statistic. Available stats: `activity` (monthly messages), `participation` (for events), `hosting` (event hosting).")
    async def leaderboard(self, ctx, stat: str = 'activity'):
        """
        Shows the top 10 members for a given statistic.
        Stats: activity, participation, hosting
        """
        stat = stat.lower()
        embed = discord.Embed(color=discord.Color.gold())
        
        async with self.bot.db.cursor() as cursor:
            if stat == 'activity':
                embed.title = "Top 10 Most Active Members (Last 30 Days)"
                # FIX APPLIED HERE
                time_cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
                await cursor.execute("""
                    SELECT user_id, COUNT(*) as msg_count FROM activity_log
                    WHERE timestamp >= ?
                    GROUP BY user_id ORDER BY msg_count DESC LIMIT 10
                """, (time_cutoff,))
                results = await cursor.fetchall()
                field_value = "\n".join([f"{i+1}. <@{user_id}> - {count} messages" for i, (user_id, count) in enumerate(results)]) if results else "No activity recorded yet."

            elif stat == 'participation':
                embed.title = "Top 10 Event Participants"
                await cursor.execute("SELECT user_id, participation_count FROM members WHERE participation_count > 0 ORDER BY participation_count DESC LIMIT 10")
                results = await cursor.fetchall()
                field_value = "\n".join([f"{i+1}. <@{user_id}> - {count} events" for i, (user_id, count) in enumerate(results)]) if results else "No one has participated in events yet."

            elif stat == 'hosting':
                embed.title = "Top 10 Event Hosts"
                await cursor.execute("SELECT user_id, host_count FROM members WHERE host_count > 0 ORDER BY host_count DESC LIMIT 10")
                results = await cursor.fetchall()
                field_value = "\n".join([f"{i+1}. <@{user_id}> - {count} events" for i, (user_id, count) in enumerate(results)]) if results else "No one has hosted an event yet."

            else:
                return await ctx.send("Invalid statistic. Please use `activity`, `participation`, or `hosting`.")

        embed.description = field_value
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(UtilityCog(bot))
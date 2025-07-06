# pw_alliance_bot/bot.py
# Reconstructed from scratch using the working Pokémon bot template.

import discord
from discord.ext import commands
import os
import asyncio
import traceback
from dotenv import load_dotenv
import aiosqlite

# --- Define Intents (Copied from working example) ---
intents = discord.Intents.default()
intents.message_content = True
intents.members = True # Enabled, as required by the P&W bot features.
intents.presences = False # Disabled for efficiency.

# --- Bot Instance (Template from working example) ---
# We use a static prefix as required by the P&W bot.
bot = commands.Bot(command_prefix='!',
                   intents=intents,
                   help_command=None,
                   case_insensitive=True)

# --- Bot Setup Hook (Template from working example) ---
@bot.event
async def setup_hook():
    print("--- Running Setup Hook ---")

    # Connect to the database and attach it to the bot instance.
    # This is the P&W bot's equivalent of loading the pokemon_list.
    try:
        bot.db = await aiosqlite.connect("database.db")
        print("✅ Database connected successfully.")
    except Exception as e:
        print(f"❌ FATAL: Could not connect to database: {e}")
        traceback.print_exc()
        # If the database is essential, we might want to prevent the bot from fully starting.
        # This can be done by raising the exception or closing the bot.
        await bot.close()
        return

    # Load Cogs from a hardcoded list (Template from working example)
    print("--- Loading Cogs ---")
    cogs_to_load = [
        'cogs.config_cog',
        'cogs.membership_cog',
        'cogs.events_cog',
        'cogs.activity_cog',
        'cogs.utility_cog',
        'cogs.listeners_cog',
        'cogs.help_cog'
    ]

    for cog_name in cogs_to_load:
        try:
            await bot.load_extension(cog_name)
            print(f'✅ Successfully loaded cog: {cog_name}')
        except commands.ExtensionNotFound:
            print(f'❌ ERROR: Cog {cog_name} not found.')
        except commands.ExtensionAlreadyLoaded:
            print(f'⚠️ Warning: Cog {cog_name} already loaded.')
        except commands.NoEntryPointError:
            print(f'❌ ERROR: Cog {cog_name} does not have a setup function.')
        except commands.ExtensionFailed as e:
            print(f'❌ ERROR: Cog {cog_name} failed to load.')
            traceback.print_exception(type(e.original), e.original, e.original.__traceback__)
        except Exception as e:
            print(f'❌ ERROR: An unexpected error occurred loading cog {cog_name}: {e}')
            traceback.print_exc()

    print("--- Setup Hook Complete ---")


# --- Basic On Ready Event (Template from working example) ---
@bot.event
async def on_ready():
    print("-" * 30)
    print(f'Logged in as {bot.user.name} ({bot.user.id})')
    print(f'Discord.py Version: {discord.__version__}')
    print(f'Successfully logged in and booted...!')
    print("-" * 30)


# --- Bot Runner Function (Template from working example) ---
def run_bot():
    # Load the .env file.
    # NOTE: Ensure your .env file is in the same directory as this bot.py file!
    load_dotenv()
    TOKEN = os.getenv('DISCORD_TOKEN')

    if not TOKEN:
        print("-" * 50)
        print("❌ ERROR: Bot token is missing!")
        print("Please ensure DISCORD_TOKEN is set in your .env file.")
        print("-" * 50)
        return

    print("Attempting to connect to Discord...")
    try:
        # Use bot.run() as it is used in the working example.
        bot.run(TOKEN)
    except discord.LoginFailure:
        print("-" * 50)
        print("❌ ERROR: Invalid bot token provided.")
        print("Please check your DISCORD_TOKEN in the .env file.")
        print("-" * 50)
    except discord.PrivilegedIntentsRequired:
        print("-" * 50)
        print("❌ ERROR: Privileged Intents are required but not enabled.")
        print("Please enable 'Server Members Intent' and 'Message Content Intent'")
        print("in your bot's settings on the Discord Developer Portal.")
        print("-" * 50)
    except discord.HTTPException as e:
        print(f"❌ ERROR connecting to Discord (HTTPException): {e.status} - {e.text}")
        print("This might be a temporary Discord issue, a network problem, or rate limiting.")
    except Exception as e:
        print(f"❌ An unexpected error occurred while running the bot: {e}")
        traceback.print_exc()


# --- Main Execution Block (Template from working example) ---
if __name__ == "__main__":
    run_bot()
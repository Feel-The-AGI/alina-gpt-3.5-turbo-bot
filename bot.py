import os
import random
import asyncio
import openai
import discord
import aioredis
from discord.ext import commands
from dotenv import load_dotenv
import os

load_dotenv()

discord_bot_token = os.getenv("DISCORD_BOT_TOKEN")

openai_api_key = os.getenv("OPENAI_API_KEY")
if not openai_api_key:
    raise ValueError("API key not found. Please set the OPENAI_API_KEY environment variable.")
openai.api_key = openai_api_key

intents = discord.Intents.default()
intents.typing = False
intents.presences = False
intents.message_content = True # Added this line to request 0auth when bot reaches 100 servers

bot = commands.Bot(command_prefix="!", intents=intents)

# Connect to Redis
async def connect_redis():
    return await aioredis.from_url("redis://localhost:6379")

redis = asyncio.run(connect_redis())

# Utility function to generate responses using GPT-3.5-Turbo
async def generate_response(prompt, user_name, bot_name):
    completions = openai.Completion.create(
        engine="text-davinci-003",
        prompt=prompt,
        max_tokens=150,
        n=1,
        stop=["Human:", "AI:"],
        temperature=0.9,
        top_p=1,
        frequency_penalty=0.0,
        presence_penalty=0.6,
    )

    message = completions.choices[0].text.strip()
    return message.replace("Human", user_name).replace("AI", bot_name)

# Command to set the user's preferences
@bot.command(name="setpreferences")
async def set_preferences(ctx, periodic_messages: bool):
    user_id = str(ctx.author.id)
    await redis.hset(user_id, "periodic_messages", periodic_messages)
    await ctx.send(f"Periodic messages preference set to {periodic_messages}.")

# Main message handling
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    if message.content.startswith("!"):
        await bot.process_commands(message)
    else:
        user_id = str(message.author.id)
        user_name = message.author.display_name
        bot_name = message.guild.me.display_name

        # Check if response is cached
        cache_key = f"response_cache:{user_id}:{message.content}"
        cached_response = await redis.get(cache_key)

        if cached_response:
            response = cached_response.decode()
        else:
            prompt = f"The following is a conversation with an AI assistant. The assistant is helpful, creative, clever, and very friendly, with occasional sarcasm.\n\n{user_name}: {message.content}\n{bot_name}:"
            response = await generate_response(prompt, user_name, bot_name)

            # Cache the response
            await redis.set(cache_key, response, expire=3600)

        await message.channel.send(response)

# Periodic message handling
async def check_up_on_user(user, channel):
    user_id = str(user.id)

    while True:
        delay = random.randint(1800, 3600)  # Random delay between 30 to 60 minutes
        await asyncio.sleep(delay)

        # Check if user has periodic_messages enabled
        periodic_messages = await redis.hget(user_id, "periodic_messages")

        if periodic_messages and periodic_messages.decode() == "True":
            user_name = user.display_name
            bot_name = channel.guild.me.display_name
            prompt = f"The following is a conversation with an AI assistant. The assistant is helpful, creative, clever, and very friendly, with occasional sarcasm.\n\n{bot_name}:"
            response = await generate_response(prompt, user_name, bot_name)
            await channel.send(response)

# Start periodic messages when user joins the server
@bot.event
async def on_member_join(member):
    await check_up_on_user(member, member.guild.system_channel)

bot.run(discord_bot_token)
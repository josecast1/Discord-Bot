import discord

def get_intents():
    intents = discord.Intents.default()
    intents.reactions = True
    intents.message_content = True
    intents.members = True
    return intents

TOKEN = 'BOT TOKEN'
import discord
import logging
import asyncio
import datetime
from bot_functions import *
from discord.ext import commands
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

intents = get_intents()

client = commands.Bot(command_prefix="!", intents=intents)
role_selection_message = None

scheduler = AsyncIOScheduler()

# Emojis and role descriptions
emoji_to_role = {
    '<:autonomous_vehicle:1148337868201267270>': 'Autonomous Vehicle Design Team',
    '<:kotlin:1148337119442518036>': 'Kotlin App',
    '<:swift:1148337328415322172>': 'Swift App',
    '<:leetcode:1148349688924340314>': 'Interview Prep',
}

role_descriptions = {
    'Autonomous Vehicle Design Team': 'if you are interested in participating in our Autonomous Vehicle design team',
    'Kotlin App': 'if you are interested in participating in our Kotlin Mobile App design team',
    'Swift App': 'if you are interested in participating in our Swift Mobile App design team',
    'Interview Prep': 'if you are interested in getting notified on our technical interview office hours'
}

@client.event
async def on_ready():
    global role_selection_message
    logger.info(f'Logged in as {client.user.name}')
    
    # Find "roles-selection" channel
    role_selection_channel = discord.utils.get(client.guilds[0].text_channels, name="roles")

    # Checking for channel
    if role_selection_channel:
        # Check if there's an existing role selection message
        async for message in role_selection_channel.history(limit=1):
            if message.author == client.user:
                role_selection_message = message
                break
        
        if role_selection_message:
            logger.info(f'Found existing role selection message: {role_selection_message.jump_url}')
        else:
            # Create a new role selection message
            embed = discord.Embed(
                title="Design Team Roles",
                color=discord.Color.dark_gray()
            )

            # Add fields to the embed message
            for emoji, role_name in emoji_to_role.items():
                role = discord.utils.get(role_selection_channel.guild.roles, name=role_name)
                if role:
                    description = role_descriptions.get(role_name, '')
                    field_value = f"{emoji} {role.mention} - {description}" if description else f"{emoji} {role.mention}"
                    embed.add_field(name="", value=field_value, inline=False)


            # Send the embed message
            role_selection_message = await role_selection_channel.send(embed=embed)

            # Add reactions to the message
            for emoji in emoji_to_role.keys():
                await role_selection_message.add_reaction(emoji)

            logger.info(f'Created new role selection message: {role_selection_message.jump_url}')
        
        client.role_selection_message = role_selection_message


    if not scheduler.running:
        scheduler.start()
    
    @client.event
    async def on_member_join(member):
        welcome_channel = discord.utils.get(client.guilds[0].text_channels, name="welcome")
        role_selection_channel = discord.utils.get(client.guilds[0].text_channels, name="roles")
        
        if welcome_channel:
            roles_channel_mention = f"<#{role_selection_channel.id}>" if role_selection_channel else "#roles"
            emoji = '\N{WAVING HAND SIGN}'
            await welcome_channel.send(f"Thanks for joining the SHPE UF Tech Cabinet {member.mention} {emoji}! Please check out {roles_channel_mention} and #rules for more information. We are now at {member.guild.member_count} members!")

    @client.command(name='schedule_announcement')
    async def schedule_announcement(ctx, date_str, time_str, recurring_option: str, *, announcement):
        # Combine date and time strings into a single datetime object
        schedule_datetime = datetime.datetime.strptime(f'{date_str} {time_str}', '%Y-%m-%d %H:%M')
        
        # Check if the user wants the announcement to be recurring
        is_recurring = recurring_option.lower() == 'recurring'
        
        if is_recurring:
            # Add job to send announcement every day at the specified time
            scheduler.add_job(send_scheduled_announcement, 'cron', hour=time_str.split(':')[0], minute=time_str.split(':')[1], args=[ctx.channel, announcement])
        else:
            # Add job to send announcement
            scheduler.add_job(send_scheduled_announcement, 'date', run_date=schedule_datetime, args=[ctx.channel, announcement])
        
        await ctx.send(f"{'Recurring' if is_recurring else 'One-time'} announcement scheduled for {schedule_datetime.strftime('%Y-%m-%d %H:%M')}.")

async def send_scheduled_announcement(channel, announcement):
    channel = discord.utils.get(client.guilds[0].text_channels, name="office-hours")
    embed = discord.Embed(
        title="Office Hours",
        description=announcement,
        color=discord.Color.green()
    )
    embed.set_footer(text="Join if you need any help!")
    embed.set_thumbnail(url="https://oai.tech.uci.edu/wp-content/uploads/2023/02/shpe-logo.png")
    
    await channel.send(embed=embed)

@client.command(name='edit_announcement')
async def edit_announcement(ctx, job_id: str, *, new_announcement: str):
    job = scheduler.get_job(job_id)
    if job:
        job.modify(args=[ctx.channel.id, new_announcement])
        await ctx.send(f"Announcement edited successfully.")
    else:
        await ctx.send(f"Announcement with ID {job_id} not found.")

@client.command(name='view_announcements')
async def view_announcements(ctx):
    jobs = scheduler.get_jobs()
    if jobs:
        embed = discord.Embed(
            title="Upcoming Announcements",
            color=discord.Color.blue()
        )
        for job in jobs:
            announcement_info = job.args[1]
            announcement_lines = announcement_info.split('\n')
            description = '\n'.join([line.strip() for line in announcement_lines])
            
            # Check if trigger is CronTrigger for recurring announcements
            if isinstance(job.trigger, CronTrigger):
                recurring_text = "Recurring"
            else:
                recurring_text = "Once"
            
            embed.add_field(
                name=f"**Job ID:** {job.id}",
                value=f"**Date and Time:** {job.next_run_time.strftime('%Y-%m-%d %H:%M')}\n**Type:** {recurring_text}\n**Description:** \n{description}",
                inline=False
            )
        await ctx.send(embed=embed)
    else:
        await ctx.send("No upcoming announcements.")

@client.command(name='delete_announcement')
async def delete_announcement(ctx, job_id: str):
    job = scheduler.get_job(job_id)
    if job:
        job.remove()
        await ctx.send(f"Announcement with ID {job_id} has been deleted successfully.")
    else:
        await ctx.send(f"Announcement with ID {job_id} not found.")

# Calls when a reaction is added to the role selection message
@client.event
async def on_reaction_add(reaction, user):
    if user.bot:
        return
    
    # Check if the reaction is on the role selection message
    if reaction.message == client.role_selection_message:
        # Needed to convert emoji to string for custom emojis to compare with emoji_to_role dictionary keys
        if str(reaction.emoji) in emoji_to_role:
            role_name = emoji_to_role[str(reaction.emoji)]
            role = discord.utils.get(user.guild.roles, name=role_name)
            if role:
                await user.add_roles(role)

                if role_name == 'Autonomous Vehicle Design Team':
                    await user.send("""You have been assigned the Autonomous Vehicle Design Team role! Here you can find the 
                                    latest updates on our Autonomous Vehicle projects. If you are a member of this project, 
                                    please reach out to Lorenz Carvajal or Alex Lyew to join your team's channels!""")
                elif role_name == 'Kotlin App':
                    await user.send("""You have been assigned the Kotlin App role! Here you can find the latest updates on our 
                                    Android Mobile App project. If you are a member for this project, please reach out to Miguel 
                                    Tejeda to join your team's channels!""")
                elif role_name == 'Swift App':
                    await user.send("""You have been assigned the Swift App role! Here you can find the latest updates on our 
                                    iOS Mobile App project. If you are a member for this project, please reach out to Jesus Lopez 
                                    to join your team's channels!""")
                elif role_name == 'Interview Prep':
                    await user.send("""You have been assigned the Interview Prep role! Here you can join us in our technical 
                                    prep office hours, sign up for mock interviews and solve a LeetCode Question of the Week. 
                                    If you have any questions, feel free to reach out to Mateo Slivka, Santiago Barrios or 
                                    Diego Santos Gonzalez!""")

# Calls when a reaction is removed from the role selection message
@client.event
async def on_reaction_remove(reaction, user):
    if user.bot:
        return

    if reaction.message == client.role_selection_message:
        if str(reaction.emoji) in emoji_to_role:
            role_name = emoji_to_role[str(reaction.emoji)]
            role = discord.utils.get(user.guild.roles, name=role_name)
            if role:
                await user.remove_roles(role)
                await user.send(f'You have removed the {role_name}.')

client.run(TOKEN)
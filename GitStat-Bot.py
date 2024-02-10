import discord
from discord.ui import Button, View
from collections import defaultdict
from datetime import datetime, timedelta
import asyncio
import json


# Predefined variables for configuration
CHANNEL_ID =  # ID of the Discord channel to send reports to
BOT_TOKEN = ''  # Token for the Discord bot
authors_list = ["",]  # List of predefined authors to track
current_style = False  # Current style for report formatting; False for table-like, True for alternate style
report_interval = timedelta(seconds=10)  # weeks=?, days=?, hours=?, minutes=?, seconds=?

# Set up Discord client with all intents enabled for comprehensive event handling
intents = discord.Intents.all()
client = discord.Client(intents=intents)

# Initialize a data structure to keep track of activity counts for each author
activity_counts = {
    'Pull request opened': defaultdict(int, {author: 0 for author in authors_list}),
    'Issue opened': defaultdict(int, {author: 0 for author in authors_list})
}

# Variable to keep track of the last time counts were reset
last_reset_time = datetime.now()

report_title = ""

def binary_search_report(start_time_str, file_path='report_history.json'):
    print(f"Starting binary search for: {start_time_str}")
    try:
        with open(file_path, 'r') as file:
            reports = json.load(file)
            left, right = 0, len(reports) - 1
            while left <= right:
                mid = (left + right) // 2
                mid_start_time = reports[mid]['start_time']
                print(f"Comparing with: {mid_start_time}")
                if mid_start_time == start_time_str:
                    print("Match found.")
                    return reports[mid]
                elif mid_start_time < start_time_str:
                    left = mid + 1
                else:
                    right = mid - 1
    except FileNotFoundError:
        print("Report history file not found.")
    return None

def save_history(start_time_str, current_time_str):
    history_data = {
        'start_time': start_time_str,
        'end_time': current_time_str,
        'report_title': report_title,
        'activity_counts': {activity: dict(counts) for activity, counts in activity_counts.items()}
    }
    try:
        with open('report_history.json', 'r+') as file:
            data = json.load(file)
            data.append(history_data)
            file.seek(0)
            file.truncate(0)  # Clear the file before rewriting
            json.dump(data, file, indent=4)
    except FileNotFoundError:
        with open('report_history.json', 'w') as file:
            json.dump([history_data], file, indent=4)

async def reset_counts():
    """Resets the activity counts for all tracked activities and authors."""
    global activity_counts
    for activity in activity_counts:
        for author in authors_list:
            activity_counts[activity][author] = 0
    print("Counts after reset:", activity_counts)

async def send_report(style):
    global last_reset_time
    global report_title

    channel = client.get_channel(CHANNEL_ID)
    if channel:
        current_time = datetime.now()
        start_time = current_time - report_interval
        start_time_str = start_time.strftime('%Y-%m-%d %H:%M:%S')
        current_time_str = current_time.strftime('%Y-%m-%d %H:%M:%S')

        report_title = f"Contribution Report\n\n`{start_time_str}` to `{current_time_str}`"

        embed_description = generate_embed_description(style, activity_counts)
        embed = discord.Embed(title=report_title, description=embed_description, color=0xFF0000)
        
        time_encoded_custom_id = f"toggle_style_{start_time_str}_{current_time_str}".replace(' ', '_').replace(':', '-')
        toggle_button = Button(label="Toggle Output Style", style=discord.ButtonStyle.green, custom_id=time_encoded_custom_id)
        
        view = View()
        view.add_item(toggle_button)
        await channel.send(embed=embed, view=view)

        save_history(start_time_str, current_time_str)
        await reset_counts()

    last_reset_time = current_time
    print(f"Contribution Report sent: `{start_time_str}` to `{current_time_str}`")

def generate_embed_description(style, activity_counts_param):
    """Generates the description for the embed based on the current style, using the provided activity counts."""
    embed_description = ""
    authors_with_warnings = []  # Track authors who will receive formal warnings

    if style:  # Alternate style
        embed_description += "\n"
        for user in authors_list:
            pr_count = activity_counts_param.get('Pull request opened', {}).get(user, 0)
            issue_count = activity_counts_param.get('Issue opened', {}).get(user, 0)
            warning_symbol = " ⚠️" if pr_count == 0 and issue_count == 0 else ""
            if warning_symbol:
                authors_with_warnings.append(user)
            embed_description += f"{user}\n> PR: `{pr_count}`, Issues: `{issue_count}`{warning_symbol}\n"
    else:  # Table-like style
        embed_description += "```"
        embed_description += "Author             | PR Opened  | Issues Opened\n"
        embed_description += "-" * 50 + "\n"
        for user in authors_list:
            pr_count = activity_counts_param.get('Pull request opened', {}).get(user, 0)
            issue_count = activity_counts_param.get('Issue opened', {}).get(user, 0)
            warning_symbol = " ⚠️" if pr_count == 0 and issue_count == 0 else ""
            if warning_symbol:
                authors_with_warnings.append(user)
            embed_description += f"{user: <18} | {pr_count: <10} | {issue_count: <13}{warning_symbol}\n"
        embed_description += "```"

    if authors_with_warnings:
        warning_text = ", ".join([f"`{author}`" for author in authors_with_warnings])
        embed_description += "\n**Formal Warnings Issued**\n\n"
        embed_description += f"{warning_text} received **`1` formal warning** due to non-compliance with the CruxAbyss Development Team License Agreement, section 3.2. Each member must make at least 1 'minor' contribution to the Project every 2 weeks. Failure to meet this requirement results in the issuance of 1 formal warning."

    return embed_description

async def background_task():
    """Background task to automatically send reports based on a time interval."""
    await client.wait_until_ready()
    while not client.is_closed():
        if datetime.now() - last_reset_time >= report_interval:  # Adjust interval as needed
            await send_report(current_style)
        await asyncio.sleep(1)  # Sleep interval between checks

@client.event
async def on_ready():
    """Event handler for when the bot is ready."""
    print(f'We have logged in as {client.user}')
    client.loop.create_task(background_task())

@client.event
async def on_message(message):
    """Event handler for new messages."""
    if message.author == client.user:
        return

    if message.embeds:

        embed_count = len(message.embeds)
        print(f"Message from {message.author} contains {embed_count} embed(s).")

        for embed in message.embeds:

            print("----- Embed Info Begin -----")
            if embed.title:
                print(f"Title: {embed.title}")
            if embed.description:
                print(f"Description: {embed.description}")
            if embed.url:
                print(f"URL: {embed.url}")
            if embed.timestamp:
                print(f"Timestamp: {embed.timestamp}")
            if embed.color:
                print(f"Color: {embed.color}")
            if embed.footer:
                print(f"Footer: {embed.footer.text}")
            if embed.image:
                print(f"Image URL: {embed.image.url}")
            if embed.thumbnail:
                print(f"Thumbnail URL: {embed.thumbnail.url}")
            if embed.author:
                print(f"Author: {embed.author.name}")
            if embed.fields:
                for i, field in enumerate(embed.fields):
                    print(f"Field {i + 1}: {field.name} - {field.value}")
            print("----- Embed Info End -----")

            embed_author_name = embed.author.name if embed.author else "No author"
            print(f"Embed author: {embed_author_name}")
            
            # Check if the embed author is in the predefined list
            if embed_author_name in authors_list:
                title = embed.title if embed.title else ""
                if "Pull request opened" in title:
                    activity_counts['Pull request opened'][embed_author_name] += 1
                    print(f"Pull request count +1 for {embed_author_name}")
                elif "Issue opened" in title:
                    activity_counts['Issue opened'][embed_author_name] += 1
                    print(f"Issue count +1 for {embed_author_name}")
            else:
                print(f"Author {embed_author_name} not in predefined list or not found in embed.")

#   if message.content.startswith('!hi'):
#       await message.channel.send('Hello!')

@client.event
async def on_interaction(interaction):
    global current_style
    if interaction.type == discord.InteractionType.component and interaction.data.get('custom_id').startswith("toggle_style"):
        parts = interaction.data.get('custom_id').replace("toggle_style_", "").split('_')
        start_time_parts = parts[0:2]
        current_time_parts = parts[2:4]

        start_time_str = f"{start_time_parts[0]} {start_time_parts[1].replace('-', ':')}"
        current_time_str = f"{current_time_parts[0]} {current_time_parts[1].replace('-', ':')}"

        print(f"Formatted for search - Start Time: {start_time_str}, Current Time: {current_time_str}")

        report_data = binary_search_report(start_time_str)
        if report_data:
            print(f"Report Data Found: {report_data}")

            report_title = f"Contribution Report\n\n`{report_data['start_time']}` to `{report_data['end_time']}`"

            current_style = not current_style
            new_embed_description = generate_embed_description(current_style, report_data['activity_counts'])
            new_embed = discord.Embed(title=report_title, description=new_embed_description, color=0xFF0000)
            toggle_button = Button(label="Toggle Output Style", style=discord.ButtonStyle.green, custom_id=interaction.data.get('custom_id'))

            view = View()
            view.add_item(toggle_button)
            await interaction.response.edit_message(embed=new_embed, view=view)
        else:
            print("Report not found.")

client.run(BOT_TOKEN)

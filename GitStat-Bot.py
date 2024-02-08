import discord
from collections import defaultdict
from datetime import datetime, timedelta
import asyncio



# Predefined variables
CHANNEL_ID = ''
BOT_TOKEN = ''
authors_list = ["???",]



intents = discord.Intents.all()
intents.messages = True

client = discord.Client(intents=intents)

# Initialize data structure with authors and set initial counts to 0
activity_counts = {
    'Pull request opened': defaultdict(int, {author: 0 for author in authors_list}),
    'Issue opened': defaultdict(int, {author: 0 for author in authors_list})
}

# Last reset time
last_reset_time = datetime.now()

async def reset_counts():
    print("Resetting counts...")
    for activity in activity_counts:
        for author in authors_list:
            activity_counts[activity][author] = 0
    print("Counts after reset:", activity_counts)

async def send_report():
    global last_reset_time
    channel = client.get_channel(int(CHANNEL_ID))  # Ensure CHANNEL_ID is an integer
    if channel:
        # Start building the embed description with a table-like header
        embed_description = "```"
        embed_description += "Author              | PR Opened | Issues Opened\n"
        embed_description += "-" * 50  # Adjust based on the width of your table
        embed_description += "\n"

        # Temporary dictionary to store combined data for easier table generation
        combined_counts = {author: {"Pull request opened": 0, "Issue opened": 0} for author in authors_list}

        # Combine the data from activity_counts into combined_counts for easier handling
        for activity, users in activity_counts.items():
            for user, count in users.items():
                if user in combined_counts:
                    combined_counts[user][activity] = count

        # Add each user and their counts to the table
        for user, activities in combined_counts.items():
            pr_count = activities["Pull request opened"]
            issue_count = activities["Issue opened"]
            # Check if both counts are 0 and append a warning symbol if true
            warning_symbol = " ⚠️" if pr_count == 0 and issue_count == 0 else ""
            embed_description += f"{user: <18} | {pr_count: <10} | {issue_count: <12}{warning_symbol}\n"

        # Close the code block to end the table
        embed_description += "```"

        # Create and send the embed
        embed = discord.Embed(title="Biweekly Contribution Report", description=embed_description, color=0xFF0000)
        await channel.send(embed=embed)

    last_reset_time = datetime.now()



async def background_task():
    await client.wait_until_ready()
    while not client.is_closed():
        if datetime.now() - last_reset_time >= timedelta(seconds=5):  # Adjust for actual use
            await send_report()
        await asyncio.sleep(1)  # Check interval

@client.event
async def on_ready():
    print(f'We have logged in as {client.user}')
    client.loop.create_task(background_task())

@client.event
async def on_message(message):
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

            # Print embed author for debugging
            embed_author_name = embed.author.name if embed.author else "No author"
            print(f"Embed author: {embed_author_name}")
            
            # Check if the embed author is in our predefined list
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

    if message.content.startswith('!hi'):
        await message.channel.send('Hello!')

client.run(BOT_TOKEN)

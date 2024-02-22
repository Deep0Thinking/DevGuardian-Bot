import discord
from discord.ui import Button, View
from discord.ext import commands
from discord import app_commands
from collections import defaultdict
from datetime import datetime
import asyncio
import aiohttp
import json
import config
import re
import DevGuardian_Bot_functions as DGB



CHANNEL_ID = config.CHANNEL_ID
SERVER_ID = config.SERVER_ID
BOT_TOKEN = config.BOT_TOKEN 
AUTHORS_LIST = config.AUTHORS_LIST
DISCORD_USER_IDS_LIST = config.DISCORD_USER_IDS_LIST
CURRENT_STYLE = config.CURRENT_STYLE
REPORT_INTERVAL = config.REPORT_INTERVAL
PERIODIC_CONTRIBUTIONS_HISTORY_FILE = config.PERIODIC_CONTRIBUTIONS_HISTORY_FILE
TOTAL_CONTRIBUTIONS_FILE = config.TOTAL_CONTRIBUTIONS_FILE
FORMAL_WARNINGS_FILE = config.FORMAL_WARNINGS_FILE
MIN_PERIODIC_CONTRIBUTIONS = config.MIN_PERIODIC_CONTRIBUTIONS
MAX_FORMAL_WARNINGS = config.MAX_FORMAL_WARNINGS
CONTRIBUTION_IMPORTANCE_FILE = config.CONTRIBUTION_IMPORTANCE_FILE
CORE_MEMBER_ROLE_NAME = config.CORE_MEMBER_ROLE_NAME
GITHUB_TOKEN = config.GITHUB_TOKEN
DOC_URL = config.DOC_URL
CURRENT_OPEN_PR_ISSUE_FILE = config.CURRENT_OPEN_PR_ISSUE_FILE
IMPORTANCES_LIST = config.IMPORTANCES_LIST
AREAS_LIST = config.AREAS_LIST



bot = commands.Bot(command_prefix="!", intents=discord.Intents.all())

@bot.tree.command(name="test", description="Test the command")
async def test(interaction: discord.Interaction):
    await interaction.response.send_message("Test command executed.") # add `ephemeral=True` to make the response `Only you can see this`.

@bot.tree.command(name="license", description="Show a specific section of the license")
@app_commands.describe(section="The section number of the license to display")
async def license(interaction: discord.Interaction, section: str):

    license_doc = await fetch_license(DOC_URL, GITHUB_TOKEN)
    extracted_section = extract_section(license_doc, section)
    messages = split_message(extracted_section, 2000 - 10)

    if not messages:
        await interaction.response.defer(ephemeral=True)
        await interaction.followup.send(f"Section `{section}` not found. Please ensure the section number is correct and try again.")
        return
    
    await interaction.response.defer()
    for msg in messages:
        msg = f"```{msg}```"
        await interaction.followup.send(msg)

@bot.tree.command(name="panel", description="Show the panel")
async def panel(interaction: discord.Interaction):
    calculate_button = Button(label="Total Contribs Report", style=discord.ButtonStyle.blurple, custom_id="display_total_contributions")
    warnings_button = Button(label="Total FWs Report", style=discord.ButtonStyle.red, custom_id="display_total_formal_warnings")
    importance_button = Button(label="Contribs Imp Report", style=discord.ButtonStyle.green, custom_id="display_contribution_importance")
    add_importance_instruction_button = Button(label="Add Contribs Imp", style=discord.ButtonStyle.grey, custom_id="add_importance_instruction")
    
    view = View()
    view.add_item(calculate_button)
    view.add_item(warnings_button)
    view.add_item(importance_button)
    view.add_item(add_importance_instruction_button)
    await interaction.response.send_message(view=view)

@bot.tree.command(name="add_contribs_imp", description="Tag a member's contribution with an importance level")
@app_commands.describe(member="The member to tag", importance="The importance level of the contribution", number="The number to adjust the importance by (default: +1)")
@app_commands.choices(importance=[
    app_commands.Choice(name='5️⃣ critical', value='5️⃣ critical'),
    app_commands.Choice(name='4️⃣ significant', value='4️⃣ significant'),
    app_commands.Choice(name='3️⃣ notable', value='3️⃣ notable'),
    app_commands.Choice(name='2️⃣ moderate', value='2️⃣ moderate'),
    app_commands.Choice(name='1️⃣ minor', value='1️⃣ minor')
])
async def add_contribs_imp(interaction: discord.Interaction, member: discord.Member, importance: app_commands.Choice[str], number: int = 1):
    if interaction.guild is None:
        await interaction.response.send_message("This command cannot be used in private messages.", ephemeral=True)
        return
    elif interaction.guild.id != SERVER_ID:
        await interaction.response.send_message("This command can only be used within the specific server.", ephemeral=True)
        return
        
    if not is_admin(interaction):
        await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
        return
    
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    issuer = interaction.user.name

    await update_contribution_importance(interaction, member.id, issuer, importance.value, now, number)

    author_name = id_to_name(member.id)

    if author_name:
        number_with_sign = f"+{number}" if number > 0 else str(number)
        await interaction.response.defer(ephemeral=False)
        await interaction.followup.send(f"`{importance.name}` `{number_with_sign}` to {member.mention}'s contributions.")
        if importance.value == '4️⃣ significant' or importance.value == '5️⃣ critical':
            with open(FORMAL_WARNINGS_FILE, 'r') as file:
                warnings_data = json.load(file)
                total_warnings = 0
                for data in warnings_data:
                    if data['author'] != author_name:
                        continue
                    total_warnings += data['warning_count']
                
                if total_warnings > 0:

                    new_warning_record = {
                        "author": author_name,
                        "warning_time": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        "warning_count": -1 
                    }
                    warnings_data.append(new_warning_record)
                    
                    with open(FORMAL_WARNINGS_FILE, 'w') as file:
                        json.dump(warnings_data, file, indent=4)

                    await interaction.followup.send(f"📝 **Formal Warning Adjustment** 📝\n\n<@{member.id}>, in accordance with section 4.2 of the CruxAbyss Development Team License Agreement, `1` **formal warning** has been officially **removed** from your record due to your `{importance.value}` contribution. Your commitment to the project and adherence to our collective standards of conduct and contribution is greatly appreciated.")
                
            qualifies_for_core_member, _, _ = await check_core_member_qualification(author_name)

            if qualifies_for_core_member:
                core_member_role = discord.utils.get(interaction.guild.roles, name=CORE_MEMBER_ROLE_NAME)
                if core_member_role and core_member_role not in member.roles:
                    await member.add_roles(core_member_role)
                    await interaction.followup.send(f"🌟 **Core Member Designation** 🌟\n\n{member.mention} has made `5` or more `significant` **contributions** and is now designated as a **Core Member** of the CruxAbyss Development Team. Core Members have the right to vote on critical decisions and are the only members eligible to serve as reviewers for `pull requests`, ensuring a high standard of quality and consistency in the development process.")
                else:
                    print(f"Role '{CORE_MEMBER_ROLE_NAME}' not found or member already has the role.")

activity_counts = {
    'Pull request opened': defaultdict(int, {author: 0 for author in AUTHORS_LIST}),
    'Issue opened': defaultdict(int, {author: 0 for author in AUTHORS_LIST})
}

last_reset_time = datetime.now()

report_title = ""

@bot.event
async def on_ready():
    print(f'We have logged in as {bot.user}')
    synced = await bot.tree.sync()
    print(f'Synced {len(synced)} command (s)') # Restart your discord to see the changes
    bot.loop.create_task(background_task())
    bot.loop.create_task(periodic_open_pr_issue_check())  # Start the periodic label check task

async def background_task():
    await bot.wait_until_ready()
    while not bot.is_closed():
        if datetime.now() - last_reset_time >= REPORT_INTERVAL:
            await send_report(CURRENT_STYLE)
        await asyncio.sleep(1)

def is_admin(interaction: discord.Interaction) -> bool:
    if interaction.guild:
        member = interaction.guild.get_member(interaction.user.id)
        return member.guild_permissions.administrator
    else:
        return False
 
def id_to_name(author_id):
    for idx, discord_id in enumerate(DISCORD_USER_IDS_LIST):
        if str(discord_id) == str(author_id):
            return AUTHORS_LIST[idx]
    return None

def name_to_id(author):
    for idx, name in enumerate(AUTHORS_LIST):
        if name == author:
            return DISCORD_USER_IDS_LIST[idx]
    return None

async def fetch_and_process_github_data(url, record_type, author_name):
    api_url = DGB.url_to_api_url(url)
    async with aiohttp.ClientSession() as session:
        async with session.get(api_url, headers={
            "Authorization": f"token {GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3+json"
        }) as response:
            if response.status == 200:
                data = await response.json()
                labels = [label["name"] for label in data.get("labels", [])]
                state = data["state"]

                parts = url.split('/')
                pr_or_issue_id = parts[6]

                if state == "closed":
                    if (record_type == "Pull Request") and (data["pull_request"]["merged_at"] is not None):
                        if DGB.meaningful_labels_verification(labels):
                            if (await DGB.check_pr_latest_importance_labeling_action(url)):
                                await update_contribution_importance(None, name_to_id(author_name), "CruxAbyss Bot", labels, datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
                                remove_record_from_current_open_pr_issue_file(pr_or_issue_id)
                                print("blabla")
                                # xx ????????????????????
                            else:
                                await DGB.update_pr_issue(url, state="open", comment="This PR/issue should be reinspected due to invalid `Importance` labeler.\n\nOnly **Core Members** are allowed to label the `Importance`.")
                                print("This PR/issue should be reinspected due to invalid `Importance` labeler. Only **Core Members** are allowed to label the `Importance`.")
                                await DGB.undo_invalid_pr_importance_labeling_action(session, url, labels)
                                remove_record_from_current_open_pr_issue_file(pr_or_issue_id)
                                print("Undone invalid `Importance` labeling actions.")
                                # ????????????????????
                        elif len(labels) == 0:
                            remove_record_from_current_open_pr_issue_file(pr_or_issue_id)
                            print("Meaningless PR without any labels.")
                            # ????????????????????
                        else:
                            remove_record_from_current_open_pr_issue_file(pr_or_issue_id)
                            await DGB.update_pr_issue(url, state="open", comment="This PR/issue has been reopened due to invalid labeling.\n\nOnly `0` label (for meaningless PR/issue) and `2` labels (`1` `Importance` and `1` `Area` for meaningful PR/issue) are allowed.")
                            print("Labels do not meet the conditions.")
                    elif (record_type == "Issue"):
                        if DGB.meaningful_labels_verification(labels):
                            if (await DGB.check_issue_latest_importance_labeling_action(url)):
                                await update_contribution_importance(None, name_to_id(author_name), "CruxAbyss Bot", labels, datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
                                remove_record_from_current_open_pr_issue_file(pr_or_issue_id)
                                print("blabla")
                                # xx ????????????????????
                            else:
                                await DGB.update_pr_issue(url, state="open", comment="This PR/issue has been reopened due to invalid `Importance` labeler.\n\nOnly **Core Members** are allowed to label the `Importance`.")
                                print("This PR/issue has been reopened due to invalid `Importance` labeler. Only **Core Members** are allowed to label the `Importance`.")
                                await DGB.undo_invalid_issue_importance_labeling_action(session, url, labels)
                                print("Undone invalid `Importance` labeling actions.")
                                # ????????????????????
                        elif len(labels) == 0:
                            remove_record_from_current_open_pr_issue_file(pr_or_issue_id)
                            print("Meaningless issue without any labels.")
                            # ????????????????????
                        else:
                            remove_record_from_current_open_pr_issue_file(pr_or_issue_id)
                            await DGB.update_pr_issue(url, state="open", comment="This PR/issue has been reopened due to invalid labeling.\n\nOnly `0` label (for meaningless PR/issue) and `2` labels (`1` `Importance` and `1` `Area` for meaningful PR/issue) are allowed.")
                            print("Labels do not meet the conditions.")
                    else:
                        remove_record_from_current_open_pr_issue_file(pr_or_issue_id)
                        print(f"Closed {record_type} not merged due to meaningless state.")
            else:
                print(f"Failed to fetch data for {api_url}. Status code: {response.status}")

def remove_record_from_current_open_pr_issue_file(record_id):
    try:
        with open(CURRENT_OPEN_PR_ISSUE_FILE, 'r+') as file:
            records = json.load(file)
            record_id = int(record_id)
            records = [record for record in records if record['id'] != record_id]
            file.seek(0)
            file.truncate()
            json.dump(records, file, indent=4)
    except FileNotFoundError:
        print("Current_open_pr_issue file not found.")

async def fetch_license(url, token):
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3.raw"
    }
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as response:
            if response.status == 200:
                text = await response.text()
                return text
            else:
                return f"Failed to fetch the license documentation. HTTP Status: {response.status}"

def split_message(message, length=2000):
    return [message[i:i+length] for i in range(0, len(message), length)]

def extract_section(document, section_number):
    lines = document.split('\n')
    section_start = f"{section_number}"
    section_content = []
    recording = False

    print(f"Looking for section: '{section_start}'")

    def is_new_section(line, current_section):
        current_parts = current_section.split('.')
        current_main = int(current_parts[0]) if current_parts[0].isdigit() else 0
        current_sub = int(current_parts[1]) if len(current_parts) > 1 and current_parts[1].isdigit() else 0
        potential_parts = line.partition(' ')[0].split('.')
        potential_main = int(potential_parts[0]) if potential_parts[0].isdigit() else 0
        potential_sub = int(potential_parts[1]) if len(potential_parts) > 1 and potential_parts[1].isdigit() else 0
        
        if potential_main > current_main:
            return True
        elif potential_main == current_main:
            return potential_sub > current_sub
        return False

    for line in lines:
        if line.strip().startswith(section_start):
            print(f"Started recording at: '{line.strip()[:50]}'")
            recording = True
            section_content.append(line)
        elif recording and is_new_section(line.strip(), section_start[:-1]):
            print(f"Stopping recording at new section: '{line.strip()[:50]}'")
            break
        elif recording:
            section_content.append(line)

    if not section_content:
        print("No content found for the specified section. Ensure section number is in the document and formatted as expected.")
        return ""
    else:
        print(f"Content found for section {section_number}.")
        return '\n'.join(section_content)

async def update_contribution_importance(interaction, author_id, issuer, labels, issued_time, number=1):
    
    if len(labels) != 2 and len(labels) != 3:
        raise ValueError("Labels list must be of length 2 or 3.")
    
    importance_label = next((label for label in labels if label in IMPORTANCES_LIST), None)
    area_label = next((label for label in labels if label in AREAS_LIST), None)

    if not importance_label or not area_label:
        raise ValueError("One label must be from the importance levels and the other from the contribution areas.")
    
    author_name = id_to_name(author_id)
    if author_name is None:
        await interaction.response.defer(ephemeral=True)
        await interaction.followup.send(f"Could not find an author name for the given ID: {author_id}")
        return
    
    try:
        with open(CONTRIBUTION_IMPORTANCE_FILE, 'r+') as file:
            try:
                data = json.load(file)
            except json.JSONDecodeError:
                data = []
            
            record = next((item for item in data if item['author'] == author_name), None)
            if record:
                record['area'] = area_label
                record['importance'] = importance_label
                record['count'] = str(int(record.get('count', '0')) + number)
            else:
                data.append({
                    'author': author_name,
                    'issued_time': issued_time,
                    'issuer': issuer,
                    'area': area_label,
                    'importance': importance_label,
                    'count': str(number)
                })
            
            file.seek(0)
            file.truncate()
            json.dump(data, file, indent=4)
            
    except FileNotFoundError:
        with open(CONTRIBUTION_IMPORTANCE_FILE, 'w') as file:
            json.dump([{
                'author': author_name,
                'issued_time': issued_time,
                'issuer': issuer,
                'area': area_label,
                'importance': importance_label,
                'count': str(number)
            }], file, indent=4)

    print("Contribution updated!")

def check_core_member_qualification(author_name):
    try:
        with open(CONTRIBUTION_IMPORTANCE_FILE, 'r') as file:
            data = json.load(file)
    except FileNotFoundError:
        print("Contribution importance file not found.")
        return False, 0, 0

    total_significant = 0
    total_critical = 0
    for record in data:
        if record['author'] == author_name:
            total_significant += record.get('4️⃣ significant', 0)
            total_critical += record.get('5️⃣ critical', 0)

    qualifies_for_core_member = total_significant >= 5 or total_critical >= 1
    return qualifies_for_core_member, total_significant, total_critical

async def calculate_and_display_contribution_importance(channel, interaction=None):
    importance_counts = defaultdict(lambda: defaultdict(int))
    for author in AUTHORS_LIST:
        for importance in IMPORTANCES_LIST:
            importance_counts[author][importance] = 0

    try:
        with open(CONTRIBUTION_IMPORTANCE_FILE, 'r') as file:
            contributions_data = json.load(file)
            for record in contributions_data:

                author_lower = {a.lower(): a for a in AUTHORS_LIST}
                record_author = author_lower.get(record['author'].lower())
                if record_author:
                    for importance, count in record.items():
                        if importance in importance_counts[record_author]:
                            importance_counts[record_author][importance] += count
    except FileNotFoundError:
        print("Contribution importance data file not found.")
    
    try:
        with open(PERIODIC_CONTRIBUTIONS_HISTORY_FILE, 'r') as file:
            reports = json.load(file)
    except FileNotFoundError:
        await channel.send("Periodic contributions history file not found. Need periodic contributions history to generate the contribution importance report.")
        return

    start_time_str = min(report['start_time'] for report in reports)
    end_time_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    embed_description = generate_embed_description_for_importance(CURRENT_STYLE, importance_counts)
    embed = discord.Embed(title=f"Contribution Importance Report\n\n`{start_time_str}` to `{end_time_str}`", description=embed_description, color=0x4895EF)
    toggle_button = Button(label="Toggle Output Style", style=discord.ButtonStyle.green, custom_id="toggle_importance_style")
    
    view = View()
    view.add_item(toggle_button)
    
    if interaction:
        await interaction.edit_original_response(embed=embed, view=view)
    else:
        await channel.send(embed=embed, view=view)

def generate_embed_description_for_importance(style, importance_counts):
    embed_description = ""
    authors_contributions_importance_index = []

    if style:  # Alternate Style
        embed_description += "\n"
        for index, author in enumerate(AUTHORS_LIST):
            counts = importance_counts[author]
            authors_contributions_importance_index.append(index)
            embed_description += f"<@{DISCORD_USER_IDS_LIST[index]}>\n"
            embed_description += "".join(f"> {importance.capitalize()}: `{counts[importance]}`\n" for importance in IMPORTANCES_LIST)
            
    else:  # Table-like style
        embed_description += "```"
        headers = "Author             | Cri | Sig | Not | Mod | Min\n"
        separator = "-" * 51 + "\n"
        embed_description += headers + separator
        for author in AUTHORS_LIST: 
            counts = importance_counts[author]
            row = f"{author: <18} | "
            row += " | ".join([f"{counts[importance]: <3}" for importance in IMPORTANCES_LIST])
            embed_description += row + "\n"
        embed_description += "```"
    return embed_description

def save_formal_warnings(authors_list, warning_time=None):
    if warning_time is None:
        warning_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    for author_name in authors_list:
        warning_data = {
            'author': author_name,
            'warning_time': warning_time,
            'warning_count': 1
        }

        try:
            with open(FORMAL_WARNINGS_FILE, 'r+') as file:
                try:
                    data = json.load(file)
                except json.JSONDecodeError:
                    data = []
                # Check if the author already has a warning on the same time to prevent duplicates
                existing_warning = next((item for item in data if item['author'] == author_name and item['warning_time'] == warning_time), None)
                if not existing_warning:
                    data.append(warning_data)
                    file.seek(0)
                    file.truncate(0)  # Clear the file before rewriting
                    json.dump(data, file, indent=4)
        except FileNotFoundError:
            with open(FORMAL_WARNINGS_FILE, 'w') as file:
                json.dump([warning_data], file, indent=4)

        print(f"Formal warning saved for {author_name} on {warning_time}.")

async def total_formal_warnings_report(channel, interaction=None):
    try:
        with open(FORMAL_WARNINGS_FILE, 'r') as file:
            warnings_data = json.load(file)
    except FileNotFoundError:
        warnings_data = []  

    warnings_count = {author: 0 for author in AUTHORS_LIST}
    members_to_expel = []
    members_to_expel_index = []
    for warning in warnings_data:
        author = warning['author']
        if author in warnings_count: 
            warnings_count[author] += warning['warning_count']
    for author in warnings_count:
        if warnings_count[author] > MAX_FORMAL_WARNINGS and author not in members_to_expel:
                members_to_expel.append(author)
                members_to_expel_index.append(AUTHORS_LIST.index(author))

    embed_description = ""
    if CURRENT_STYLE:  # Alternate Style
        for index, author in enumerate(AUTHORS_LIST):
            count = warnings_count[author]
            warning_symbol = " ❗️" if count > MAX_FORMAL_WARNINGS else ""
            embed_description += f"<@{DISCORD_USER_IDS_LIST[index]}>\n> FW: `{count}`{warning_symbol}\n"
    else:  # Table-like Style
        embed_description = "```Author             | FW Count\n"
        embed_description += "-" * 32 + "\n"
        for author in AUTHORS_LIST:
            count = warnings_count[author]
            warning_symbol = " ❗️" if count > MAX_FORMAL_WARNINGS else ""
            embed_description += f"{author: <18} | {count: <8}{warning_symbol}\n"
        embed_description += "```"

    if members_to_expel:
        warning_members = ", ".join([f"`{author}`" for author in members_to_expel])
        warning_members_ID = ", ".join([f"<@{DISCORD_USER_IDS_LIST[author_index]}>" for author_index in members_to_expel_index])
        expulsion_message = "**Members to be Expelled**\n\n"
        expulsion_message += f"{warning_members_ID if CURRENT_STYLE else warning_members} should be expelled due to accumulating `{MAX_FORMAL_WARNINGS + 1}` or more **formal warnings**, in accordance with the CruxAbyss Development Team License Agreement, section 4.2 Members who accumulate 2 formal warnings will be expelled from the Development Team.\n"
        embed_description += "\n" + expulsion_message

    try:
        with open(PERIODIC_CONTRIBUTIONS_HISTORY_FILE, 'r') as file:
            reports = json.load(file)
    except FileNotFoundError:
        await channel.send("Periodic contributions history file not found. Need periodic contributions history to generate the total formal warnings report.")
        return

    start_time_str = min(report['start_time'] for report in reports)
    end_time_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    embed = discord.Embed(title=f"Formal Warnings Report\n\n`{start_time_str}` to `{end_time_str}`", description=embed_description, color=0xFF0000)
    toggle_button = Button(label="Toggle Output Style", style=discord.ButtonStyle.green, custom_id="toggle_formal_warnings_style")
    view = View()
    view.add_item(toggle_button)
    
    if interaction:
        await interaction.edit_original_response(embed=embed, view=view)
    else:
        await channel.send(embed=embed, view=view)

def save_history(start_time_str, current_time_str):
    history_data = {
        'start_time': start_time_str,
        'end_time': current_time_str,
        'report_title': report_title,
        'activity_counts': {activity: dict(counts) for activity, counts in activity_counts.items()}
    }
    try:
        with open(PERIODIC_CONTRIBUTIONS_HISTORY_FILE, 'r+') as file:
            data = json.load(file)
            data.append(history_data)
            file.seek(0)
            file.truncate(0)  # Clear the file before rewriting
            json.dump(data, file, indent=4)
    except FileNotFoundError:
        with open(PERIODIC_CONTRIBUTIONS_HISTORY_FILE, 'w') as file:
            json.dump([history_data], file, indent=4)

def reset_counts():
    global activity_counts
    for activity in activity_counts:
        for author in AUTHORS_LIST:
            activity_counts[activity][author] = 0
    print("Counts after reset:", activity_counts)

def generate_embed_description(style, activity_counts_param, include_warnings=True):
    embed_description = ""
    authors_with_warnings = []  # Track authors who will receive formal warnings only if include_warnings is True
    authors_with_warnings_index = []

    if style:  # Alternate style
        embed_description += "\n"
        for index, author in enumerate(AUTHORS_LIST):
            pr_count = activity_counts_param.get('Pull request opened', {}).get(author, 0)
            issue_count = activity_counts_param.get('Issue opened', {}).get(author, 0)
            if include_warnings:
                warning_symbol = " ⚠️" if (pr_count + issue_count) < MIN_PERIODIC_CONTRIBUTIONS else ""
                if warning_symbol:
                    authors_with_warnings.append(author)
                    authors_with_warnings_index.append(index)
            else:
                warning_symbol = ""
            embed_description += f"<@{DISCORD_USER_IDS_LIST[index]}>\n> PR: `{pr_count}`\n> Issues: `{issue_count}`{warning_symbol}\n"
    else:  # Table-like style
        embed_description += "```"
        embed_description += "Author             | PR Opened  | Issues Opened\n"
        embed_description += "-" * 50 + "\n"
        for author in AUTHORS_LIST:
            pr_count = activity_counts_param.get('Pull request opened', {}).get(author, 0)
            issue_count = activity_counts_param.get('Issue opened', {}).get(author, 0)
            if include_warnings:
                warning_symbol = " ⚠️" if (pr_count + issue_count) < MIN_PERIODIC_CONTRIBUTIONS else ""
                if warning_symbol:
                    authors_with_warnings.append(author)
                    authors_with_warnings_index.append(AUTHORS_LIST.index(author))
            else:
                warning_symbol = ""
            embed_description += f"{author: <18} | {pr_count: <10} | {issue_count: <13}{warning_symbol}\n"
        embed_description += "```"

    if include_warnings and authors_with_warnings:
        warning_members = ", ".join([f"`{author}`" for author in authors_with_warnings])
        warning_members_ID = ", ".join([f"<@{DISCORD_USER_IDS_LIST[author_index]}>" for author_index in authors_with_warnings_index])
        embed_description += "\n**Formal Warnings Issued**\n\n"
        embed_description += f"{warning_members_ID if style else warning_members} **received** `1` **formal warning** due to non-compliance with the CruxAbyss Development Team License Agreement, section 3.2 Each member must make at least 1 'minor' contribution to the Project every 2 weeks. Failure to meet this requirement results in the issuance of 1 formal warning. 1 'significant' contribution can eliminate 1 formal warning."

    return (embed_description, authors_with_warnings) if include_warnings else embed_description
    
async def send_report(style):
    global last_reset_time
    global report_title

    channel = bot.get_channel(CHANNEL_ID)
    if channel:
        current_time = datetime.now()
        start_time = current_time - REPORT_INTERVAL
        start_time_str = start_time.strftime('%Y-%m-%d %H:%M:%S')
        current_time_str = current_time.strftime('%Y-%m-%d %H:%M:%S')

        report_title = f"Periodic Contributions Report\n\n`{start_time_str}` to `{current_time_str}`"

        embed_description, authors_with_fw = generate_embed_description(style, activity_counts)
        embed = discord.Embed(title=report_title, description=embed_description, color=0xFF0000)
        if authors_with_fw:  
            save_formal_warnings(authors_with_fw)

        time_encoded_custom_id = f"toggle_style_{start_time_str}_{current_time_str}".replace(' ', '_').replace(':', '-')
        toggle_button = Button(label="Toggle Output Style", style=discord.ButtonStyle.green, custom_id=time_encoded_custom_id)
        
        view = View()
        view.add_item(toggle_button)
        await channel.send(embed=embed, view=view)

        save_history(start_time_str, current_time_str)
        await reset_counts()

    last_reset_time = current_time
    print(f"Periodic Contributions Report sent: `{start_time_str}` to `{current_time_str}`")

async def periodic_open_pr_issue_check():
    while True:
        try:
            with open(CURRENT_OPEN_PR_ISSUE_FILE, 'r') as file:
                records = json.load(file)

            for record in records:
                url = record.get('url')
                if not url:
                    continue

                async with aiohttp.ClientSession() as session:
                    api_url = DGB.url_to_api_url(url)
                    async with session.get(api_url, headers={
                        "Authorization": f"token {GITHUB_TOKEN}",
                        "Accept": "application/vnd.github.v3+json"
                    }) as response:
                        if response.status == 200:
                            data = await response.json()
                            labels = [label['name'] for label in data.get("labels", [])]
                            if len(labels) == 0:
                                print("Meaningless PR/issue without any labels.")
                            elif labels == ['❔ pending']:
                                if (not record['valid_area_labeled_by_author_time']):
                                    # ????????????????????? send the public notification
                                    await DGB.update_pr_issue(url, comment="Please add 1 appropriate `Area` label for this PR/issue.")
                                    record['valid_area_labeled_by_author_time'] = 'Notified'
                                else:
                                    print("Area label notification already sent.")
                            elif DGB.area_label_verification(labels):
                                print("Valid area label found. Awaiting `Importance` label.")
                                if (not record['valid_area_labeled_by_author_time'] or record['valid_area_labeled_by_author_time'] == 'Notified'):
                                    record['valid_area_labeled_by_author_time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                                if (not record['reviewers']):
                                    current_reviewers = [AUTHORS_LIST[0]]
                                    current_reviewers_str = ', @'.join(current_reviewers)
                                    record['reviewers'] = current_reviewers
                                    await DGB.update_pr_issue(url, reviewers=current_reviewers, comment=f"Reviewer @{current_reviewers_str} is assigned to this PR/issue. Awaiting `Importance` label for this PR/issue.")
                                elif DGB.check_review_deadline_exceeded(record):
                                    if len(labels) == 2:
                                        print("Adding the label `⏰ review deadline exceeded`.")
                                        new_labels = labels + ['⏰ review deadline exceeded']
                                        previous_reviewers = record['reviewers']
                                        previous_reviewers_str = ', @'.join(previous_reviewers)
                                        # ????????????????????? notify previous reviewers
                                        new_reviewers = [AUTHORS_LIST[0]]
                                        new_reviewers_str = ', @'.join(new_reviewers)
                                        await DGB.update_pr_issue(url, labels=new_labels, reviewers=new_reviewers, comment=f"The review deadline for this PR/issue has been exceeded. New reviewer @{new_reviewers_str} is assigned to this PR/issue. Previous reviewers were: @{previous_reviewers_str}.")
                                        # ????????????????????? send the public notification
                                        record['reviewers'] = new_reviewers
                                        record['previous_reviewers'] = previous_reviewers
                                        record['review_ddl_time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                                    else:
                                        print("Label `⏰ review deadline exceeded` has already been added.")
                            elif DGB.meaningful_labels_verification(labels):
                                if (not record['reviewers']):
                                    record['labels'] = ['❔ pending']
                                    record['valid_importance_labeled_by_reviewers_time'] = ''
                                    record['valid_area_labeled_by_author_time'] = ''
                                    record['reviewers'] = []
                                    await DGB.update_pr_issue(url, labels=['❔ pending'], comment="This PR/issue has been relabeled as `❔ pending` due to invalid labeling.")
                                elif (not record['valid_importance_labeled_by_reviewers_time']):
                                    current_reviewers = record['reviewers']
                                    current_reviewers_str = ', @'.join(current_reviewers)
                                    record['reviewers'] = current_reviewers
                                    record['valid_importance_labeled_by_reviewers_time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                                    await DGB.update_pr_issue(url, comment=f"Reviewer @{current_reviewers_str} has added the `Importance` label to this PR/issue.")
                                else:
                                    print("No action needed.")
                            else:
                                record['labels'] = ['❔ pending']
                                record['valid_importance_labeled_by_reviewers_time'] = ''
                                record['valid_area_labeled_by_author_time'] = ''
                                record['reviewers'] = []
                                await DGB.update_pr_issue(url, labels=['❔ pending'], comment="This PR/issue has been relabeled as `❔ pending` due to invalid labeling.")

            with open(CURRENT_OPEN_PR_ISSUE_FILE, 'w') as file:
                json.dump(records, file, indent=4)

        except FileNotFoundError:
            print("Current open PR/Issue records file not found.")

        await asyncio.sleep(5)  # Wait for 30 minutes (1800 seconds) before next iteration


@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    if message.embeds:

        embed_count = len(message.embeds)
        print(f"Message from {message.author} contains {embed_count} embed(s).")

        for embed in message.embeds:

            # DGB.print_embed_message(embed)

            title = embed.title if embed.title else ""
            embed_author_name = embed.author.name if embed.author else "No author"
            
            if "Issue opened:" in title or "Pull request opened:" in title or "Issue reopened:" in title or "Pull request reopened:" in title:
                match = re.search(r'#(\d+)', title)
                if match:
                    record_id = int(match.group(1))
                else:
                    print("Error extracting the PR/issue ID.")
                    return

                record_type = "Issue" if ("Issue" in title) else "Pull Request"
                record_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
                record = {
                    'id': record_id,
                    'type': record_type,
                    'time': record_time,
                    'valid_area_labeled_by_author_time': '',
                    'valid_importance_labeled_by_reviewers_time': '',
                    'author': embed_author_name,
                    'reviewers': [],
                    'url': embed.url,
                    'labels': [],
                }

                try:
                    with open(CURRENT_OPEN_PR_ISSUE_FILE, 'r') as file:
                        records = json.load(file)
                except FileNotFoundError:
                    records = []

                existing_record = next((item for item in records if item['id'] == record_id), None)

                if existing_record == None:
                    records.append(record)
                else:
                    print("Record already exists.")
                    pass

                with open(CURRENT_OPEN_PR_ISSUE_FILE, 'w') as file:
                    json.dump(records, file, indent=4)

                record_id = int(match.group(1))

                
                if "Issue opened:" in title or "Pull request opened:" in title:
                    await DGB.update_pr_issue(embed.url, labels=['❔ pending'], reviewers=[]) 
                    # ?????????????????
                
            if "Issue closed:" in title or "Pull request closed:" in title:
                match = re.search(r'#(\d+)', title)
                if match:
                    record_id = int(match.group(1))
                    record_type = "Issue" if ("Issue" in title) else "Pull Request"
                    if embed.url:
                        await fetch_and_process_github_data(embed.url, record_type, embed_author_name)
                    else:
                        print("Error extracting URL details.")
                else:
                    print("Error extracting the PR/issue ID.")


async def calculate_and_display_total_contributions(channel, interaction=None, toggle=False):
    if toggle:
        # When toggling, read from the total contributions file instead of recalculating
        try:
            with open(TOTAL_CONTRIBUTIONS_FILE, 'r') as file:
                total_data = json.load(file)
                start_time_str = total_data['start_time']
                end_time_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                total_activity_counts = total_data['activity_counts']
        except FileNotFoundError:
            await channel.send("Total contributions data file not found.")
            return
    else:
        # Calculate total contributions and save to file
        try:
            with open(PERIODIC_CONTRIBUTIONS_HISTORY_FILE, 'r') as file:
                reports = json.load(file)
                if not reports:
                    await channel.send("No report history found.")
                    return

                total_activity_counts = defaultdict(lambda: defaultdict(int))
                for report in reports:
                    for activity, counts in report['activity_counts'].items():
                        for author, count in counts.items():
                            total_activity_counts[activity][author] += count

                start_time_str = min(report['start_time'] for report in reports)
                end_time_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                total_data = {
                    'start_time': start_time_str,
                    'end_time': end_time_str,
                    'activity_counts': {activity: dict(counts) for activity, counts in total_activity_counts.items()}
                }
                with open(TOTAL_CONTRIBUTIONS_FILE, 'w') as outfile:
                    json.dump(total_data, outfile, indent=4)
        except FileNotFoundError:
            await channel.send("Periodic contributions history file not found.")
            return

    total_report_title = f"Total Contributions Report\n\n`{start_time_str}` to `{end_time_str}`"
    total_embed_description = generate_embed_description(CURRENT_STYLE, total_activity_counts, include_warnings=False)
    total_embed = discord.Embed(title=total_report_title, description=total_embed_description, color=0x4895EF)
    toggle_button = Button(label="Toggle Output Style", style=discord.ButtonStyle.green, custom_id="toggle_total_style")
    view = View()
    view.add_item(toggle_button)
    
    if interaction:
        await interaction.edit_original_response(embed=total_embed, view=view)
    else:
        await channel.send(embed=total_embed, view=view)

@bot.event
async def on_interaction(interaction):
    global CURRENT_STYLE
    if interaction.type == discord.InteractionType.component:
        if interaction.data.get('custom_id') == "add_importance_instruction":
            instruction_message = "To assign a contribution importance level to a member, use the command `/add_contribs_imp`. "
            instruction_message += "You'll need to specify the member, the importance level of their contribution, and the number of contributions at that level.\n\n"
            instruction_message += "Example 1: `/add_contribs_imp member:@User importance:5️⃣ critical number:2`.\n\n"
            instruction_message += "Example 2: `/add_contribs_imp member:@User importance:3️⃣ notable number:-1`.\n\n"
            instruction_message += "**Important Restrictions**:\n"
            instruction_message += "- **Server Limitation**: This command is exclusive to the **CruxAbyss** server.\n"
            instruction_message += "- **Permission Requirement**: Only **admin** roles are authorized to use this command."
            await interaction.response.send_message(instruction_message, ephemeral=True)
        elif interaction.data.get('custom_id') == "toggle_importance_style":
            await interaction.response.defer()
            CURRENT_STYLE = not CURRENT_STYLE
            await calculate_and_display_contribution_importance(interaction.channel, interaction=interaction)
        elif interaction.data.get('custom_id') == "display_contribution_importance":
            await interaction.response.defer()
            await calculate_and_display_contribution_importance(interaction.channel, interaction=None)
        elif interaction.data.get('custom_id') == "display_total_formal_warnings":
            await interaction.response.defer()
            await total_formal_warnings_report(interaction.channel, interaction=None)
            return
        elif interaction.data.get('custom_id') == "toggle_formal_warnings_style":
            await interaction.response.defer()
            CURRENT_STYLE = not CURRENT_STYLE
            await total_formal_warnings_report(interaction.channel, interaction=interaction)
        elif interaction.data.get('custom_id') == "display_total_contributions":
            await interaction.response.defer()
            await calculate_and_display_total_contributions(interaction.channel, interaction=None, toggle=False)
            return
        elif interaction.data.get('custom_id') == "toggle_total_style":
            await interaction.response.defer()
            CURRENT_STYLE = not CURRENT_STYLE
            await calculate_and_display_total_contributions(interaction.channel, interaction=interaction, toggle=True)
            return
        elif interaction.data.get('custom_id').startswith("toggle_style"):
            parts = interaction.data.get('custom_id').replace("toggle_style_", "").split('_')
            start_time_parts = parts[0:2]
            current_time_parts = parts[2:4]

            start_time_str = f"{start_time_parts[0]} {start_time_parts[1].replace('-', ':')}"
            current_time_str = f"{current_time_parts[0]} {current_time_parts[1].replace('-', ':')}"

            print(f"Formatted for search - Start Time: {start_time_str}, Current Time: {current_time_str}")

            report_data = binary_search_report(start_time_str)

            if report_data:
                print(f"Report Data Found: {report_data}")

                report_title = f"Periodic Contributions Report\n\n`{report_data['start_time']}` to `{report_data['end_time']}`"

                CURRENT_STYLE = not CURRENT_STYLE
                new_embed_description = generate_embed_description(CURRENT_STYLE, report_data['activity_counts'])[0]
                new_embed = discord.Embed(title=report_title, description=new_embed_description, color=0xFF0000)
                toggle_button = Button(label="Toggle Output Style", style=discord.ButtonStyle.green, custom_id=interaction.data.get('custom_id'))

                view = View()
                view.add_item(toggle_button)
                await interaction.response.edit_message(embed=new_embed, view=view)
            else:
                print("Report not found.")

def binary_search_report(start_time_str, file_path=PERIODIC_CONTRIBUTIONS_HISTORY_FILE):
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

bot.run(BOT_TOKEN)
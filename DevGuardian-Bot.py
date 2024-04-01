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
FORMAL_WARNINGS_FILE = config.FORMAL_WARNINGS_FILE
MIN_PERIODIC_CONTRIBUTIONS = config.MIN_PERIODIC_CONTRIBUTIONS
MAX_FORMAL_WARNINGS = config.MAX_FORMAL_WARNINGS
CONTRIBUTIONS_HISTORY_FILE = config.CONTRIBUTIONS_HISTORY_FILE
CORE_MEMBER_ROLE_NAME = config.CORE_MEMBER_ROLE_NAME
GITHUB_TOKEN = config.GITHUB_TOKEN
DOC_URL = config.DOC_URL
CURRENT_OPEN_PR_ISSUE_FILE = config.CURRENT_OPEN_PR_ISSUE_FILE
IMPORTANCES_LIST = config.IMPORTANCES_LIST
AREAS_LIST = config.AREAS_LIST
CORE_MEMBERS_LIST = config.CORE_MEMBERS_LIST
REPO_NAME = config.REPO_NAME
MAIN_BRANCH = config.MAIN_BRANCH



file_access_lock = asyncio.Lock()

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
    importance_button = Button(label="Contribs Report", style=discord.ButtonStyle.green, custom_id="display_contributions")
    warnings_button = Button(label="FWs Report", style=discord.ButtonStyle.red, custom_id="display_total_formal_warnings")
    add_importance_instruction_button = Button(label="Add Contribs", style=discord.ButtonStyle.grey, custom_id="add_importance_instruction")
    
    view = View()
    view.add_item(importance_button)
    view.add_item(warnings_button)
    view.add_item(add_importance_instruction_button)
    await interaction.response.send_message(view=view)

@bot.tree.command(name="add_contribs", description="Tag a member's contribution with a pair area and importance level")
@app_commands.describe(member="The member to tag", area="The area of the contribution", importance="The importance level of the contribution", number="The number to adjust the importance by (default: +1)", reason="The reason for the adjustment (default: N/A)")
@app_commands.choices(area=[
    app_commands.Choice(name='Art', value='Art'),
    app_commands.Choice(name='Community Management', value='Community Management'),
    app_commands.Choice(name='Game Design', value='Game Design'),
    app_commands.Choice(name='Marketing and Public Relations', value='Marketing and Public Relations'),
    app_commands.Choice(name='Narrative and Writing', value='Narrative and Writing'),
    app_commands.Choice(name='Programming', value='Programming'),
    app_commands.Choice(name='Project Management', value='Project Management'),
    app_commands.Choice(name='Quality Assurance', value='Quality Assurance'),
    app_commands.Choice(name='Sound and Music', value='Sound and Music'),
    app_commands.Choice(name='Technical Art', value='Technical Art'),
    app_commands.Choice(name='UI/UX Design', value='UI/UX Design')
])
@app_commands.choices(importance=[
    app_commands.Choice(name='5️⃣ critical', value='5️⃣ critical'),
    app_commands.Choice(name='4️⃣ significant', value='4️⃣ significant'),
    app_commands.Choice(name='3️⃣ notable', value='3️⃣ notable'),
    app_commands.Choice(name='2️⃣ moderate', value='2️⃣ moderate'),
    app_commands.Choice(name='1️⃣ minor', value='1️⃣ minor')
])
async def add_contribs(interaction: discord.Interaction, member: discord.Member, area: app_commands.Choice[str], importance: app_commands.Choice[str], number: int = 1, reason: str = "N/A"):
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
    url = "N/A"

    await DGB.update_contribution(bot, member.id, issuer, [area.value, importance.value], now, number, reason=reason)

    author_name = DGB.id_to_name(member.id)

    if author_name:
        number_with_sign = f"+{number}" if number > 0 else str(number)
        await interaction.response.defer(ephemeral=False)
        await interaction.followup.send(f"`{importance.name}` `{number_with_sign}` to {member.mention}'s contribution in `{area.name}`, URL: `{url}`, Reason: `{reason}`")
        if importance.value == '4️⃣ significant' or importance.value == '5️⃣ critical':
            async with file_access_lock:
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

                        await interaction.followup.send(f"📝 **Formal Warning Adjustment** 📝\n\n<@{member.id}>, ????")
                    
                qualifies_for_core_member, _, _ = check_core_member_qualification(author_name)

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
    if not synced:
        raise RuntimeError("No commands were synced.")
    print(f'Synced {len(synced)} command (s)') # Restart your discord to see the changes
    bot.loop.create_task(background_task())
    bot.loop.create_task(periodic_open_pr_issue_check())

async def background_task():
    await bot.wait_until_ready()
    while not bot.is_closed():
        await check_direct_commits_to_main()
        # if datetime.now() - last_reset_time >= REPORT_INTERVAL:
            # await send_report(CURRENT_STYLE)
        await asyncio.sleep(1)

def is_admin(interaction: discord.Interaction) -> bool:
    if interaction.guild:
        member = interaction.guild.get_member(interaction.user.id)
        return member.guild_permissions.administrator
    else:
        return False


def name_to_id(author):
    for idx, name in enumerate(AUTHORS_LIST):
        if name == author:
            return DISCORD_USER_IDS_LIST[idx]
    return None

async def check_direct_commits_to_main():
    repo_name = REPO_NAME
    main_branch = MAIN_BRANCH
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }

    prs_url = f"https://api.github.com/repos/{repo_name}/pulls?state=closed&base={main_branch}"

    merged_pr_commits = set()

    async with aiohttp.ClientSession() as session:
        async with session.get(prs_url, headers=headers) as prs_response:
            if prs_response.status == 200:
                merged_prs = await prs_response.json()
                for pr in merged_prs:
                    if pr['merged_at']:  # Check if the PR was merged
                        commits_url = pr['commits_url']
                        async with session.get(commits_url, headers=headers) as commits_response:
                            if commits_response.status == 200:
                                pr_commits = await commits_response.json()
                                for pr_commit in pr_commits:
                                    merged_pr_commits.add(pr_commit['sha'])

        commits_url = f"https://api.github.com/repos/{repo_name}/commits?sha={main_branch}"
        async with session.get(commits_url, headers=headers) as commits_response:
            print(f"Fetching commits status: {commits_response.status}")
            if commits_response.status == 200:
                print("Connected to GitHub.")
                commits = await commits_response.json()
                for commit in commits:
                    commit_sha = commit['sha']
                    if commit_sha in merged_pr_commits:
                        print(f"Commit {commit_sha} was brought in through a merged PR.")
                        break  # Stop the loop once the first merged PR commit is found
                    else:
                        if len(commit['parents']) > 1:
                            print(f"Merge commit {commit_sha} was identified as a result of merging into {main_branch}.")
                        else:
                            print(f"❗️❗️❗️ Commit {commit_sha} was made directly to {main_branch}.")
                            commit_url = f"https://github.com/{repo_name}/commit/{commit_sha}"
                            await DGB.notify_member(bot, name_to_id(CORE_MEMBERS_LIST[0]), f"❗️❗️❗️\n\nHello, <@{name_to_id(CORE_MEMBERS_LIST[0])}>, direct commit to main detected, please resolve it immediately\n\nCommit SHA: `{commit_sha}`\n\nURL: {commit_url}")

    await asyncio.sleep(3600)

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
                    if (record_type == "Pull Request"):
                        if data["pull_request"]["merged_at"] is not None:
                            if DGB.meaningful_labels_verification(labels):
                                if (await DGB.check_pr_latest_importance_labeling_action(url)):
                                    async with file_access_lock:

                                        try:
                                            with open(CURRENT_OPEN_PR_ISSUE_FILE, 'r') as file:
                                                records = json.load(file)
                                        except FileNotFoundError:
                                            print("Current_open_pr_issue file not found.")
                                            return False
                                        record = next((record for record in records if str(record.get('id')) == pr_or_issue_id), None)

                                        if not (await process_pr_issue_record(record, session)):
                                            await DGB.update_pr_issue(url, state="open", comment="This issue has been reopened due to non-notification update. Please wait until the notification is sent.")
                                        else:
                                            remove_record_from_current_open_pr_issue_file(pr_or_issue_id)
                                            await DGB.notify_member(bot, name_to_id(author_name), f"📝📝📝\n\nHello, <@{name_to_id(author_name)}>, your PR has been merged. Thank you for your contribution!\n\nURL: {url}")
                                            print("PR archived.")
                                else:
                                    await DGB.update_pr_issue(url, comment="This PR/issue should be reinspected due to invalid `Importance` labeler.\n\nOnly **Reviewers** are allowed to label the `Importance`.") # state="open"
                                    print("This PR/issue should be reinspected due to invalid `Importance` labeler. Only **Reviewers** are allowed to label the `Importance`.")
                                    await DGB.undo_invalid_pr_importance_labeling_action(session, url, labels)
                                    remove_record_from_current_open_pr_issue_file(pr_or_issue_id)
                                    print("Undone invalid `Importance` labeling actions.")
                            elif len(labels) == 0:
                                remove_record_from_current_open_pr_issue_file(pr_or_issue_id)
                                print("Meaningless PR without any labels.")
                            else:
                                remove_record_from_current_open_pr_issue_file(pr_or_issue_id)
                                await DGB.update_pr_issue(url, state="open", comment="This PR has been reopened due to invalid labeling.\n\nOnly `0` label (for meaningless PR/issue) and `2` labels (`1` `Importance` and `1` `Area` for meaningful PR/issue) are allowed.")
                                print("Labels do not meet the conditions.")
                        elif len(labels) == 0:
                                remove_record_from_current_open_pr_issue_file(pr_or_issue_id)
                                print("Meaningless PR without any labels.")
                        else:
                            remove_record_from_current_open_pr_issue_file(pr_or_issue_id)
                            await DGB.update_pr_issue(url, state="open", comment="This PR has been reopened due to invalid labeling.\n\nOnly `0` label (for meaningless PR/issue) and `2` labels (`1` `Importance` and `1` `Area` for meaningful PR/issue) are allowed.")
                            print("Labels do not meet the conditions.")
                    elif (record_type == "Issue"):
                        if DGB.meaningful_labels_verification(labels):
                            if (await DGB.check_issue_latest_importance_labeling_action(url)):

                                async with file_access_lock:

                                    try:
                                        with open(CURRENT_OPEN_PR_ISSUE_FILE, 'r') as file:
                                            records = json.load(file)
                                    except FileNotFoundError:
                                        print("Current_open_pr_issue file not found.")
                                        return False
                                    record = next((record for record in records if str(record.get('id')) == pr_or_issue_id), None)

                                    if not (await process_pr_issue_record(record, session)):
                                        await DGB.update_pr_issue(url, state="open", comment="This issue has been reopened due to non-notification update. Please wait until the notification is sent.")
                                    else:
                                        remove_record_from_current_open_pr_issue_file(pr_or_issue_id)
                                        await DGB.notify_member(bot, name_to_id(author_name), f"📝📝📝\n\nHello, <@{name_to_id(author_name)}>, your issue has been archived. Thank you for your contribution!\n\nURL: {url}")
                                        print("Issue archived.")
                            else:
                                await DGB.update_pr_issue(url, state="open", comment="This issue has been reopened due to invalid `Importance` labeler.\n\nOnly **Core Members** are allowed to label the `Importance`.")
                                print("This issue has been reopened due to invalid `Importance` labeler. Only **Core Members** are allowed to label the `Importance`.")
                                await DGB.undo_invalid_issue_importance_labeling_action(session, url, labels)
                                print("Undone invalid `Importance` labeling actions.")
                        elif len(labels) == 0:
                            remove_record_from_current_open_pr_issue_file(pr_or_issue_id)
                            print("Meaningless issue without any labels.")
                        else:
                            remove_record_from_current_open_pr_issue_file(pr_or_issue_id)
                            await DGB.update_pr_issue(url, state="open", comment="This issue has been reopened due to invalid labeling.\n\nOnly `0` label (for meaningless PR/issue) and `2` labels (`1` `Importance` and `1` `Area` for meaningful PR/issue) are allowed.")
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

def check_core_member_qualification(author_name):
    try:
        with open(CONTRIBUTIONS_HISTORY_FILE, 'r') as file:
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

async def calculate_and_display_contributions(channel, interaction=None):
    area_imp_counts = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))

    try:
        with open(CONTRIBUTIONS_HISTORY_FILE, 'r') as file:
            lines = iter(file)
            first_line = next(lines, None)
            if first_line:
                first_record = json.loads(first_line.strip())
                start_time_str = first_record['issued_time']

                author = first_record['author']
                area = first_record['area']
                importance = first_record['importance']
                count = int(first_record['count'])

                if author in AUTHORS_LIST:
                    area_imp_counts[author][area][importance] += count

            for line in lines:
                try:
                    record = json.loads(line.strip())
                    author = record['author']
                    area = record['area']
                    importance = record['importance']
                    count = int(record['count'])

                    if author in AUTHORS_LIST:
                        area_imp_counts[author][area][importance] += count
                except json.JSONDecodeError:
                    continue
    except FileNotFoundError:
        print("Contribution history data file not found.")

    if start_time_str is None:
        await channel.send("Contribution history file is empty or not properly formatted.")
        return

    end_time_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    embed_description = generate_embed_description_for_importance(CURRENT_STYLE, area_imp_counts)
    embed = discord.Embed(title=f"Contributions Report\n\n`{start_time_str}` to `{end_time_str}`", description=embed_description, color=0x4895EF)
    toggle_button = Button(label="Toggle Output Style", style=discord.ButtonStyle.green, custom_id="toggle_importance_style")

    view = View()
    view.add_item(toggle_button)

    if interaction:
        await interaction.edit_original_response(embed=embed, view=view)
    else:
        await channel.send(embed=embed, view=view)

def generate_embed_description_for_importance(style, area_imp_counts):
    embed_description = ""
    
    if style:
        for author_id, discord_id in zip(AUTHORS_LIST, DISCORD_USER_IDS_LIST):
            embed_description += f"\n\n<@{discord_id}>\n"
            
            for area in AREAS_LIST:
                area_abbreviation = ''.join(filter(str.isupper, area))
                area_description = f"\n{area_abbreviation}:\n"
                has_contributions = False
                
                for importance in IMPORTANCES_LIST:
                    first_word_of_importance = importance.split()[0] if importance else ""
                    count = area_imp_counts.get(author_id, {}).get(area, {}).get(importance, 0)
                    if count > 0:
                        area_description += f"> {first_word_of_importance}: `{count}`\n"
                        has_contributions = True
                
                if has_contributions:
                    embed_description += area_description

    else:
        embed_description += "```"
        embed_description += "\n"
        for author_index, (author_id, discord_id) in enumerate(zip(AUTHORS_LIST, DISCORD_USER_IDS_LIST)):
            author_description = f"{author_id}\n\n"
            has_area_contributions = False
            
            for area in AREAS_LIST:
                area_abbreviation = ''.join(filter(str.isupper, area))
                area_description = f"{area_abbreviation}:\n"
                area_has_contributions = False
                
                for importance in IMPORTANCES_LIST:
                    first_word_of_importance = importance.split()[0] if importance else ""
                    count = area_imp_counts.get(author_id, {}).get(area, {}).get(importance, 0)
                    if count > 0:
                        area_description += f" {first_word_of_importance}: {count}\n"
                        area_has_contributions = True
                        has_area_contributions = True

                if area_has_contributions:
                    author_description += f"{area_description}\n"
            
            if has_area_contributions:
                embed_description += f"{author_description}"
            else:
                embed_description += f"{author_id}\n"
            
            if author_index < len(AUTHORS_LIST) - 1:
                embed_description += "\n"
                
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
                    file.truncate(0)
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
        expulsion_message += f"{warning_members_ID if CURRENT_STYLE else warning_members} should be expelled due to accumulating `{MAX_FORMAL_WARNINGS + 1}` or more **formal warnings**, in accordance with ???? \n"
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
        embed_description += f"{warning_members_ID if style else warning_members} **received** `1` **formal warning** due to ???"

    return (embed_description, authors_with_warnings) if include_warnings else embed_description
    
''' 

need to be updated

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

    last_reset_time = current_time
    print(f"Periodic Contributions Report sent: `{start_time_str}` to `{current_time_str}`")

'''
    

async def periodic_open_pr_issue_check():
    i = 0
    while True:
        print(f"Periodic open PR/issue check iteration: {i}")
        async with file_access_lock:
            try:
                with open(CURRENT_OPEN_PR_ISSUE_FILE, 'r') as file:
                    records = json.load(file)
            except FileNotFoundError:
                print("Current open PR/Issue records file not found.")
                records = []

            async with aiohttp.ClientSession() as session:
                await process_pr_issue_records(records, session)

        await asyncio.sleep(120)  # Wait for 120 seconds before next iteration, note: 5,000 requests limit per hour for github personal api token
        i += 1

async def process_pr_issue_records(records, session):
    for record in records:
        await process_pr_issue_record(record, session)
    with open(CURRENT_OPEN_PR_ISSUE_FILE, 'w') as file:
        json.dump(records, file, indent=4)

async def process_pr_issue_record(record, session):

    url = record.get('url')

    has_updated_contribution = False

    api_url = DGB.url_to_api_url(url)
    async with session.get(api_url, headers={
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }) as response:
        if response.status == 200:
            data = await response.json()
            labels = [label['name'] for label in data.get("labels", [])]
            if len(labels) == 0:
                if (not record['reviewers']):
                    await DGB.update_pr_issue(url, labels=['❔ pending'], comment="Revert meaningless label to `❔ pending` due to no reviewer assigned.")
                else:
                    if record['last_valid_labels']:
                        record['current_labels'] = labels
                        await DGB.update_pr_issue(url, comment=f"This PR/issue has been labeled as `meaningless`.")
                        await DGB.update_contribution(bot, name_to_id(record['author']), record['reviewers'], record['last_valid_labels'], datetime.now().strftime('%Y-%m-%d %H:%M:%S'), number=-1, url=url, reason="Contributions have been labeled as meaningless, contributions updated.")
                        record['last_valid_labels'] = []
                        has_updated_contribution = True
            elif labels == ['❔ pending']:
                if (not record['valid_area_labeled_by_author_time']):
                    # print("Sending area label notification.")
                    await DGB.update_pr_issue(url, comment="Please add 1 appropriate `Area` label for this PR/issue.")
                    await DGB.notify_member(bot, name_to_id(record['author']), f"📝📝📝\n\nHello, <@{name_to_id(record['author'])}>, please add 1 appropriate `Area` label for your PR/issue.\n\nURL: {url}")
                    record['current_labels'] = labels
                    record['valid_area_labeled_by_author_time'] = 'Notified'
                else:
                    record['current_labels'] = labels
                    # print("Area label notification already sent.")
            elif DGB.area_label_verification(labels):
                record['valid_importance_labeled_by_reviewers_time'] = ''
                # print("Valid area label found. Awaiting `Importance` label. (Reset `valid_importance_labeled_by_reviewers_time`.)")
                if (not record['valid_area_labeled_by_author_time'] or record['valid_area_labeled_by_author_time'] == 'Notified'):
                    record['valid_area_labeled_by_author_time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    record['current_labels'] = labels
                if (not record['reviewers']):
                    current_reviewers = [CORE_MEMBERS_LIST[0]]
                    current_reviewers_str = ', @'.join(current_reviewers)
                    record['current_labels'] = labels
                    record['reviewers'] = current_reviewers
                    await DGB.update_pr_issue(url, reviewers=current_reviewers, comment=f"Reviewer @{current_reviewers_str} is assigned to this PR/issue. Awaiting `Importance` label for this PR/issue.")
                    await DGB.notify_member(bot, name_to_id(current_reviewers[0]), f"📝📝📝\n\nHello, <@{name_to_id(current_reviewers[0])}>, you've been assigned to this PR/issue. Awaiting `Importance` label for this PR/issue.\n\nURL: {url}")
                elif DGB.check_review_deadline_exceeded(record):
                    if len(labels) == 2:
                        print("Adding the label `⏰ review deadline exceeded`.")
                        new_labels = labels + ['⏰ review deadline exceeded']
                        previous_reviewers = record['reviewers']
                        previous_reviewers_str = ', @'.join(previous_reviewers)
                        # ????????????????????? notify previous reviewers
                        new_reviewers = [CORE_MEMBERS_LIST[0]] # ?????
                        new_reviewers_str = ', @'.join(new_reviewers)
                        await DGB.update_pr_issue(url, labels=new_labels, reviewers=new_reviewers, comment=f"The review deadline for this PR/issue has been exceeded. New reviewer @{new_reviewers_str} is assigned to this PR/issue.\n(Previous reviewers were: @{previous_reviewers_str})")
                        # ????????????????????? send the public notification
                        record['current_labels'] = new_labels
                        record['reviewers'] = new_reviewers
                        record['previous_reviewers'] = previous_reviewers
                        record['review_ddl_time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    else:
                        record['current_labels'] = labels
                        # print("Label `⏰ review deadline exceeded` has already been added.")
            elif DGB.meaningful_labels_verification(labels) and record['valid_area_labeled_by_author_time']:
                if DGB.check_review_deadline_exceeded(record):
                    if len(labels) == 2:
                        new_labels = labels + ['⏰ review deadline exceeded']
                        await DGB.update_pr_issue(url, labels=new_labels)
                if (not record['reviewers']):
                    first_match = next((label for label in labels if label in AREAS_LIST), None)
                    review_deadline_exceeded_label = next((label for label in labels if label in ['⏰ review deadline exceeded']), None)
                    area_label = [first_match] if first_match is not None else []
                    area_label = (area_label + [review_deadline_exceeded_label]) if review_deadline_exceeded_label is not None else area_label
                    area_label_with_pending_label = area_label + ['❔ pending']
                    record['current_labels'] = area_label_with_pending_label
                    record['valid_importance_labeled_by_reviewers_time'] = ''
                    record['valid_area_labeled_by_author_time'] = ''
                    record['reviewers'] = []
                    await DGB.update_pr_issue(url, labels=area_label_with_pending_label, comment="This PR/issue has been relabeled as `❔ pending` due to invalid labeling.")
                elif (not record['valid_importance_labeled_by_reviewers_time']):
                    if record['type'] == 'Issue':
                        if (await DGB.check_issue_latest_importance_labeling_action(url)):
                            record['current_labels'] = labels
                            current_reviewers = record['reviewers']
                            current_reviewers_str = ', @'.join(current_reviewers)
                            record['reviewers'] = current_reviewers
                            record['valid_importance_labeled_by_reviewers_time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                            await DGB.update_pr_issue(url, comment=f"Reviewer @{current_reviewers_str} has added the `Importance` label to this PR/issue.")
                            if not record['last_valid_labels']:
                                await DGB.update_contribution(bot, name_to_id(record['author']), record['reviewers'], labels, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), number=1, url=url, reason="Contributions (Issue) recorded.")
                                record['last_valid_labels'] = labels
                            elif record['last_valid_labels'] != record['current_labels']:
                                await DGB.update_contribution(bot, name_to_id(record['author']), record['reviewers'], record['last_valid_labels'], datetime.now().strftime('%Y-%m-%d %H:%M:%S'), number=-1, url=url, reason="Updating contributions with latest labels.")
                                await DGB.update_contribution(bot, name_to_id(record['author']), record['reviewers'], labels, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), number=1, url=url, reason="Update finished.")
                                record['last_valid_labels'] = labels

                            has_updated_contribution = True

                        else:
                            await DGB.undo_invalid_issue_importance_labeling_action(session, url, labels)
                    else: # PR
                        if (await DGB.check_pr_latest_importance_labeling_action(url)):
                            record['current_labels'] = labels
                            current_reviewers = record['reviewers']
                            current_reviewers_str = ', @'.join(current_reviewers)
                            record['reviewers'] = current_reviewers
                            record['valid_importance_labeled_by_reviewers_time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                            await DGB.update_pr_issue(url, comment=f"Reviewer @{current_reviewers_str} has added the `Importance` label to this PR/issue.")
                            if not record['last_valid_labels']:
                                await DGB.update_contribution(bot, name_to_id(record['author']), record['reviewers'], labels, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), number=1, url=url, reason="Contributions (PR) recorded.")
                                record['last_valid_labels'] = labels
                            elif record['last_valid_labels'] != record['current_labels']:
                                await DGB.update_contribution(bot, name_to_id(record['author']), record['reviewers'], record['last_valid_labels'], datetime.now().strftime('%Y-%m-%d %H:%M:%S'), number=-1, url=url, reason="Updating contributions with latest labels.")
                                await DGB.update_contribution(bot, name_to_id(record['author']), record['reviewers'], labels, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), number=1, url=url, reason="Update finished.")
                                record['last_valid_labels'] = labels
                            
                            has_updated_contribution = True

                        else:
                            await DGB.undo_invalid_pr_importance_labeling_action(session, url, labels)
                else:
                    record['current_labels'] = labels
                    if record['last_valid_labels'] != record['current_labels']:
                        if record['type'] == 'Issue':
                            if (await DGB.check_issue_latest_importance_labeling_action(url)):
                                if not record['last_valid_labels']:
                                    await DGB.update_contribution(bot, name_to_id(record['author']), record['reviewers'], labels, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), number=1, url=url, reason="Contributions (Issue) recorded.")
                                    record['last_valid_labels'] = labels
                                elif record['last_valid_labels'] != record['current_labels']:
                                    await DGB.update_contribution(bot, name_to_id(record['author']), record['reviewers'], record['last_valid_labels'], datetime.now().strftime('%Y-%m-%d %H:%M:%S'), number=-1, url=url, reason="Updating contributions with latest labels.")
                                    await DGB.update_contribution(bot, name_to_id(record['author']), record['reviewers'], labels, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), number=1, url=url, reason="Update finished.")
                                    record['last_valid_labels'] = labels

                                has_updated_contribution = True
                            else:
                                await DGB.undo_invalid_issue_importance_labeling_action(session, url, labels)
                                record['last_valid_labels'] = labels
                        else: # PR
                            if (await DGB.check_pr_latest_importance_labeling_action(url)):
                                if not record['last_valid_labels']:
                                    await DGB.update_contribution(bot, name_to_id(record['author']), record['reviewers'], labels, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), number=1, url=url, reason="Contributions (PR) recorded.")
                                    record['last_valid_labels'] = labels
                                elif record['last_valid_labels'] != record['current_labels']:
                                    await DGB.update_contribution(bot, name_to_id(record['author']), record['reviewers'], record['last_valid_labels'], datetime.now().strftime('%Y-%m-%d %H:%M:%S'), number=-1, url=url, reason="Updating contributions with latest labels.")
                                    await DGB.update_contribution(bot, name_to_id(record['author']), record['reviewers'], labels, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), number=1, url=url, reason="Update finished.")
                                    record['last_valid_labels'] = labels
                                
                                has_updated_contribution = True
                            else:
                                await DGB.undo_invalid_pr_importance_labeling_action(session, url, labels)
                                record['last_valid_labels'] = labels
                    else:
                        has_updated_contribution = True
            else:
                first_match = next((label for label in labels if label in AREAS_LIST), None)
                review_deadline_exceeded_label = next((label for label in labels if label in ['⏰ review deadline exceeded']), None)
                area_label = [first_match] if first_match is not None else []
                area_label = (area_label + [review_deadline_exceeded_label]) if review_deadline_exceeded_label is not None else area_label
                area_label_with_pending_label = area_label + ['❔ pending']
                record['current_labels'] = area_label_with_pending_label
                record['valid_importance_labeled_by_reviewers_time'] = ''
                record['valid_area_labeled_by_author_time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                record['reviewers'] = []
                await DGB.update_pr_issue(url, labels=area_label_with_pending_label, comment="This PR/issue has been relabeled as `❔ pending` due to invalid labeling.")
    
    return has_updated_contribution

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
                    'last_valid_labels': [],
                    'current_labels': []
                }

                async with file_access_lock:

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

                    async with aiohttp.ClientSession() as session:
                        current_area_label = await DGB.fetch_current_area_label(session, embed.url)
                    current_area_label = current_area_label + ['❔ pending']
                    await DGB.update_pr_issue(embed.url, current_area_label, reviewers=[]) 
                
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

@bot.event
async def on_interaction(interaction):
    global CURRENT_STYLE
    if interaction.type == discord.InteractionType.component:
        if interaction.data.get('custom_id') == "add_importance_instruction":
            instruction_message = "To assign a contribution to a member, use the command `/add_contribs`. "
            instruction_message += "You'll need to specify the member, the area, the importance level of their contribution, and the number of contributions at that level.\n\n"
            instruction_message += "Example 1: `/add_contribs member:@User area:Art importance:5️⃣ critical number:1`.\n\n"
            instruction_message += "Example 2: `/add_contribs member:@User area:Programming importance:3️⃣ notable number:-2`.\n\n"
            instruction_message += "**Important Restrictions**:\n"
            instruction_message += "- **Server Limitation**: This command is exclusive to the **CruxAbyss** server.\n"
            instruction_message += "- **Permission Requirement**: Only **admin** roles are authorized to use this command."
            await interaction.response.send_message(instruction_message, ephemeral=True)
        elif interaction.data.get('custom_id') == "toggle_importance_style":
            await interaction.response.defer()
            CURRENT_STYLE = not CURRENT_STYLE
            await calculate_and_display_contributions(interaction.channel, interaction=interaction)
        elif interaction.data.get('custom_id') == "display_contributions":
            await interaction.response.defer()
            await calculate_and_display_contributions(interaction.channel, interaction=None)
        elif interaction.data.get('custom_id') == "display_total_formal_warnings":
            await interaction.response.defer()
            await total_formal_warnings_report(interaction.channel, interaction=None)
            return
        elif interaction.data.get('custom_id') == "toggle_formal_warnings_style":
            await interaction.response.defer()
            CURRENT_STYLE = not CURRENT_STYLE
            await total_formal_warnings_report(interaction.channel, interaction=interaction)
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
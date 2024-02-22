# Predefined variables for configuration


from datetime import timedelta


# ID of the Discord channel to send periodic reports to
CHANNEL_ID = 

# ID of the Discord server
SERVER_ID = 

# Token for the Discord bot
BOT_TOKEN = ''

# Token for the GitHub API
GITHUB_TOKEN = ''

# Doc URL for the GitHub API
DOC_URL = ""

# List of predefined authors to track
AUTHORS_LIST = ["",]

# List of corresponding Discord userID
DISCORD_USER_IDS_LIST = ["",]

# List of predefined core members
CORE_MEMBERS_LIST = ["",] 

# Areas for contributions
AREAS_LIST = ["Art", "Community Management", "Marketing and Public Relations", "Narrative and Writing", "Programming", "Project Management", "Quality Assurance", "Sound and Music", "Technical Art", "UI/UX Design"]

# Importance levels for contributions
IMPORTANCES_LIST = ['5️⃣ critical', '4️⃣ significant', '3️⃣ notable', '2️⃣ moderate', '1️⃣ minor']

# Current style for report formatting; False for table-like, True for alternate style
CURRENT_STYLE = False 

# Time interval for periodic reports (weeks=? or days=? or hours=? or minutes=? or seconds=?)
REPORT_INTERVAL = timedelta(days=1)

# Deadline for reviewing PRs
REVIEW_DEADLINE = timedelta(days=4)

# Minimum number of contributions to be considered for periodic reports
MIN_PERIODIC_CONTRIBUTIONS = 1

# Maximum number of formal warnings before being expelled
MAX_FORMAL_WARNINGS = 1

# Core member role name
CORE_MEMBER_ROLE_NAME = "Core Member"

# Periodic contributions history file path
PERIODIC_CONTRIBUTIONS_HISTORY_FILE = 'periodic_contributions_history.json'

# Total contributions file path
TOTAL_CONTRIBUTIONS_FILE = 'total_contributions.json'

# Formal warnings file path
FORMAL_WARNINGS_FILE = 'formal_warnings.json'

# Contribution importance file path
CONTRIBUTION_IMPORTANCE_FILE = 'contribution_importance.json'

# Temporary PR issue records file path
CURRENT_OPEN_PR_ISSUE_FILE = 'current_open_pr_issue.json'
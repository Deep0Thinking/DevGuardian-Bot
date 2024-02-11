# Predefined variables for configuration


from datetime import timedelta


# ID of the Discord channel to send reports to
CHANNEL_ID = 

# Token for the Discord bot
BOT_TOKEN = ''

# List of predefined authors to track
AUTHORS_LIST = ["",]

# List of corresponding Discord userID
DISCORD_USER_IDS_LIST = ["",]

# Current style for report formatting; False for table-like, True for alternate style
CURRENT_STYLE = False 

# Time interval for periodic reports (weeks=? or days=? or hours=? or minutes=? or seconds=?)
REPORT_INTERVAL = timedelta(seconds=10)

# Minimum number of contributions to be considered for periodic reports
MIN_PERIODIC_CONTRIBUTIONS = 

# Maximum number of formal warnings before being expelled
MAX_FORMAL_WARNINGS = 

# Periodic contributions history file path
PERIODIC_CONTRIBUTIONS_HISTORY_FILE = 'periodic_contributions_history.json'

# Total contributions file path
TOTAL_CONTRIBUTIONS_FILE = 'total_contributions.json'

# Formal warnings file path
FORMAL_WARNINGS_FILE = 'formal_warnings.json'

# Contribution importance file path
CONTRIBUTION_IMPORTANCE_FILE = 'contribution_importance.json'

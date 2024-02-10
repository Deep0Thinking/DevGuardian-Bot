# Predefined variables for configuration


from datetime import timedelta

# ID of the Discord channel to send reports to
CHANNEL_ID = 

# Token for the Discord bot
BOT_TOKEN = ''

# List of predefined authors to track
authors_list = ["",]

# Current style for report formatting: False for table-like, True for alternate style
current_style = False 

# Time interval for periodic reports (weeks=? or days=? or hours=? or minutes=? or seconds=?)
report_interval = timedelta(seconds=10)

# Periodic contributions history file path
PERIODIC_CONTRIBUTIONS_HISTORY_FILE = 'periodic_contributions_history.json'

# Total contributions file path
TOTAL_CONTRIBUTIONS_FILE = 'total_contributions.json'

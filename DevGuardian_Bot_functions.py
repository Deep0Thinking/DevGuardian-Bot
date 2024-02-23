import re
import config
import aiohttp
from datetime import datetime
import json

IMPORTANCES_LIST = config.IMPORTANCES_LIST
AREAS_LIST = config.AREAS_LIST
GITHUB_TOKEN = config.GITHUB_TOKEN
CORE_MEMBERS_LIST = config.CORE_MEMBERS_LIST
AUTHORS_LIST = config.AUTHORS_LIST
REVIEW_DEADLINE = config.REVIEW_DEADLINE
CURRENT_OPEN_PR_ISSUE_FILE = config.CURRENT_OPEN_PR_ISSUE_FILE

def print_embed_message(embed):
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

def url_to_api_url(url):

    # This function's output (api_url) should only be used for fetching the basic raw response from GitHub API
    # Any further PR/issue update request or specific info retrieval should directly use pr_api_url or issue_api_url specifically
    # The reason is at (*) below

    url_match = re.search(r'https://github\.com/([^/]+)/([^/]+)/(pull|issues)/(\d+)', url)
    if url_match:
        org, repo, _, record_id = url_match.groups()

        # (*) Reason for using `issues` within the output here: https://stackoverflow.com/questions/68459601/can-we-add-labels-to-a-pull-request-while-creation-using-rest-api
        return f"https://api.github.com/repos/{org}/{repo}/issues/{record_id}"
    else:
        return None
    
def area_label_verification(labels):
    label_conditions_1 = [
        any(label in labels for label in ['❔ pending']),
        any(label in labels for label in AREAS_LIST)
    ]
    label_conditions_2 = [
        any(label in labels for label in ['❔ pending']),
        any(label in labels for label in AREAS_LIST),
        any(label in labels for label in ['⏰ review deadline exceeded'])
    ]
    return (len(labels) == 2 and all(label_conditions_1)) or (len(labels) == 3 and all(label_conditions_2))
    
def meaningful_labels_verification(labels):
    label_conditions_1 = [
        any(label in labels for label in IMPORTANCES_LIST),
        any(label in labels for label in AREAS_LIST)
    ]
    label_conditions_2 = [
        any(label in labels for label in IMPORTANCES_LIST),
        any(label in labels for label in AREAS_LIST),
        any(label in labels for label in ['⏰ review deadline exceeded'])
    ]
    return (len(labels) == 2 and all(label_conditions_1)) or (len(labels) == 3 and all(label_conditions_2))

def review_ddl_exceeded_label_verification(labels):
    label_conditions = [
        any(label in labels for label in IMPORTANCES_LIST),
        any(label in labels for label in AREAS_LIST),
        any(label in labels for label in ['⏰ review deadline exceeded'])
    ]
    return len(labels) == 3 and all(label_conditions)

def check_review_deadline_exceeded(pr_issue_data):
    valid_area_labeled_by_author_time_str = pr_issue_data['valid_area_labeled_by_author_time']
    if valid_area_labeled_by_author_time_str == 'Notified':
        return False
    valid_area_labeled_by_author_time = datetime.strptime(valid_area_labeled_by_author_time_str, '%Y-%m-%d %H:%M:%S')
    deadline = valid_area_labeled_by_author_time + REVIEW_DEADLINE
    current_time = datetime.now()
    return current_time > deadline

async def fetch_pr_reviewers(session, url):

    parts = url.split('/')
    owner_repo = f"{parts[3]}/{parts[4]}"
    pr_or_issue_id = parts[6]
    api_base_url = f"https://api.github.com/repos/{owner_repo}"
    pr_api_url = f"{api_base_url}/pulls/{pr_or_issue_id}"

    if "pull" in url:
        reviewers_api_url = f"{pr_api_url}/requested_reviewers"

        headers = {
            "Authorization": f"token {GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3+json"
        }
        async with session.get(reviewers_api_url, headers=headers) as response:
            if response.status == 200:
                data = await response.json()
                reviewers = {user['login'] for user in data.get('users', [])}
                return reviewers
            else:
                print("Failed to fetch reviewers.")
                return {}
    else:
        print("It's not a PR. No reviewers to fetch.")
        return {}
    
async def fetch_pr_importance_labeling_action(session, url):
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    async with session.get(f"{url_to_api_url(url)}/events", headers=headers) as response:
        if response.status == 200:
            data = await response.json()
            importance_labelers = []
            importance_labels = []
            importance_action = []

            for event in data:
                if (event["event"] == "labeled" or event["event"] == "unlabeled")  and event["label"]["name"] in IMPORTANCES_LIST:
                    importance_labelers.append(event["actor"]["login"])
                    importance_labels.append(event["label"]["name"])
                    importance_action.append(event["event"])
            
            if importance_labelers != None and importance_labels != None:
                return importance_labelers, importance_labels, importance_action
            else:
                print("No `Importance` labeler and label found.")
                return None
            
        else:
            print("Failed to fetch PR events.")
            return None

async def undo_invalid_pr_importance_labeling_action(session, url, labels):
    pr_importance_labelers, pr_importance_labels, pr_importance_action = await fetch_pr_importance_labeling_action(session, url)
    pr_importance_labelers.reverse()
    pr_importance_labels.reverse()
    pr_importance_action.reverse()

    try:
        with open(CURRENT_OPEN_PR_ISSUE_FILE, 'r+') as file:
            records = json.load(file)
    except FileNotFoundError:
        print("Current_open_pr_issue file not found.")

    parts = url.split('/')
    pr_or_issue_id = parts[6]

    matched_record = next((record for record in records if str(record.get('id')) == pr_or_issue_id), None)

    for i in range(len(pr_importance_labelers)):
        if (pr_importance_labelers[i] not in matched_record['reviewers']) and (pr_importance_labels[i] not in IMPORTANCES_LIST):
            print("Undoing the invalid `Importance` labeling action.")
            if pr_importance_action[i] == "labeled":
                labels = [label for label in labels if label != pr_importance_labels[i]]
                await update_pr_issue(url, labels=labels)
            else:
                labels = labels + [pr_importance_labels[i]]
                await update_pr_issue(url, labels=labels)
        else:
            print(f"{pr_importance_labelers[i]} is the reviewer of the PR. No action needed.")
            break

async def undo_invalid_issue_importance_labeling_action(session, url, labels):
    pr_importance_labelers, pr_importance_labels, pr_importance_action = await fetch_pr_importance_labeling_action(session, url)
    pr_importance_labelers.reverse()
    pr_importance_labels.reverse()
    pr_importance_action.reverse()

    for i in range(len(pr_importance_labelers)):
        if (pr_importance_labelers[i] not in CORE_MEMBERS_LIST) and (pr_importance_labels[i] in IMPORTANCES_LIST):
            print("Undoing the invalid `Importance` labeling action.")
            if pr_importance_action[i] == "labeled":
                labels = [label for label in labels if label != pr_importance_labels[i]]
                await update_pr_issue(url, labels=labels)
            else:
                labels = labels + [pr_importance_labels[i]]
                await update_pr_issue(url, labels=labels)
        else:
            print(f"{pr_importance_labelers[i]} is the reviewer of the PR. No action needed.")
            break

async def fetch_current_area_label(session, url):
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3.raw"
    }
    async with aiohttp.ClientSession() as session:
        async with session.get(url_to_api_url(url), headers=headers) as response:
            if response.status == 200:
                data = await response.json()
                first_label_in_area = next((label['name'] for label in data.get("labels", []) if label['name'] in AREAS_LIST), None)
                if first_label_in_area:  
                    area_label = [first_label_in_area]
                else:
                    area_label = []
                return area_label
    
async def fetch_latest_importance_labeler(session, url):
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    async with session.get(f"{url_to_api_url(url)}/events", headers=headers) as response:
        if response.status == 200:
            data = await response.json()
            latest_importance_labeler = None

            for event in data:
                if event["event"] == "labeled" and event["label"]["name"] in IMPORTANCES_LIST:
                    latest_importance_labeler = event["actor"]["login"]
            
            if latest_importance_labeler != None:
                return latest_importance_labeler
            else:
                print("No `Importance` label found.")
                return None
            
        else:
            print("Failed to fetch PR events.")
            return None

async def check_pr_latest_importance_labeling_action(url):
    async with aiohttp.ClientSession() as session:
        reviewers = await fetch_pr_reviewers(session, url)
        latest_importance_labeler = await fetch_latest_importance_labeler(session, url)
        if not latest_importance_labeler:
            print("No `Importance` label found.")
            return False

        return (latest_importance_labeler in reviewers)
    
async def check_issue_latest_importance_labeling_action(url):
    async with aiohttp.ClientSession() as session:
        latest_importance_labeler = await fetch_latest_importance_labeler(session, url)
        if not latest_importance_labeler:
            print("No `Importance` label found.")
            return False
        return (latest_importance_labeler in CORE_MEMBERS_LIST)

async def update_pr_issue(url, labels=None, state=None, comment=None, reviewers=None):
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    data = {}
    if labels is not None:
        data["labels"] = labels
    if state is not None:
        data["state"] = state

    parts = url.split('/')
    owner_repo = f"{parts[3]}/{parts[4]}"
    pr_or_issue_id = parts[6]
    api_base_url = f"https://api.github.com/repos/{owner_repo}"
    issue_api_url = f"{api_base_url}/issues/{pr_or_issue_id}"
    pr_api_url = f"{api_base_url}/pulls/{pr_or_issue_id}"

    if comment is not None:
        comment_url = f"{issue_api_url}/comments"
        async with aiohttp.ClientSession() as session:
            await session.post(comment_url, headers=headers, json={"body": comment})

    if data:
        async with aiohttp.ClientSession() as session:
            async with session.patch(issue_api_url, headers=headers, json=data) as response:
                if response.status == 200:
                    print(f"PR/issue #{pr_or_issue_id} updated successfully")
                else:
                    print(f"Failed to update PR/issue #{pr_or_issue_id}. Status code: {response.status}")
                    response_text = await response.text()
                    print(f"Response body: {response_text}")

    if reviewers and "pull" in url:
        reviewers_data = {"reviewers": reviewers}
        reviewers_url = f"{pr_api_url}/requested_reviewers"
        print(f"reviewers_data: {reviewers_data}")
        print(f"reviewers_url: {reviewers_url}")
        async with aiohttp.ClientSession() as session:
            async with session.post(reviewers_url, headers=headers, json=reviewers_data) as response:
                if response.status == 200:
                    print(f"Reviewers for PR #{pr_or_issue_id} set successfully")
                else:
                    print(f"Failed to set reviewers for PR #{pr_or_issue_id}. Status code: {response.status}")
                    response_text = await response.text()
                    print(f"Response body: {response_text}")

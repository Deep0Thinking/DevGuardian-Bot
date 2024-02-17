import re
import config
import aiohttp
from datetime import datetime, timedelta

IMPORTANCES_LIST = config.IMPORTANCES_LIST
AREAS_LIST = config.AREAS_LIST
GITHUB_TOKEN = config.GITHUB_TOKEN

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
        any(label in labels for label in ['🕒 deadline exceeded'])
    ]
    return (len(labels) == 2 and all(label_conditions_1)) or (len(labels) == 3 and all(label_conditions_2))
    
def labels_verification(labels):
    label_conditions_1 = [
        any(label in labels for label in IMPORTANCES_LIST),
        any(label in labels for label in AREAS_LIST)
    ]
    label_conditions_2 = [
        any(label in labels for label in IMPORTANCES_LIST),
        any(label in labels for label in AREAS_LIST),
        any(label in labels for label in ['🕒 deadline exceeded'])
    ]
    return (len(labels) == 2 and all(label_conditions_1)) or (len(labels) == 3 and all(label_conditions_2))

def review_ddl_exceeded_label_verification(labels):
    label_conditions = [
        any(label in labels for label in IMPORTANCES_LIST),
        any(label in labels for label in AREAS_LIST),
        any(label in labels for label in ['🕒 deadline exceeded'])
    ]
    return len(labels) == 3 and all(label_conditions)

def check_review_deadline_exceeded(pr_issue_data):
    valid_importance_labeled_by_reviewers_time_str = pr_issue_data.get('valid_importance_labeled_by_reviewers_time')
    valid_importance_labeled_by_reviewers_time = datetime.strptime(valid_importance_labeled_by_reviewers_time_str, '%Y-%m-%d %H:%M:%S')
    deadline = valid_importance_labeled_by_reviewers_time + timedelta(minutes=1)
    current_time = datetime.now()
    return current_time > deadline

async def check_latest_importance_labeling_action(url, reviewers=[]):
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{url_to_api_url(url)}/events", headers=headers) as response:
            if response.status == 200:
                data = await response.json()

                labeler = None

                for event in data:
                    if event["event"] == "labeled" and event["label"]["name"] in IMPORTANCES_LIST:
                        labeler = event["actor"]["login"]
                    
                if not labeler:
                    return False

                print(f"Labeler: {labeler}")
                return (labeler in reviewers)
                
            else:
                print("No")


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

import re
import config

IMPORTANCES_LIST = config.IMPORTANCES_LIST
AREAS_LIST = config.AREAS_LIST


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
    url_match = re.search(r'https://github\.com/([^/]+)/([^/]+)/(pull|issues)/(\d+)', url)
    if url_match:
        org, repo, _, record_id = url_match.groups()
        return f"https://api.github.com/repos/{org}/{repo}/issues/{record_id}"
        # Reason for using `issues` within the output here: https://stackoverflow.com/questions/68459601/can-we-add-labels-to-a-pull-request-while-creation-using-rest-api
    else:
        return None
    
def labels_verification(labels):
    label_conditions = [
        any(label in labels for label in IMPORTANCES_LIST),
        any(label in labels for label in AREAS_LIST)
    ]
    return all(label_conditions) and len(labels) == 2
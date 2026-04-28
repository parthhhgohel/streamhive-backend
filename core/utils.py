import re

def extract_hashtags(content: str) -> list[str]:
    return list(set(
        tag.lower() for tag in re.findall(r"#(\w+)", content)
    ))

def extract_mentions(content: str) -> list[str]:
    """
    Extract @username mentions from post content
    We'll use this to create mention notifications
    """
    return list(set(
        mention.lower() for mention in re.findall(r"@(\w+)", content)
    ))
import re

def extract_hashtags(content: str) -> list[str]:
    return list(set(
        tag.lower() for tag in re.findall(r"#(\w+)", content)
    ))

def extract_mentions(content: str) -> list[str]:
    return list(set(
        tag.lower() for tag in re.findall(r"@(\w+)", content)
    ))
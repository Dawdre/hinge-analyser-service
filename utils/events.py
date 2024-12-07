import json
from typing import List


def get_like_content(content: List):
    """
    Determine the type of content associated with the given `content`.

    :param content: The content to determine the type of.
    :return: An integer indicating the type of content. 0 for unknown, 1 for photo, 2 for prompt, 3 for video.
    """
    like_stuff = json.loads(content[0]["content"])[0]

    if like_stuff.get("photo") and like_stuff.get("photo").get("url"):
        return 1
    elif like_stuff.get("prompt") and like_stuff.get("prompt").get("question"):
        return 2
    elif like_stuff.get("video") and like_stuff.get("video").get("url"):
        return 3

    return 0

from typing import Dict


def get_like_content(item: Dict):
    """
    Determine the type of content associated with the given `content`.

    :param item: The content to determine the type of.
    :return: An integer indicating the type of content. 0 for unknown, 1 for photo, 2 for prompt, 3 for video.
    """

    get_media = item.get("content")[0]

    if get_media.get("photo") and get_media.get("photo").get("url"):
        return 1
    elif get_media.get("prompt") and get_media.get("prompt").get("question"):
        return 2
    elif get_media.get("video") and get_media.get("video").get("url"):
        return 3

    return 0

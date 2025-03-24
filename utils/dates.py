import dateparser

from models.models import Events


def parse_timestamp(event: dict):
    return dateparser.parse(event["timestamp"])


def calc_per_day(arr):
    return round(len(arr) / (arr[-1].timestamp - arr[0].timestamp).days, 2)


def get_chat_timestamps(events: Events):
    def find_timestamp(e: dict):
        if e.get("chats"):
            for chat in e.get("chats"):
                return parse_timestamp(chat)

    timestamps = map(
        lambda e: find_timestamp(e),
        events.root
    )
    filtered_timestamps = [
        timestamp
        for timestamp in timestamps
        if timestamp is not None
    ]

    return list(filtered_timestamps)


def get_timestamps(events: Events):
    all_timestamps = []

    for event in events.root:
        for key, value in event.data.items():
            # value is always a single item list
            first_item = value[0]

            if isinstance(first_item, dict) and not None:
                if key in ["match", "like", "block"]:
                    all_timestamps.append(parse_timestamp(first_item))

    return all_timestamps


def get_date_ranges(events: Events):
    all_timestamps_sorted = sorted(get_timestamps(events))

    date_range = {
        "start_date": all_timestamps_sorted[0],
        "end_date": all_timestamps_sorted[-1]
    }

    return date_range

import dateparser

from models.models import Events


def parse_timestamp(event: dict):
    return dateparser.parse(event["timestamp"])


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


def get_timestamps(event_type: str, events: Events):
    def filter_types(evt: dict):
        if evt.get("chats"):
            return False
        else:
            return True

    all_events_but_chats = filter(
        lambda e: filter_types(e),
        events.root
    )

    all_timestamps = [
        parse_timestamp(evt.get(event_type)[0])
        for evt in all_events_but_chats
        if evt.get(event_type) is not None
    ]

    return all_timestamps


def get_date_ranges(events: Events):
    all_timestamps = [
        *get_timestamps("match", events),
        *get_timestamps("like", events),
        *get_timestamps("block", events),
        *get_chat_timestamps(events)
    ]

    all_timestamps_sorted = sorted(all_timestamps)

    date_range = {
        "start_date": all_timestamps_sorted[0],
        "end_date": all_timestamps_sorted[-1]
    }

    return date_range

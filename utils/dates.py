import dateparser


def parse_timestamp(event: dict):
    return dateparser.parse(event["timestamp"])

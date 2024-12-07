from typing import Optional, List

from pydantic import BaseModel, field_validator


class ImageUrls(BaseModel):
    urls: List[Optional[str]]

    @field_validator('urls')
    def remove_none_urls(cls, v):
        return [url for url in v if url is not None]


class ThumbNailResponse(BaseModel):
    original_url: Optional[str] = None
    base64: Optional[str] = None
    size: Optional[tuple] = None
    image_error: Optional[str] = None

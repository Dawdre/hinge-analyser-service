from typing import Optional

from pydantic import BaseModel, field_validator


class ImageUrl(BaseModel):
    url: str

    @field_validator('url')
    def remove_none_urls(cls, v):
        if v is None:
            return None
        return v


class ThumbNailResponse(BaseModel):
    original_url: Optional[str] = None
    base64: Optional[str] = None
    size: Optional[tuple] = None
    image_error: Optional[str] = None

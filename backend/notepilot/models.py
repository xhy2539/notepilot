from datetime import datetime, timezone
from typing import Literal
from pydantic import BaseModel, Field, HttpUrl, field_validator


def now():
    return datetime.now(timezone.utc).isoformat()


class Sample(BaseModel):
    id: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=200)
    text: str = Field(default="", max_length=12000)
    url: HttpUrl | None = None
    image_url: HttpUrl | None = None
    published_at: datetime | None = None
    observed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    likes: int | None = Field(default=None, ge=0)
    saves: int | None = Field(default=None, ge=0)
    comments: int | None = Field(default=None, ge=0)
    questions: list[str] = Field(default_factory=list, max_length=20)

    @field_validator('published_at', 'observed_at')
    @classmethod
    def aware_dates(cls, value):
        return value.replace(tzinfo=timezone.utc) if value and value.tzinfo is None else value


class Music(BaseModel):
    id: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=200)
    artist: str = Field(default="", max_length=200)
    version: str = Field(default="原版", max_length=100)
    platform: Literal["xiaohongshu", "douyin", "other"] = "xiaohongshu"
    source_url: HttpUrl
    observed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    rank: int | None = Field(default=None, ge=1)
    mood: str = Field(default="", max_length=200)
    availability: Literal["unknown", "verified"] = "unknown"


class Brief(BaseModel):
    intent: str = Field(min_length=3, max_length=2000)
    audience: str = Field(default="大学生与初学者", max_length=200)
    goal: Literal["save", "follow", "comment"] = "save"
    mode: Literal["demo", "live"] = "demo"
    pages: int = Field(default=6, ge=4, le=9)
    samples: list[Sample] = Field(default_factory=list, max_length=30)
    music: list[Music] = Field(default_factory=list, max_length=20)


class Angle(BaseModel):
    id: str
    title: str = Field(min_length=1, max_length=80)
    reason: str = Field(max_length=500)
    contribution: str = Field(max_length=500)
    sample_ids: list[str] = Field(default_factory=list)


class Slide(BaseModel):
    id: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,40}$")
    kind: Literal["cover", "steps", "compare", "summary"] = "steps"
    title: str = Field(min_length=1, max_length=70)
    body: list[str] = Field(default_factory=list, max_length=5)
    sample_ids: list[str] = Field(default_factory=list)
    image_prompt: str = Field(default="", max_length=2000)
    image_id: str | None = Field(default=None, pattern=r"^[a-f0-9]{32}$")


class Draft(BaseModel):
    titles: list[str] = Field(min_length=1, max_length=3)
    caption: str = Field(max_length=6000)
    tags: list[str] = Field(default_factory=list, max_length=10)
    slides: list[Slide] = Field(min_length=4, max_length=9)
    palette: Literal["mint", "ink", "peach"] = "mint"
    music_id: str | None = None
    music_reason: str = Field(default="暂无可核验音乐候选，发布时确认平台曲库。", max_length=500)


class Edit(BaseModel):
    revision: int = Field(ge=1)
    draft: Draft


class Selection(BaseModel):
    revision: int = Field(ge=1)
    angle_id: str


class Revision(BaseModel):
    revision: int = Field(ge=1)


class ImageRequest(Revision):
    slide_id: str

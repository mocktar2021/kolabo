"""Schemas for country configuration."""
from pydantic import BaseModel, Field


class CountryConfigIn(BaseModel):
    code: str = Field(min_length=2, max_length=2)
    name: str
    currency: str = Field(min_length=3, max_length=3)
    phone_prefix: str
    phone_example: str | None = None
    mobile_money_provider: str | None = None
    enabled: bool = False


class CountryConfigOut(BaseModel):
    code: str
    name: str
    currency: str
    phone_prefix: str
    phone_example: str | None
    mobile_money_provider: str | None
    enabled: bool


class EnabledIn(BaseModel):
    enabled: bool

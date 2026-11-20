"""A böngésző és az API közös adatszerződése, mezőszintű ellenőrzésekkel."""

from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt, StringConstraints, field_validator, model_validator

Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=120)]
Location = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=120)]
Aircraft = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=80)]
Notes = Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)]
Minutes = Annotated[StrictInt, Field(ge=0, le=600)]
Status = Literal["planned", "active", "completed"]


class MissionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: Title
    location: Location
    aircraft: Aircraft
    mission_date: date
    flight_minutes: Minutes = 0
    status: Status = "planned"
    notes: Notes = ""

    @field_validator("mission_date")
    @classmethod
    def date_in_demo_range(cls, value: date) -> date:
        if not date(2000, 1, 1) <= value <= date(2100, 12, 31):
            raise ValueError("A dátum 2000 és 2100 közé essen.")
        return value


class MissionPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: Title | None = None
    location: Location | None = None
    aircraft: Aircraft | None = None
    mission_date: date | None = None
    flight_minutes: Minutes | None = None
    status: Status | None = None
    notes: Notes | None = None

    @model_validator(mode="after")
    def nonempty_nonnull_changes(self):
        if not self.model_fields_set:
            raise ValueError("Legalább egy módosítandó mezőt adj meg.")
        if any(getattr(self, field) is None for field in self.model_fields_set):
            raise ValueError("A megadott mező értéke nem lehet null.")
        if self.mission_date is not None:
            MissionCreate.date_in_demo_range(self.mission_date)
        return self


class Mission(MissionCreate):
    id: int
    created_at: datetime


class MissionList(BaseModel):
    items: list[Mission]
    count: int


class MissionStats(BaseModel):
    total: int
    planned: int
    active: int
    completed: int
    flight_minutes: int

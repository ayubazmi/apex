from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

Priority = Literal["low", "medium", "high", "critical"]
Status = Literal["open", "in_progress", "resolved"]


class TicketCreate(BaseModel):
    title: str = Field(min_length=3, max_length=120)
    description: str = Field(default="", max_length=1000)
    priority: Priority = "medium"


class TicketUpdate(BaseModel):
    status: Optional[Status] = None
    priority: Optional[Priority] = None


class TicketOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    description: str
    priority: str
    status: str
    created_at: datetime

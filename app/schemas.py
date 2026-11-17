from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field
class ServiceCreate(BaseModel):
    name: str
    description: str = ""
    price: float = Field(ge=0)
    duration_minutes: int = Field(default=60, ge=5, le=600)
class ServiceOut(ServiceCreate):
    id: int
    is_active: bool
    model_config = ConfigDict(from_attributes=True)
class CustomerOut(BaseModel):
    id: int
    name: str
    phone: str
    email: str | None
    model_config = ConfigDict(from_attributes=True)
class AppointmentCreate(BaseModel):
    customer_name: str = Field(min_length=1, max_length=120)
    phone: str = Field(min_length=5, max_length=30)
    service_id: int
    start_at: datetime
    notes: str = ""
class AppointmentOut(BaseModel):
    id: int
    customer_id: int
    service_id: int
    start_at: datetime
    end_at: datetime
    status: str
    model_config = ConfigDict(from_attributes=True)
class ChatRequest(BaseModel):
    message: str
    channel: str = "web"
    phone: str | None = None
    name: str | None = None
    conversation_id: int | None = None
class ChatResponse(BaseModel):
    reply: str
    conversation_id: int
    ai_mode: str

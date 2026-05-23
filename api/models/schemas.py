from pydantic import BaseModel, field_validator
from typing import Optional, List
from datetime import datetime


# ── Auth ─────────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ── Children ─────────────────────────────────────────────────────────────────

class ChildCreate(BaseModel):
    name: str
    age: Optional[int] = None
    birthday: Optional[str] = None          # ISO date YYYY-MM-DD
    preset: str = "middle_school"           # elementary | middle_school | high_school | custom
    avatar: Optional[str] = None

class ChildUpdate(BaseModel):
    name: Optional[str] = None
    age: Optional[int] = None
    birthday: Optional[str] = None
    preset: Optional[str] = None
    avatar: Optional[str] = None

class ChildOut(ChildCreate):
    id: int
    created_at: str


# ── Devices ───────────────────────────────────────────────────────────────────

class DeviceOut(BaseModel):
    id: int
    mac: str
    hostname: Optional[str]
    ip: Optional[str]
    label: Optional[str]
    device_type: Optional[str]
    child_id: Optional[int]
    last_seen: Optional[str]

class DeviceAssign(BaseModel):
    child_id: Optional[int]   # None = unassign
    label: Optional[str] = None


# ── Category Rules ────────────────────────────────────────────────────────────

class CategoryRule(BaseModel):
    category: str
    blocked: bool

class BulkCategoryUpdate(BaseModel):
    rules: List[CategoryRule]


# ── Schedules ─────────────────────────────────────────────────────────────────

VALID_DAYS = {"Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"}

class ScheduleCreate(BaseModel):
    name: str
    days: List[str]
    start_time: str   # HH:MM
    end_time: str
    action: str = "block_all"
    enabled: bool = True

    @field_validator("days")
    @classmethod
    def validate_days(cls, v):
        invalid = set(v) - VALID_DAYS
        if invalid:
            raise ValueError(f"Invalid days: {invalid}")
        return v

class ScheduleOut(ScheduleCreate):
    id: int


# ── Allow Exceptions (educational bypass) ────────────────────────────────────

class AllowException(BaseModel):
    domain: str
    label: Optional[str] = None

class AllowExceptionOut(AllowException):
    id: int


# ── DNS Log / Reports ─────────────────────────────────────────────────────────

class DnsLogEntry(BaseModel):
    id: int
    ts: str
    client_ip: Optional[str]
    domain: str
    blocked: bool
    rule: Optional[str]
    child_id: Optional[int]

class DailySummary(BaseModel):
    child_id: Optional[int]
    date: str
    total_queries: int
    blocked_queries: int
    top_domains: List[dict]
    top_blocked: List[dict]


# ── Alerts ────────────────────────────────────────────────────────────────────

class AlertOut(BaseModel):
    id: int
    ts: str
    child_id: Optional[int]
    alert_type: str
    title: str
    detail: Optional[str]
    read: bool


# ── Setup Wizard ──────────────────────────────────────────────────────────────

class WizardStep1(BaseModel):
    network_name: str           # e.g. "The Johnson Family"

class WizardStep2Child(BaseModel):
    name: str
    age: int
    birthday: Optional[str] = None

class WizardStep3(BaseModel):
    device_assignments: List[DeviceAssign]  # mac + child_id pairs

class SetupStatus(BaseModel):
    wizard_complete: bool
    adguard_reachable: bool
    children_count: int
    devices_assigned: int

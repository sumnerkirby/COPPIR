"""Request models.

Every request body is validated here, so bad values are rejected before they
reach application state or get broadcast to clients.
"""
import re
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

# Allowlists for enum-style fields. Validated at the Pydantic layer so invalid
# values are rejected before touching in-memory state or being broadcast to clients.
_VALID_STATUS    = {"Clean", "Monitored", "Contained", "Under Investigation", "Compromised"}
_VALID_OP_STATUS = {"Healthy", "Degraded", "Critical", "Offline"}
_VALID_SEVERITY  = {"info", "warning", "critical"}
_VALID_SECTOR    = {"all", "medical", "government", "power", "emergency", "civilian", "financial"}
_HEX_RE          = re.compile(r'^#[0-9a-fA-F]{6}$')


def _non_blank(v):
    """Trim a name-ish field and reject it if nothing is left.

    min_length alone lets "   " through, which puts a pin on the map with no
    readable label and no way to find it by filtering.
    """
    if v is None:
        return v
    v = v.strip()
    if not v:
        raise ValueError("must not be blank")
    return v


class PinIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    category: str = Field("Asset", max_length=100)

    @field_validator("name", "category")
    @classmethod
    def val_non_blank(cls, v):
        return _non_blank(v)
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)
    status: str = "Clean"
    op_status: str = "Healthy"
    pin_color: Optional[str] = None
    notes: str = Field("", max_length=2000)

    @field_validator("status")
    @classmethod
    def val_status(cls, v):
        if v not in _VALID_STATUS: raise ValueError(f"Invalid status: {v}")
        return v

    @field_validator("op_status")
    @classmethod
    def val_op_status(cls, v):
        if v not in _VALID_OP_STATUS: raise ValueError(f"Invalid op_status: {v}")
        return v

    @field_validator("pin_color")
    @classmethod
    def val_pin_color(cls, v):
        if v is not None and not _HEX_RE.match(v): raise ValueError("pin_color must be #RRGGBB")
        return v

class PinUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=200)
    category: Optional[str] = Field(None, max_length=100)

    @field_validator("name", "category")
    @classmethod
    def val_non_blank(cls, v):
        return _non_blank(v)
    status: Optional[str] = None
    op_status: Optional[str] = None
    pin_color: Optional[str] = None
    notes: Optional[str] = Field(None, max_length=2000)

    @field_validator("status")
    @classmethod
    def val_status(cls, v):
        if v is not None and v not in _VALID_STATUS: raise ValueError(f"Invalid status: {v}")
        return v

    @field_validator("op_status")
    @classmethod
    def val_op_status(cls, v):
        if v is not None and v not in _VALID_OP_STATUS: raise ValueError(f"Invalid op_status: {v}")
        return v

    @field_validator("pin_color")
    @classmethod
    def val_pin_color(cls, v):
        if v is not None and not _HEX_RE.match(v): raise ValueError("pin_color must be #RRGGBB")
        return v

class GeoReq(BaseModel):
    query: str = Field(..., min_length=1, max_length=300)

class NewPinData(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    category: str = Field("Asset", max_length=100)

    @field_validator("name", "category")
    @classmethod
    def val_non_blank(cls, v):
        return _non_blank(v)
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)
    status: str = "Under Investigation"

    @field_validator("status")
    @classmethod
    def val_status(cls, v):
        if v not in _VALID_STATUS: raise ValueError(f"Invalid status: {v}")
        return v

class InjectIn(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: str = Field(..., max_length=2000)
    severity: str = "warning"
    target_pid: Optional[str] = None
    target_status: Optional[str] = None
    new_pin: Optional[NewPinData] = None

    @field_validator("severity")
    @classmethod
    def val_severity(cls, v):
        if v not in _VALID_SEVERITY: raise ValueError(f"Invalid severity: {v}")
        return v

    @field_validator("target_status")
    @classmethod
    def val_target_status(cls, v):
        if v is not None and v not in _VALID_STATUS: raise ValueError(f"Invalid target_status: {v}")
        return v

class LogEntry(BaseModel):
    action: str = Field(..., min_length=1, max_length=500)
    asset_name: Optional[str] = Field(None, max_length=200)
    asset_pid: Optional[str] = None
    notes: str = Field("", max_length=2000)

class ScenarioReq(BaseModel):
    name: str = Field(..., min_length=1, max_length=64)

class BulkStatusReq(BaseModel):
    status: Optional[str] = None
    op_status: Optional[str] = None
    category: Optional[str] = Field(None, max_length=100)

    @field_validator("status")
    @classmethod
    def val_status(cls, v):
        if v is not None and v not in _VALID_STATUS: raise ValueError(f"Invalid status: {v}")
        return v

    @field_validator("op_status")
    @classmethod
    def val_op_status(cls, v):
        if v is not None and v not in _VALID_OP_STATUS: raise ValueError(f"Invalid op_status: {v}")
        return v

class BulkPinItem(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    category: str = Field("Asset", max_length=100)

    @field_validator("name", "category")
    @classmethod
    def val_non_blank(cls, v):
        return _non_blank(v)
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)

class BulkCreate(BaseModel):
    items: List[BulkPinItem] = Field(default_factory=list)
    status: str = "Clean"
    op_status: str = "Healthy"
    pin_color: Optional[str] = None

    @field_validator("status")
    @classmethod
    def val_status(cls, v):
        if v not in _VALID_STATUS: raise ValueError(f"Invalid status: {v}")
        return v

    @field_validator("op_status")
    @classmethod
    def val_op_status(cls, v):
        if v not in _VALID_OP_STATUS: raise ValueError(f"Invalid op_status: {v}")
        return v

    @field_validator("pin_color")
    @classmethod
    def val_pin_color(cls, v):
        if v is not None and not _HEX_RE.match(v): raise ValueError("pin_color must be #RRGGBB")
        return v

class EdgeIn(BaseModel):
    from_pid: str
    to_pid: str
    label: str = Field("", max_length=200)
    edge_type: str = "connection"

class ThresholdIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    sector: str
    below_pct: int = Field(50, ge=0, le=100)
    severity: str = "warning"

    @field_validator("sector")
    @classmethod
    def val_sector(cls, v):
        if v not in _VALID_SECTOR: raise ValueError(f"Invalid sector: {v}")
        return v

    @field_validator("severity")
    @classmethod
    def val_severity(cls, v):
        if v not in _VALID_SEVERITY: raise ValueError(f"Invalid severity: {v}")
        return v

class OSMReq(BaseModel):
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)
    radius_mi: float = Field(15.0, gt=0, le=100)
    category: str

"""
ShopGuard AI - Phase 2 API Data Models
Pydantic schemas for request validation and structured JSON responses.
"""

from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field


class BaseResponse(BaseModel):
    """Standard base schema for all JSON API responses."""
    success: bool = True
    timestamp: float
    timestamp_iso: str


class StatusResponse(BaseModel):
    """System and operational status summary."""
    service_status: str
    security_state: str
    is_armed: bool
    timestamp: float
    timestamp_iso: str
    cameras_total: int
    cameras_connected: int
    active_incidents_today: int
    uptime_seconds: float
    mode: str = "CCTV"
    notice: Optional[str] = None


class CameraInfoModel(BaseModel):
    """Sanitized camera metadata without sensitive credentials."""
    id: str
    name: str
    source_masked: str
    is_connected: bool
    status: str
    fps: float
    resolution: Optional[Tuple[int, int]] = None
    consecutive_failures: int = 0
    last_frame_timestamp: Optional[float] = None
    is_webcam: bool = False
    camera_type: str = "IP Camera"
    location: Optional[str] = None
    ip_address: Optional[str] = None
    port: Optional[int] = None
    stream_path: Optional[str] = None
    last_status_update: Optional[str] = None


class CameraTestRequest(BaseModel):
    """Payload for testing an RTSP stream connection."""
    name: Optional[str] = Field(default="Test Camera", max_length=100)
    camera_type: str = Field(default="IP Camera", max_length=50)
    ip_address: Optional[str] = None
    port: int = Field(default=554, ge=1, le=65535)
    username: Optional[str] = Field(default=None, max_length=100)
    password: Optional[str] = Field(default=None, max_length=200)
    stream_path: Optional[str] = Field(default=None, max_length=200)
    rtsp_url: Optional[str] = Field(default=None, max_length=500)
    timeout_seconds: float = Field(default=4.0, ge=1.0, le=15.0)


class CameraTestResponse(BaseModel):
    """Structured diagnostic result of a camera stream probe."""
    success: bool
    message: str
    resolution: Optional[Tuple[int, int]] = None
    fps: Optional[float] = None
    latency_ms: Optional[float] = None
    source_masked: str = ""
    details: Optional[str] = None


class CameraCreateRequest(BaseModel):
    """Payload to add a new monitored CCTV camera."""
    id: Optional[str] = Field(default=None, max_length=50, pattern=r"^[a-zA-Z0-9_\-]+$")
    name: str = Field(min_length=1, max_length=100)
    camera_type: str = Field(default="IP Camera", max_length=50)
    ip_address: Optional[str] = None
    port: int = Field(default=554, ge=1, le=65535)
    username: Optional[str] = Field(default=None, max_length=100)
    password: Optional[str] = Field(default=None, max_length=200)
    stream_path: Optional[str] = Field(default=None, max_length=200)
    rtsp_url: Optional[str] = Field(default=None, max_length=500)
    location: Optional[str] = Field(default=None, max_length=150)
    fps: float = Field(default=5.0, ge=0.5, le=60.0)
    enabled: bool = True


class CameraUpdateRequest(BaseModel):
    """Payload to update an existing camera configuration."""
    name: Optional[str] = Field(default=None, max_length=100)
    camera_type: Optional[str] = Field(default=None, max_length=50)
    ip_address: Optional[str] = None
    port: Optional[int] = Field(default=None, ge=1, le=65535)
    username: Optional[str] = Field(default=None, max_length=100)
    password: Optional[str] = Field(default=None, max_length=200)
    stream_path: Optional[str] = Field(default=None, max_length=200)
    rtsp_url: Optional[str] = Field(default=None, max_length=500)
    location: Optional[str] = Field(default=None, max_length=150)
    fps: Optional[float] = Field(default=None, ge=0.5, le=60.0)
    enabled: Optional[bool] = None


class CameraOperationResponse(BaseModel):
    """Result of camera add, edit, or remove operations."""
    success: bool
    camera_id: str
    message: str
    camera: Optional[CameraInfoModel] = None


class CamerasResponse(BaseModel):
    """List of all registered cameras and aggregated health status."""
    total: int
    connected: int
    cameras: List[CameraInfoModel]


class SecurityStateResponse(BaseModel):
    """Current state machine status and pre-arm check readiness."""
    state: str
    is_armed: bool
    can_arm: bool
    active_zones_count: int
    connected_cameras: int
    total_cameras: int
    last_state_change: Optional[str] = None
    rejection_reasons: List[str] = Field(default_factory=list)


class ArmRequest(BaseModel):
    """Payload for arming request."""
    reason: Optional[str] = Field(default="Manual local API arm request", max_length=200)


class DisarmRequest(BaseModel):
    """Payload for disarming request."""
    reason: Optional[str] = Field(default="Manual local API disarm request", max_length=200)


class ArmOperationResponse(BaseModel):
    """Result of arming operation."""
    success: bool
    state: str
    message: str
    timestamp: float
    timestamp_iso: str
    reasons: Optional[List[str]] = None


class DisarmOperationResponse(BaseModel):
    """Result of disarming operation."""
    success: bool
    state: str
    message: str
    timestamp: float
    timestamp_iso: str


class IncidentSummaryModel(BaseModel):
    """High-level summary of a recorded intrusion incident."""
    incident_id: str
    camera_id: str
    camera_name: str
    event_type: str
    event_timestamp: str
    timestamp: float
    track_id: Optional[int] = None
    confidence: float
    zone_name: str
    video_filename: Optional[str] = None
    has_video: bool = False
    duration_seconds: float = 0.0
    review_status: str = "UNREVIEWED"


class IncidentsListResponse(BaseModel):
    """Paginated list of local incident history."""
    total: int
    limit: int
    offset: int
    incidents: List[IncidentSummaryModel]


class IncidentDetailResponse(BaseModel):
    """Detailed metadata for a specific incident."""
    incident_id: str
    camera_id: str
    camera_name: str
    event_type: str
    event_timestamp: str
    track_id: Optional[int] = None
    detection_confidence: float
    confidence: float
    zone_id: str
    zone_name: str
    video_filename: str
    video_exists: bool
    video_size_bytes: int = 0
    review_status: str
    duration_seconds: float
    total_frames: int
    source_type: str
    simulation_mode: bool
    rtsp_verified: bool


class HealthResponse(BaseModel):
    """Diagnostic health summary of all components."""
    healthy: bool
    overall_health: str  # "HEALTHY", "DEGRADED", "CRITICAL"
    security_state: str
    ai_model_loaded: bool
    ai_model_path: str
    ai_device: str
    disk_free_gb: float
    disk_total_gb: float
    cameras: List[Dict[str, Any]]
    timestamp: float
    mode: str = "CCTV"
    notice: Optional[str] = None


class SystemInfoResponse(BaseModel):
    """Host environment and runtime diagnostic information."""
    service_name: str = "ShopGuard AI Local Security Agent"
    version: str = "2.0.0"
    operating_system: str
    python_version: str
    uptime_seconds: float
    cpu_count: int
    process_memory_mb: float
    total_incidents_recorded: int
    api_host: str
    api_port: int
    auth_enabled: bool


class ErrorResponse(BaseModel):
    """Standardized error format."""
    error: str
    message: str
    timestamp: float


class DeviceTokenRegisterRequest(BaseModel):
    """Request payload to register an FCM device token."""
    token: str = Field(..., min_length=10, max_length=4096)
    device_name: Optional[str] = Field(default="Android Device", max_length=100)
    app_version: Optional[str] = Field(default="1.0.0", max_length=50)


class DeviceTokenUnregisterRequest(BaseModel):
    """Request payload to unregister an FCM device token."""
    token: str = Field(..., min_length=10, max_length=4096)


class NotificationTestRequest(BaseModel):
    """Request payload for triggering an administrative test notification."""
    title: Optional[str] = Field(default="Test Alert", max_length=100)
    body: Optional[str] = Field(default="This is a test notification from ShopGuard AI.", max_length=500)


class NotificationOperationResponse(BaseModel):
    """Response returned upon registering/unregistering an FCM device token or sending a test alert."""
    success: bool
    message: str
    tokens_count: int
    timestamp: float
    timestamp_iso: str


class NotificationStatusResponse(BaseModel):
    """Status summary of the FCM notification manager."""
    configured: bool
    credentials_present: bool
    tokens_count: int
    timestamp: float
    timestamp_iso: str


import os
import re
import shutil
from typing import Any, Dict, Optional
import yaml

from .logger import get_logger, mask_url

logger = get_logger("helpers")


def resolve_env_vars(value: Any) -> Any:
    """
    Recursively resolves environment variable placeholders in configuration values.
    Supports:
      - 'ENV:VAR_NAME'
      - '${VAR_NAME}'
      - '$VAR_NAME'
    """
    if isinstance(value, str):
        # Match ENV:VAR_NAME
        if value.startswith("ENV:"):
            env_key = value[4:].strip()
            env_val = os.getenv(env_key)
            if env_val is None:
                logger.warning(f"Environment variable '{env_key}' not found in environment.")
                return ""
            return env_val

        # Match ${VAR_NAME}
        pattern = re.compile(r"\$\{([A-Za-z0-9_]+)\}")
        matches = pattern.findall(value)
        if matches:
            res = value
            for key in matches:
                env_val = os.getenv(key, "")
                if not env_val:
                    logger.warning(f"Environment variable '{key}' not set.")
                res = res.replace(f"${{{key}}}", env_val)
            return res

        return value

    elif isinstance(value, dict):
        return {k: resolve_env_vars(v) for k, v in value.items()}
    elif isinstance(value, list):
        return [resolve_env_vars(v) for v in value]
    return value


def load_config(config_path: str = "config/config.yaml") -> Dict[str, Any]:
    """
    Loads YAML configuration file, resolves environment variables, and validates required sections.
    """
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    # Optionally load .env file if python-dotenv is available
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    with open(config_path, "r", encoding="utf-8") as f:
        try:
            raw_config = yaml.safe_load(f) or {}
        except yaml.YAMLError as e:
            raise ValueError(f"YAML parsing error in {config_path}: {e}") from e

    config = resolve_env_vars(raw_config)
    validate_config(config)
    return config


def validate_config(config: Dict[str, Any]) -> None:
    """
    Validates the structure and essential parameters of the configuration dictionary.
    Raises ValueError with descriptive explanation on invalid settings.
    """
    required_sections = ["security", "recording", "ai", "cameras"]
    for section in required_sections:
        if section not in config:
            raise ValueError(f"Missing required configuration section: '{section}'")

    # Security section validation
    sec = config.get("security", {})
    if "confidence_threshold" in sec:
        th = sec["confidence_threshold"]
        if not (0.0 <= float(th) <= 1.0):
            raise ValueError(f"Invalid confidence_threshold: {th}. Must be between 0.0 and 1.0")

    if "minimum_persistence_seconds" in sec:
        pers = sec["minimum_persistence_seconds"]
        if float(pers) < 0:
            raise ValueError(f"minimum_persistence_seconds must be >= 0, got {pers}")

    if "event_cooldown_seconds" in sec:
        cd = sec["event_cooldown_seconds"]
        if float(cd) < 0:
            raise ValueError(f"event_cooldown_seconds must be >= 0, got {cd}")

    # Cameras section validation
    cameras = config.get("cameras", [])
    if not isinstance(cameras, list):
        raise ValueError("'cameras' configuration must be a list of camera objects")

    camera_ids = set()
    for idx, cam in enumerate(cameras):
        if not isinstance(cam, dict):
            raise ValueError(f"Camera item at index {idx} must be a dictionary")
        if "id" not in cam or not cam["id"]:
            raise ValueError(f"Camera at index {idx} is missing a unique 'id'")
        if cam["id"] in camera_ids:
            raise ValueError(f"Duplicate camera id detected: '{cam['id']}'")
        camera_ids.add(cam["id"])

        if "source" not in cam or cam["source"] is None:
            raise ValueError(f"Camera '{cam['id']}' is missing 'source' configuration")


def detect_compute_device(requested_device: Optional[str] = "cpu") -> str:
    """
    Detects available compute devices (CPU vs CUDA GPU).
    Falls back gracefully to 'cpu' if CUDA is unavailable or not configured.
    """
    req = (requested_device or "cpu").lower()

    try:
        import torch
        cuda_available = torch.cuda.is_available()
    except ImportError:
        cuda_available = False

    if req == "cuda":
        if cuda_available:
            try:
                import torch
                gpu_name = torch.cuda.get_device_name(0)
                logger.info(f"Using NVIDIA GPU acceleration: {gpu_name}")
                return "cuda"
            except Exception as e:
                logger.warning(f"Error accessing CUDA device: {e}. Falling back to CPU.")
                return "cpu"
        else:
            logger.info("CUDA requested but no compatible NVIDIA GPU or CUDA drivers detected. Falling back to CPU.")
            return "cpu"

    logger.info("Using CPU for inference (standard default).")
    return "cpu"


def check_disk_space(path: str = ".", min_gb_warning: float = 2.0) -> Dict[str, float]:
    """
    Checks free disk space on the volume hosting the given path.
    Returns dictionary with total, used, and free space in gigabytes.
    """
    try:
        usage = shutil.disk_usage(path)
        total_gb = usage.total / (1024 ** 3)
        used_gb = usage.used / (1024 ** 3)
        free_gb = usage.free / (1024 ** 3)

        if free_gb < min_gb_warning:
            logger.warning(f"Low disk space on {os.path.abspath(path)}: {free_gb:.2f} GB free.")

        return {
            "total_gb": round(total_gb, 2),
            "used_gb": round(used_gb, 2),
            "free_gb": round(free_gb, 2),
        }
    except Exception as e:
        logger.error(f"Failed to check disk space for path '{path}': {e}")
        return {"total_gb": 0.0, "used_gb": 0.0, "free_gb": 0.0}

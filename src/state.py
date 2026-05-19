import threading
import time
import copy

from src.config import (
    STREAM_PORT_RIGHT,
    STREAM_PORT_LEFT,
    CAMERAS,
)

# =============================================================================
# Thread synchronization
# =============================================================================

stop_event = threading.Event()
frame_lock = threading.Lock()
status_lock = threading.Lock()
connection_lock = threading.Lock()

# =============================================================================
# Frame state
# =============================================================================

latest_frames = {port: None for port in CAMERAS}
frame_timestamps = {port: 0.0 for port in CAMERAS}

fps_data = {
    port: {
        "frames": 0,
        "last_time": time.time(),
        "fps": 0.0,
    }
    for port in CAMERAS
}

# =============================================================================
# Connection state
# =============================================================================

connected_cameras = set()

# =============================================================================
# System state
# =============================================================================

systemStatus = {
    "controlMode": 0,  # 0: Rover, 1: Calibration, 2: Depth
    "cameraBroadcasting": False,
    "roverBroadcasting": False,
    "roverConnected": False,
    "cameraData": {
        "rightCameraConnected": False,
        "leftCameraConnected": False,
        "rightCameraFPS": 0.0,
        "leftCameraFPS": 0.0,
    },
    "encodersData": {
        "frontRightMotorEncoderReading": {
            "encoderDir": "",
            "encoderStep": 0,
            "encoderTurns": 0,
            "encoderUpdated": False,
        },
        "frontLeftMotorEncoderReading": {
            "encoderDir": "",
            "encoderStep": 0,
            "encoderTurns": 0,
            "encoderUpdated": False,
        },
        "rearRightMotorEncoderReading": {
            "encoderDir": "",
            "encoderStep": 0,
            "encoderTurns": 0,
            "encoderUpdated": False,
        },
        "rearLeftMotorEncoderReading": {
            "encoderDir": "",
            "encoderStep": 0,
            "encoderTurns": 0,
            "encoderUpdated": False,
        },
    },
    "accelerometerData": {
        "accelerometerXReading": 0,
        "accelerometerYReading": 0,
        "accelerometerZReading": 0,
    },
    "gyroscopeData": {
        "gyroscopeXReading": 0,
        "gyroscopeYReading": 0,
        "gyroscopeZReading": 0,
    },
    "takenPictures": {
        "captureCount": 0,
    },
}

# =============================================================================
# Status helpers
# =============================================================================


def get_status_copy():
    with status_lock:
        return copy.deepcopy(systemStatus)


def set_control_mode(mode: int):
    with status_lock:
        systemStatus["controlMode"] = mode


def get_control_mode():
    with status_lock:
        return systemStatus["controlMode"]


def set_camera_broadcasting(enabled: bool):
    with status_lock:
        systemStatus["cameraBroadcasting"] = enabled


def get_camera_broadcasting():
    with status_lock:
        return systemStatus["cameraBroadcasting"]


def set_rover_broadcasting(enabled: bool):
    with status_lock:
        systemStatus["roverBroadcasting"] = enabled


def get_rover_broadcasting():
    with status_lock:
        return systemStatus["roverBroadcasting"]


def set_rover_connected(status: bool):
    with status_lock:
        systemStatus["roverConnected"] = status


def get_rover_connected():
    with status_lock:
        return systemStatus["roverConnected"]


# =============================================================================
# Encoder helpers
# =============================================================================


def set_encoder_reading(name, value):
    if name not in systemStatus["encodersData"]:
        raise KeyError(f"Unknown encoder field: {name}")

    with status_lock:
        encoder_state = systemStatus["encodersData"][name]

        encoder_state["encoderDir"] = value.get("encoderDir", "")

        encoder_state["encoderStep"] = value.get("encoderStep", 0)

        encoder_state["encoderTurns"] = value.get("encoderTurns", 0)

        encoder_state["encoderUpdated"] = value.get(
            "encoderUpdated",
            False,
        )


# =============================================================================
# Accelerometer helpers
# =============================================================================


def set_accelerometer_reading(axis: str, value):
    key = f"accelerometer{axis.capitalize()}Reading"

    with status_lock:
        if key not in systemStatus["accelerometerData"]:
            raise KeyError(f"Unknown accelerometer axis: {axis}")

        systemStatus["accelerometerData"][key] = value


# =============================================================================
# Gyroscope helpers
# =============================================================================


def set_gyroscope_reading(axis: str, value):
    key = f"gyroscope{axis.capitalize()}Reading"

    with status_lock:
        if key not in systemStatus["gyroscopeData"]:
            raise KeyError(f"Unknown gyroscope axis: {axis}")

        systemStatus["gyroscopeData"][key] = value


# =============================================================================
# Frame helpers
# =============================================================================


def set_latest_frame(port, frame):
    with frame_lock:
        latest_frames[port] = frame
        frame_timestamps[port] = time.time()


def get_frame_timestamp(port):
    with frame_lock:
        return frame_timestamps.get(port, 0)


def get_latest_frame(port):
    with frame_lock:
        return latest_frames.get(port)


def get_latest_frames_copy():
    with frame_lock:
        return latest_frames.copy()


def update_fps(port):
    now = time.time()

    with frame_lock:
        data = fps_data[port]

        data["frames"] += 1

        elapsed = now - data["last_time"]

        if elapsed >= 1.0:
            data["fps"] = data["frames"] / elapsed
            data["frames"] = 0
            data["last_time"] = now


def get_camera_fps(port):
    with frame_lock:
        return fps_data[port]["fps"]


def refresh_fps():
    with status_lock:
        systemStatus["cameraData"]["rightCameraFPS"] = get_camera_fps(STREAM_PORT_RIGHT)

        systemStatus["cameraData"]["leftCameraFPS"] = get_camera_fps(STREAM_PORT_LEFT)


# =============================================================================
# Camera connection helpers
# =============================================================================


def get_connected_cameras():
    with connection_lock:
        return connected_cameras.copy()


def connect_camera(port):
    with connection_lock:
        connected_cameras.add(port)

    refresh_connection_flags()


def disconnect_camera(port):
    with connection_lock:
        connected_cameras.discard(port)

    refresh_connection_flags()


def get_connected_camera_count():
    with connection_lock:
        return len(connected_cameras)


def is_camera_connected(port):
    with connection_lock:
        return port in connected_cameras


def get_connection_flags():
    with connection_lock:
        return (
            STREAM_PORT_RIGHT in connected_cameras,
            STREAM_PORT_LEFT in connected_cameras,
        )


def all_cameras_connected():
    with connection_lock:
        return len(connected_cameras) == len(CAMERAS)


def refresh_connection_flags():
    right, left = get_connection_flags()

    with status_lock:
        systemStatus["cameraData"]["rightCameraConnected"] = right
        systemStatus["cameraData"]["leftCameraConnected"] = left


# =============================================================================
# Capture helpers
# =============================================================================


def get_capture_count():
    with status_lock:
        return systemStatus["takenPictures"]["captureCount"]


def increment_capture_count():
    with status_lock:
        current = systemStatus["takenPictures"]["captureCount"]
        systemStatus["takenPictures"]["captureCount"] += 1
        return current

import json
import socket
import threading

from src.config import ROVER_CONTROL_PORT
from src.state import (
    set_encoder_reading,
    set_gyroscope_reading,
    stop_event,
    set_rover_connected,
    set_accelerometer_reading,
)

_server_socket = None
_client_socket = None

_socket_lock = threading.Lock()


def rover_control():
    """
    TCP server that waits for rover connection
    and receives telemetry/messages.
    """

    global _server_socket
    global _client_socket

    _server_socket = socket.socket(
        socket.AF_INET,
        socket.SOCK_STREAM,
    )

    _server_socket.setsockopt(
        socket.SOL_SOCKET,
        socket.SO_REUSEADDR,
        1,
    )

    _server_socket.bind(("0.0.0.0", ROVER_CONTROL_PORT))
    _server_socket.listen(1)

    _server_socket.settimeout(1.0)

    print(f"[ROVER CONTROL] Waiting for rover on port {ROVER_CONTROL_PORT}")

    while not stop_event.is_set():
        try:
            client_socket, addr = _server_socket.accept()

            print(f"[ROVER CONTROL] Rover connected from {addr[0]}")

            with _socket_lock:
                _client_socket = client_socket

            set_rover_connected(True)

            _handle_rover_connection(client_socket)

        except socket.timeout:
            continue

        except Exception as e:
            print("[ROVER CONTROL] Error:", e)

    cleanup()


def _handle_rover_connection(client_socket):
    """
    Receives messages from rover
    until disconnect.
    """

    global _client_socket

    client_socket.settimeout(1.0)

    try:
        while not stop_event.is_set():
            try:
                data = client_socket.recv(4096)

                if not data:
                    print("[ROVER CONTROL] Rover disconnected")
                    break

                _process_message(data)

            except socket.timeout:
                continue

            except Exception as e:
                print("[ROVER CONTROL] Receive error:", e)
                break

    finally:
        with _socket_lock:
            _client_socket = None

        set_rover_connected(False)

        try:
            client_socket.close()
        except Exception:
            pass


def _process_message(data: bytes):
    """
    Process telemetry received from rover.
    """

    try:
        message = json.loads(data.decode())

    except json.JSONDecodeError as e:
        print("[ROVER CONTROL] Invalid JSON:", e)
        return

    print("[ROVER RX]", message)

    try:
        # ==========================================================
        # Encoders
        # ==========================================================

        encoders = message.get("encodersData")

        if encoders:
            mapping = (
                "frontRightMotorEncoderReading",
                "frontLeftMotorEncoderReading",
                "rearRightMotorEncoderReading",
                "rearLeftMotorEncoderReading",
            )

            for key in mapping:
                encoder_data = encoders.get(key)

                if encoder_data is None:
                    continue

                set_encoder_reading(
                    key,
                    encoder_data,
                )

        # ==========================================================
        # Accelerometer
        # ==========================================================

        accel = message.get("accelerometerData")

        if accel:
            for axis in ("x", "y", "z"):
                value = accel.get(axis)

                if value is None:
                    continue

                set_accelerometer_reading(
                    axis,
                    value,
                )

        # ==========================================================
        # Gyroscope
        # ==========================================================

        gyro = message.get("gyroscopeData")

        if gyro:
            for axis in ("x", "y", "z"):
                value = gyro.get(axis)

                if value is None:
                    continue

                set_gyroscope_reading(
                    axis,
                    value,
                )

    except Exception as e:
        print(f"[ROVER CONTROL] Message processing error: {e}")


def send_to_rover(message: dict):
    """
    Send JSON message to rover.
    Safe to call from anywhere.
    """

    with _socket_lock:
        sock = _client_socket

    if sock is None:
        print("[ROVER CONTROL] No rover connected")
        return False

    try:
        payload = (json.dumps(message) + "\n").encode()  # ← adiciona \n
        sock.sendall(payload)
        return True

    except Exception as e:
        print("[ROVER CONTROL] Send error:", e)


def cleanup():
    global _client_socket
    global _server_socket

    with _socket_lock:
        if _client_socket:
            try:
                _client_socket.close()
            except Exception:
                pass

            _client_socket = None

    if _server_socket:
        try:
            _server_socket.close()
        except Exception:
            pass

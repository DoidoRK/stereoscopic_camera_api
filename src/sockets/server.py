import threading

from src.config import CAMERAS
from src.sockets.camera.broadcast import cameras_send_broadcast
from src.sockets.camera.receiver import stream_receiver
from src.sockets.camera.watchdog import watchdog
from src.sockets.rover.broadcast import rover_send_broadcast
from src.sockets.rover.control import rover_control

_threads = []


def start_socket_server():
    """Start all TCP/UDP socket services."""

    print("[SOCKETS] Starting...")

    _start_thread(
        target=cameras_send_broadcast,
        name="camera-broadcast",
    )

    for port, info in CAMERAS.items():
        _start_thread(
            target=stream_receiver,
            args=(port, info["name"], info["side"]),
            name=f"camera-{info['side']}",
        )

    _start_thread(
        target=watchdog,
        name="camera-watchdog",
    )

    _start_thread(
        target=rover_send_broadcast,
        name="rover-broadcast",
    )

    _start_thread(
        target=rover_control,
        name="rover-control",
    )

    print("[SOCKETS] Running")


def stop_socket_server(timeout=2):
    """Wait for all socket threads to finish."""

    print("[SOCKETS] Stopping")

    for thread in _threads:
        thread.join(timeout=timeout)


def _start_thread(target, args=(), name=None):
    thread = threading.Thread(
        target=target,
        args=args,
        daemon=True,
        name=name,
    )

    thread.start()
    _threads.append(thread)

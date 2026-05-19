import socket
import time
from src.config import ROVER_BROADCAST_MSG, ROVER_BROADCAST_PORT, BROADCAST_INTERVAL
from src.state import (
    stop_event,
    get_rover_broadcasting,
    get_rover_connected,
    set_rover_broadcasting,
)
from src.utils import get_broadcast_addr


def rover_send_broadcast():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

    print(f"Rover UDP Broadcast started in port: {ROVER_BROADCAST_PORT}")

    broadcast_addr = get_broadcast_addr()

    try:
        while not stop_event.is_set():
            connected = get_rover_connected()
            broadcasting = get_rover_broadcasting()
            if not connected:
                if not broadcasting:
                    set_rover_broadcasting(True)

                try:
                    sock.sendto(
                        ROVER_BROADCAST_MSG,
                        (broadcast_addr, ROVER_BROADCAST_PORT),
                    )

                    print("Sending rover broadcast message")

                except Exception as e:
                    print("Rover Broadcast error:", e)

            else:
                if broadcasting:
                    set_rover_broadcasting(False)
                    print("Stopping broadcast: rover connected")

            time.sleep(BROADCAST_INTERVAL)

    finally:
        sock.close()
        set_rover_broadcasting(False)

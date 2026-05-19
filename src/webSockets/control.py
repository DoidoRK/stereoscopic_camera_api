import asyncio
import json
import websockets
import cv2
from src.config import (
    STATUS_SEND_INTERVAL,
    STREAM_PORT_LEFT,
    STREAM_PORT_RIGHT,
    LEFT_IMAGE_FOLDER,
    RIGHT_IMAGE_FOLDER,
)
from src.sockets.rover.control import send_to_rover
from src.state import (
    frame_lock,
    refresh_fps,
    stop_event,
    refresh_connection_flags,
    get_status_copy,
    set_control_mode,
    latest_frames,
    increment_capture_count,
    get_capture_count,
)


async def send_status(websocket):
    """Periodically send current system status as JSON.

    The status dictionary is built from :data:`systemStatus` so
    that all of the fields requested by the UI are available.  Helper
    functions are used to update FPS and connectivity before each send.
    """
    while not stop_event.is_set():
        # refresh values that are derived from other globals
        refresh_fps()
        refresh_connection_flags()
        status = get_status_copy()
        try:
            await websocket.send(json.dumps(status))
        except websockets.exceptions.ConnectionClosed:
            break
        await asyncio.sleep(STATUS_SEND_INTERVAL)


async def receive_commands(websocket):
    while not stop_event.is_set():
        try:
            message = await websocket.recv()
            if not isinstance(message, str):
                print("Received non-text message (binary?) → ignoring")
                continue

            try:
                data = json.loads(message)
            except json.JSONDecodeError:
                print(f"Invalid JSON received: {message}")
                continue

            # Handle ping messages
            if data.get("type") == "ping":
                try:
                    await websocket.send(json.dumps({"type": "pong"}))
                except Exception as e:
                    print(f"Failed to send pong: {e}")
                continue

            # Handle mode messages
            if data.get("type") == "mode":
                mode_str = data.get("mode")
                if mode_str == "control":
                    set_control_mode(0)
                    print("Switched to control mode")
                elif mode_str == "calibration":
                    set_control_mode(1)
                    print("Switched to calibration mode")
                elif mode_str == "depth":
                    set_control_mode(2)
                    print("Switched to depth mode")
                else:
                    print(f"Unknown mode: {mode_str}")
                continue

            # Handle command messages
            if data.get("type") == "command":
                if data.get("command") == "drive":
                    state = data.get("state")
                    rover_direction = ""
                    if state.get("state") == "press":
                        match state.get("key"):
                            case "w":
                                rover_direction = "forward"
                                print("forward")
                            case "s":
                                rover_direction = "backward"
                                print("backward")
                            case "a":
                                rover_direction = "left"
                                print("left")
                            case "d":
                                rover_direction = "right"
                                print("right")
                    else:
                        rover_direction = "stop"
                        print("stop")
                    rover_message = {
                        "command": "move",
                        "direction": rover_direction,
                    }
                    send_to_rover(rover_message)

            if data.get("command") == "saveImage":
                print("Taking pictures")

                with frame_lock:
                    if (
                        latest_frames[STREAM_PORT_LEFT] is not None
                        and latest_frames[STREAM_PORT_RIGHT] is not None
                    ):
                        left_image = latest_frames[STREAM_PORT_LEFT][:, :, 0]
                        right_image = latest_frames[STREAM_PORT_RIGHT][:, :, 0]

                        count = get_capture_count()

                        name_l = f"{LEFT_IMAGE_FOLDER}/{count}.jpg"
                        name_r = f"{RIGHT_IMAGE_FOLDER}/{count}.jpg"

                        cv2.imwrite(name_l, left_image)
                        cv2.imwrite(name_r, right_image)

                        increment_capture_count()

            continue

        except websockets.exceptions.ConnectionClosed:
            break
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"Unexpected error in receive loop: {e}")
            break


async def status_handler(websocket):
    # 'path' argument dropped for compatibility with current websockets library
    print("Client connected to system status")
    send_task = asyncio.create_task(send_status(websocket))
    receive_task = asyncio.create_task(receive_commands(websocket))
    try:
        await asyncio.gather(send_task, receive_task)
    except asyncio.CancelledError:
        pass
    finally:
        send_task.cancel()
        receive_task.cancel()
        print("Status client disconnected")

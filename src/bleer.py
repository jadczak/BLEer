import asyncio
import msvcrt
import sys

from bleak import BleakScanner
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData
from typing import ValuesView

from ansi_commands import Keys, flush, clear, home, move_cursor, hide_cursor, highlight, show_cursor, reset_color, write

OK = 0
ERROR = 1


async def get_key(queue: asyncio.Queue):
    while True:
        if msvcrt.kbhit():
            key = msvcrt.getwch()
            if key == Keys.SPECIAL1 or key == Keys.SPECIAL2:
                key += msvcrt.getwch()
                await queue.put(key)
            else:
                await queue.put(key.lower())
        else:
            await asyncio.sleep(0.01)


async def scan(
    timeout: float, event: asyncio.Event, queue: asyncio.Queue[dict[str, tuple[BLEDevice, AdvertisementData]]]
):
    while True:
        await event.wait()
        async with BleakScanner() as scanner:
            await asyncio.sleep(timeout)
            await queue.put(scanner.discovered_devices_and_advertisement_data)
            write(1, FOOTER, f"{'Scanning Finished':{WIDTH}}")
            flush()
            event.clear()


HEIGHT: int = 41
WIDTH: int = 120
HEADER: int = 1
TOP_SEPERATOR: int = HEADER + 1
FIRST_LINE: int = TOP_SEPERATOR + 1
FIRST_USER: int = FIRST_LINE + 1
FOOTER: int = HEIGHT - 1
BOTTOM_SEPERATOR: int = FOOTER - 1
LAST_LINE: int = BOTTOM_SEPERATOR - 1
MID_LINE: int = (LAST_LINE - FIRST_LINE) // 2


def update_scan_result(devices_and_data: ValuesView[tuple[BLEDevice, AdvertisementData]], user_line: int) -> int:
    # not need to redraw if we are already at the limit of the screen.
    if user_line < FIRST_USER:
        user_line = FIRST_USER
        return user_line
    if user_line >= LAST_LINE:
        user_line = LAST_LINE
        return user_line

    NAME_LEN = 20
    ADDR_LEN = 20
    RSSI_LEN = 6
    LOCAL_LEN = 20

    header = f"{'Name':{NAME_LEN}}{'Address':{ADDR_LEN}}{
        'RSSI':^{RSSI_LEN}}{'Local Name':{LOCAL_LEN}}"
    write(1, FIRST_LINE, header)
    # TODO: We're going to want to dynamically slice into the tuple, based on
    #       where the user is in the list.  Once we get past half way down the
    #       list and we aren't showing the bottom we should bump the view.
    #       Same thing in the other direction.  If we cross into the upper half
    #       of the window and we aren't showing the top of the list, bump the list
    #       down one.  When we are in bump mode the user line is going to stay
    #       where it is and the list will move under it.

    # FIX:  currently user_line can walk past the bottom of the list.
    for dev_no, (dev, data) in enumerate(devices_and_data, 1):
        write_line = FIRST_LINE + dev_no
        if write_line < LAST_LINE:
            name = dev.name if dev.name else "<UNKNOWN>"
            if len(name) >= NAME_LEN:
                name = name[: NAME_LEN - 4] + "..."
            local_name = data.local_name if data.local_name else "<UNKNOWN>"
            if len(local_name) >= NAME_LEN:
                local_name = local_name[: NAME_LEN - 4] + "..."

            dev_addr = dev.address
            s = f"{name:{NAME_LEN}}{dev_addr:{ADDR_LEN}}{
                data.rssi:^{RSSI_LEN}}{local_name:{LOCAL_LEN}}"
            if write_line == user_line:
                highlight(1, write_line, s)
            else:
                write(1, write_line, s)
        else:
            write(1, write_line, f"{'---MORE---':{WIDTH}}")
            flush()
            break
        flush()
    return user_line


async def main():
    # Setup the terminal
    hide_cursor()
    clear()
    home()
    write(1, HEADER, f"{'(Q)uit (S)can':{WIDTH}}")
    write(1, TOP_SEPERATOR, "-" * WIDTH)
    write(1, BOTTOM_SEPERATOR, "-" * WIDTH)
    flush()

    # Setup all_tasks
    main_task = asyncio.current_task()
    scan_event = asyncio.Event()
    scan_queue: asyncio.Queue[dict[str, tuple[BLEDevice,
                                              AdvertisementData]]] = asyncio.Queue()
    key_queue = asyncio.Queue()
    asyncio.create_task(scan(5.0, scan_event, scan_queue), name="scan task")
    asyncio.create_task(get_key(key_queue), name="keyboard task")

    # Main loop
    key = ""
    user_line: int = FIRST_USER
    devices_and_data = {}.values()
    while key != Keys.Q:
        # Get keyboard input
        if not key_queue.empty():
            key = await key_queue.get()
        else:
            key = ""
        # Handle keyboard input
        match key:
            case Keys.S:
                if scan_event.is_set():
                    write(1, FOOTER, f"{'Scan already in process':{WIDTH}}")
                else:
                    scan_event.set()
                    write(1, FOOTER, f"{'Starting scan...':{WIDTH}}")
                flush()
            case Keys.UP:
                if devices_and_data:
                    user_line -= 1
                    user_line = update_scan_result(devices_and_data, user_line)
            case Keys.DOWN:
                if devices_and_data:
                    user_line += 1
                    user_line = update_scan_result(devices_and_data, user_line)

        # Handle scan results
        if not scan_queue.empty():
            scan_results = await scan_queue.get()
            devices_and_data = scan_results.values()
            user_line = FIRST_USER
            update_scan_result(devices_and_data, user_line)
        await asyncio.sleep(0.01)

    # Clean up on quit
    for task in asyncio.all_tasks():
        if not (task == main_task):
            task.cancel()
    reset_color()
    move_cursor(1, HEIGHT)
    show_cursor()
    return OK


if __name__ == "__main__":
    asyncio.run(main())
    sys.exit(OK)

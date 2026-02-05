import asyncio
import msvcrt
import sys
import time

from bleak import BleakScanner
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData
from itertools import cycle
from typing import ValuesView

from ansi_commands import Keys, flush, clear, home, move_cursor, hide_cursor, highlight, show_cursor, reset_color, write

OK = 0
ERROR = 1

# Screen coordinates and offsets
HEIGHT: int = 38
WIDTH: int = 120
HEADER: int = 1
TOP_SEPERATOR: int = HEADER + 1
FIRST_LINE: int = TOP_SEPERATOR + 1
FOOTER: int = HEIGHT - 1
BOTTOM_SEPERATOR: int = FOOTER - 1
LAST_LINE: int = BOTTOM_SEPERATOR - 1
WRITEABLE = LAST_LINE - FIRST_LINE


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
    TICK: float = 0.15
    DOTS = cycle(
        [
            "...",
            " ..",
            "  .",
            ".  ",
            ".. ",
        ]
    )
    while True:
        await event.wait()
        end = time.time() + timeout
        async with BleakScanner() as scanner:
            while time.time() < end:
                s = f"Scanning{next(DOTS)}"
                write(1, FOOTER, f"{s:{WIDTH}}")
                flush()
                await asyncio.sleep(TICK)
            await queue.put(scanner.discovered_devices_and_advertisement_data)
            write(1, FOOTER, f"{'Scanning Finished':{WIDTH}}")
            flush()
            event.clear()


def truncate(s: str | None, length: int) -> str:
    if s is None:
        s = "<UNKNOWN>"
    if len(s) >= length:
        s = s[: length - 4] + "..."
    return s


def update_scan_result(devices_and_data: ValuesView[tuple[BLEDevice, AdvertisementData]], current_idx: int) -> int:
    n_devices = len(devices_and_data)
    last_idx = n_devices - 1
    if current_idx < 0:
        current_idx = 0
    if current_idx > last_idx:
        current_idx = last_idx

    NAME_LEN: int = 20
    ADDR_LEN: int = 20
    RSSI_LEN: int = 6
    LOCAL_LEN: int = 20
    BLANK: str = " "

    header = f"{'Name':{NAME_LEN}}{'Address':{ADDR_LEN}}{
        'RSSI':^{RSSI_LEN}}{'Local Name':{LOCAL_LEN}}"
    write(1, FIRST_LINE, header)

    # NOTE: Try putting the current idex in the middle of the writeable
    #       area.  Calculate the theoretic start, clamping it to 0.
    #       Calculate the theoretic end, clamping it to the writeable
    #       area.
    start_idx = current_idx - WRITEABLE // 2
    if start_idx < 0:
        start_idx = 0
    end_idx = start_idx + last_idx
    if end_idx >= WRITEABLE:
        end_idx = start_idx + WRITEABLE
    line_no = 0
    for x, (dev, data) in enumerate(devices_and_data):
        if x < end_idx and x >= start_idx:
            line_no += 1
            name = truncate(dev.name, NAME_LEN)
            local_name = truncate(data.local_name, LOCAL_LEN)
            dev_addr = truncate(dev.address, ADDR_LEN)
            rssi = truncate(str(data.rssi), RSSI_LEN)
            s = f"{name:{NAME_LEN}}{dev_addr:{ADDR_LEN}}{
                rssi:^{RSSI_LEN}}{local_name:{LOCAL_LEN}}"
            if x == current_idx:
                highlight(1, FIRST_LINE + line_no, s)
            else:
                write(1, FIRST_LINE + line_no, s)
        else:
            continue
    # NOTE: blank out any lines that weren't written to, to clear
    #       previous writes.
    for blank in range(line_no + 1, WRITEABLE + 1):
        write(1, FIRST_LINE + blank, f"{BLANK:{WIDTH}}")
    # NOTE: Indicate that there are devices not being written.
    if end_idx <= last_idx:
        write(1, LAST_LINE, f"{'---MORE---':{WIDTH}}")
    flush()
    return current_idx


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
    scan_queue: asyncio.Queue[dict[str, tuple[BLEDevice, AdvertisementData]]] = asyncio.Queue()
    key_queue = asyncio.Queue()
    asyncio.create_task(scan(5.0, scan_event, scan_queue), name="scan task")
    asyncio.create_task(get_key(key_queue), name="keyboard task")

    # Main loop
    key = ""
    current_idx: int = 0
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
                    current_idx -= 1
                    current_idx = update_scan_result(devices_and_data, current_idx)
            case Keys.PG_UP:
                if devices_and_data:
                    current_idx -= 10
                    current_idx = update_scan_result(devices_and_data, current_idx)

            case Keys.DOWN:
                if devices_and_data:
                    current_idx += 1
                    current_idx = update_scan_result(devices_and_data, current_idx)
            case Keys.PG_DOWN:
                if devices_and_data:
                    current_idx += 10
                    current_idx = update_scan_result(devices_and_data, current_idx)

        # Handle scan results
        if not scan_queue.empty():
            scan_results = await scan_queue.get()
            devices_and_data = scan_results.values()
            current_idx = 0
            update_scan_result(devices_and_data, current_idx)
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

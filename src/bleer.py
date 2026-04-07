import asyncio
import msvcrt
import sys
import time

from bleak import BleakClient
from bleak import BleakScanner
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData
from enum import auto, Enum
from itertools import cycle
from typing import ValuesView

from ansi_commands import flush, clear, home, move_cursor, hide_cursor, highlight, show_cursor, reset_color, write
from keymap import Keys

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


class ScanData:
    # Note: couldn't get a dataclass working for this.
    # mutable default data needs a default_factory and things got annoying.
    __slots__ = "current_idx", "devices_and_data"

    def __init__(self):
        self.current_idx: int = 0
        self.devices_and_data: ValuesView[tuple[BLEDevice, AdvertisementData]] = {}.values()


class ConnData:
    __slots__ = "device_and_data", "client", "current_idx"

    def __init__(self):
        self.device_and_data: tuple[BLEDevice, AdvertisementData] = (None, None)
        self.client: BleakClient | None = None
        self.current_idx: int = 0


class Mode(Enum):
    SCAN = auto()
    CONN = auto()


class State:
    __slots__ = "mode", "scan", "conn"

    def __init__(self):
        self.mode: Mode = Mode(Mode.SCAN)
        self.scan: ScanData = ScanData()
        self.conn: ConnData = ConnData()


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
    if not isinstance(s, str):
        s = str(s)
    if len(s) >= length:
        s = s[: length - 4] + "..."
    return s


def update_scan_result(scan: ScanData) -> int:
    n_devices = len(scan.devices_and_data)
    last_idx = n_devices - 1
    if scan.current_idx < 0:
        scan.current_idx = 0
    if scan.current_idx > last_idx:
        scan.current_idx = last_idx

    NAME_LEN: int = 20
    ADDR_LEN: int = 20
    RSSI_LEN: int = 6
    LOCAL_LEN: int = 20
    BLANK_LEN: int = WIDTH - NAME_LEN - ADDR_LEN - RSSI_LEN - LOCAL_LEN
    BLANK: str = " "

    header = (
        f"{'Name':{NAME_LEN}}{'Address':{ADDR_LEN}}{'RSSI':^{RSSI_LEN}}{'Local Name':{LOCAL_LEN}}{BLANK:{BLANK_LEN}}"
    )
    write(1, FIRST_LINE, header)

    # NOTE: Try putting the current idex in the middle of the writeable
    #       area.  Calculate the theoretic start, clamping it to 0.
    #       Calculate the theoretic end, clamping it to the writeable
    #       area.
    start_idx = scan.current_idx - WRITEABLE // 2
    if start_idx < 0:
        start_idx = 0
    end_idx = start_idx + last_idx
    if end_idx >= WRITEABLE:
        end_idx = start_idx + WRITEABLE
    line_no = 0
    for x, (dev, data) in enumerate(scan.devices_and_data):
        if x < end_idx and x >= start_idx:
            line_no += 1
            name = truncate(dev.name, NAME_LEN)
            local_name = truncate(data.local_name, LOCAL_LEN)
            dev_addr = truncate(dev.address, ADDR_LEN)
            rssi = truncate(str(data.rssi), RSSI_LEN)
            s = f"{name:{NAME_LEN}}{dev_addr:{ADDR_LEN}}{rssi:^{RSSI_LEN}}{local_name:{LOCAL_LEN}}{BLANK:{BLANK_LEN}}"
            if x == scan.current_idx:
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
    return scan.current_idx


def update_conn_data(conn: ConnData) -> int:
    conn_data = [
        ("Name", conn.client.name),
        ("Address", conn.client.address),
        ("MTU Size", conn.client.mtu_size),
    ]

    for x, service in enumerate(conn.client.services):
        conn_data.append((f"Service {x:2}", service))
        for char in service.characteristics:
            conn_data.append((f" Characteristic", char.uuid))
            conn_data.append((f" Properties", char.properties))
            conn_data.append((f" Handle", char.handle))

    n_items = len(conn_data)
    last_idx = n_items - 1
    if conn.current_idx < 0:
        conn.current_idx = 0
    if conn.current_idx > last_idx:
        conn.current_idx = last_idx

    FIELD_LEN: int = 20
    DATA_LEN: int = WIDTH - FIELD_LEN
    BLANK: str = " "

    header = f"{'Field':{FIELD_LEN}}{'DATA':{DATA_LEN}}"
    write(1, FIRST_LINE, header)

    # NOTE: Try putting the current idex in the middle of the writeable
    #       area.  Calculate the theoretic start, clamping it to 0.
    #       Calculate the theoretic end, clamping it to the writeable
    #       area.
    start_idx = conn.current_idx - WRITEABLE // 2
    if start_idx < 0:
        start_idx = 0
    end_idx = start_idx + last_idx
    if end_idx >= WRITEABLE:
        end_idx = start_idx + WRITEABLE
    line_no = 0

    for x, (field, data) in enumerate(conn_data):
        if x < end_idx and x >= start_idx:
            line_no += 1
            f_string = truncate(field, DATA_LEN)
            d_string = truncate(data, DATA_LEN)
            s = f"{f_string:{FIELD_LEN}}{d_string:{DATA_LEN}}"
            if x == conn.current_idx:
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
    return conn.current_idx


async def bleer(state: State):
    # Setup the terminal
    hide_cursor()
    clear()
    home()
    write(1, HEADER, f"{'(Q)uit (S)can (D)isconnect':{WIDTH}}")
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
    while key != Keys.Q:
        if not key_queue.empty():
            key = await key_queue.get()
        else:
            key = ""
        match state.mode:
            case Mode.SCAN:
                match key:
                    case Keys.S:
                        if scan_event.is_set():
                            write(1, FOOTER, f"{'Scan already in process':{WIDTH}}")
                        else:
                            scan_event.set()
                            write(1, FOOTER, f"{'Starting scan...':{WIDTH}}")
                        flush()
                    case Keys.UP:
                        if state.scan.devices_and_data:
                            state.scan.current_idx -= 1
                            state.scan.current_idx = update_scan_result(state.scan)
                    case Keys.PG_UP:
                        if state.scan.devices_and_data:
                            state.scan.current_idx -= 10
                            state.scan.current_idx = update_scan_result(state.scan)
                    case Keys.DOWN:
                        if state.scan.devices_and_data:
                            state.scan.current_idx += 1
                            state.scan.current_idx = update_scan_result(state.scan)
                    case Keys.PG_DOWN:
                        if state.scan.devices_and_data:
                            state.scan.current_idx += 10
                            state.scan.current_idx = update_scan_result(state.scan)
                    case Keys.ENTER:
                        state.conn.device_and_data = state.scan.devices_and_data[state.scan.current_idx]
                        write(1, FOOTER, f"{f'Connecting to {state.conn.device_and_data[0].address}':{WIDTH}}")
                        flush()
                        state.conn.client = BleakClient(state.conn.device_and_data[0])
                        await state.conn.client.connect()
                        write(1, FOOTER, f"{'Connected':{WIDTH}}")
                        flush()
                        state.mode = Mode.CONN
                        state.conn.current_idx = update_conn_data(state.conn)

                # Handle scan results
                if not scan_queue.empty():
                    scan_results = await scan_queue.get()
                    state.scan.devices_and_data = scan_results.values()
                    state.scan.devices_and_data = sorted(
                        state.scan.devices_and_data, key=lambda x: x[1].rssi, reverse=True
                    )
                    current_idx = 0
                    update_scan_result(state.scan)

            case Mode.CONN:
                match key:
                    case Keys.D:
                        write(1, FOOTER, f"{f'Disconnecting from {state.conn.client.address}':{WIDTH}}")
                        flush()
                        await state.conn.client.disconnect()
                        write(1, FOOTER, f"{'Disconnected':{WIDTH}}")
                        flush()
                        state.scan.current_idx = update_scan_result(state.scan)
                        state.mode = Mode.SCAN
                    case Keys.UP:
                        state.conn.current_idx -= 1
                        state.conn.current_idx = update_conn_data(state.conn)
                    case Keys.PG_UP:
                        state.conn.current_idx -= 10
                        state.conn.current_idx = update_conn_data(state.conn)
                    case Keys.DOWN:
                        state.conn.current_idx += 1
                        state.conn.current_idx = update_conn_data(state.conn)
                    case Keys.PG_DOWN:
                        state.conn.current_idx += 10
                        state.conn.current_idx = update_conn_data(state.conn)

        await asyncio.sleep(0.01)

    # Clean up on quit
    write(1, FOOTER, f"{'Quitting...':{WIDTH}}")
    flush()
    if state.conn.client.is_connected:
        await state.conn.client.disconnect()
    for task in asyncio.all_tasks():
        if not (task == main_task):
            task.cancel()
    reset_color()
    move_cursor(1, HEIGHT)
    show_cursor()
    return OK


async def main():
    state = State()
    # NOTE: since we aren't using a context manager for the client we don't
    # get it automatically cleaned up.  This seemed like the cleanest way
    # of guarenteeing that we are going to be able close the connection.
    try:
        await bleer(state)
    except Exception as e:
        if state.conn.client is not None:
            if state.conn.client.is_connected:
                await state.conn.client.disconnect()
        raise e


if __name__ == "__main__":
    asyncio.run(main())
    sys.exit(OK)

import sys

from dataclasses import dataclass

# ANSI escape keys
BGBLACK = "\x1b[40m"
BGRED = "\x1b[41m"
BGGREEN = "\x1b[42m"
BGYELLOW = "\x1b[43m"
BGBLUE = "\x1b[44m"
BGPURPLE = "\x1b[45m"
BGCYAN = "\x1b[46m"
BGWHITE = "\x1b[47m"

BLACK = "\x1b[30m"
RED = "\x1b[31m"
GREEN = "\x1b[32m"
YELLOW = "\x1b[33m"
BLUE = "\x1b[34m"
PURPLE = "\x1b[35m"
CYAN = "\x1b[36m"
WHITE = "\x1b[37m"


@dataclass(slots=True)
class Keys():
    A = "a"
    B = "b"
    C = "c"
    D = "d"
    E = "e"
    F = "f"
    G = "g"
    H = "h"
    I = "i"
    J = "j"
    K = "k"
    L = "l"
    M = "m"
    N = "n"
    O = "o"
    P = "p"
    Q = "q"
    R = "r"
    S = "s"
    T = "t"
    U = "u"
    V = "v"
    W = "w"
    X = "x"
    Y = "y"
    Z = "z"
    SPECIAL1 = b'\xc3\xa0'.decode()
    SPECIAL2 = b'\x00'.decode()
    LEFT = SPECIAL1 + "K"
    DOWN = SPECIAL1 + "P"
    RIGHT = SPECIAL1 + "M"
    UP = SPECIAL1 + "H"
    INSERT = SPECIAL1 + "R"
    HOME = SPECIAL1 + "G"
    DEL = SPECIAL1 + "S"
    END = SPECIAL1 + "O"
    PG_UP = SPECIAL1 + "I"
    PG_DOWN = SPECIAL1 + "Q"
    F1 = SPECIAL2 + ";"
    F2 = SPECIAL2 + "<"
    F3 = SPECIAL2 + "="
    F4 = SPECIAL2 + ">"
    F5 = SPECIAL2 + "?"
    F6 = SPECIAL2 + "@"
    F7 = SPECIAL2 + "A"
    F8 = SPECIAL2 + "B"
    F9 = SPECIAL2 + "C"
    F10 = SPECIAL2 + "D"
    # F11 doesn't get captured.
    F12 = SPECIAL1 + b"\xc2\x86".decode()


def flush():
    sys.stdout.flush()


def clear():
    sys.stdout.write("\x1b[2J")


def home():
    sys.stdout.write("\x1b[H")


def move_cursor(x, y):
    sys.stdout.write(f"\x1b[{y};{x}H")


def hide_cursor():
    sys.stdout.write("\x1b[?25l")


def show_cursor():
    sys.stdout.write("\x1b[?25h")


def write(x, y, s):
    move_cursor(x, y)
    sys.stdout.write(s)


def write_color(x, y, s, color):
    move_cursor(x, y)
    sys.stdout.write(f"{color}{s}")
    reset_color()


def write_colors(x, y, s, color, bgcolor):
    move_cursor(x, y)
    sys.stdout.write(f"{color}{bgcolor}{s}")
    reset_color()


def highlight(x, y, s):
    move_cursor(x, y)
    sys.stdout.write(f"{BLACK}{BGWHITE}{s}")
    reset_color()


def reset_color():
    sys.stdout.write("\x1b[0m")


def box(x, y, w, h):
    sys.stdout.write(f"\x1b[{y};{x}H")
    sys.stdout.write(" " + "-" * (w-2) + " ")
    PAD = " "
    for i in range(y+1, y+h):
        sys.stdout.write(f"\x1b[{i};{y}H")
        sys.stdout.write(f"|{PAD*(w-2)}|")
    sys.stdout.write(f"\x1b[{y+h};{x}H")
    sys.stdout.write(" " + "-" * (w-2) + " ")


def box2(x, y, w, h):
    sys.stdout.write(f"\x1b[{y};{x}H")
    sys.stdout.write("-"*w)
    PAD = " "
    for i in range(y+1, y+h):
        sys.stdout.write(f"\x1b[{i};{y}H")
        sys.stdout.write(f"|{PAD*(w-2)}|")
    sys.stdout.write(f"\x1b[{y+h};{x}H")
    sys.stdout.write("-"*w)

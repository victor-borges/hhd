import logging
import select
from typing import Mapping, Sequence, TypeVar, cast

import evdev

from hhd.controller import Axis, Button, Event, Producer
from hhd.controller.lib.common import hexify

from ..const import AbsAxis, GamepadButton, KeyboardButton

logger = logging.getLogger(__name__)


def B(b: str):
    return cast(int, getattr(evdev.ecodes, b))


A = TypeVar("A")


def to_map(b: dict[A, Sequence[int]]) -> dict[int, A]:
    out = {}
    for btn, seq in b.items():
        for s in seq:
            out[s] = btn
    return out


XBOX_BUTTON_MAP: dict[int, GamepadButton] = to_map(
    {
        # Gamepad
        "a": [B("BTN_A")],
        "b": [B("BTN_B")],
        "x": [B("BTN_X")],
        "y": [B("BTN_Y")],
        # Sticks
        "ls": [B("BTN_THUMBL")],
        "rs": [B("BTN_THUMBR")],
        # Bumpers
        "lb": [B("BTN_TL")],
        "rb": [B("BTN_TR")],
        # Select
        "start": [B("BTN_START")],
        "select": [B("BTN_SELECT")],
        # Misc
        "mode": [B("BTN_MODE")],
    }
)

XBOX_AXIS_MAP: dict[int, AbsAxis] = to_map(
    {
        # Sticks
        # Values should range from -1 to 1
        "ls_x": [B("ABS_X")],
        "ls_y": [B("ABS_Y")],
        "rs_x": [B("ABS_RX")],
        "rs_y": [B("ABS_RY")],
        # Triggers
        # Values should range from -1 to 1
        "rt": [B("ABS_Z")],
        "lt": [B("ABS_RZ")],
        # Hat, implemented as axis. Either -1, 0, or 1
        "hat_x": [B("ABS_HAT0X")],
        "hat_y": [B("ABS_HAT0Y")],
    }
)


class GenericGamepadEvdev(Producer):
    def __init__(
        self,
        vid: Sequence[int],
        pid: Sequence[int],
        name: Sequence[str],
        btn_map: Mapping[int, Button] = XBOX_BUTTON_MAP,
        axis_map: Mapping[int, Axis] = XBOX_AXIS_MAP,
        aspect_ratio: float | None = None,
    ) -> None:
        self.vid = vid
        self.pid = pid
        self.name = name

        self.btn_map = btn_map
        self.axis_map = axis_map
        self.aspect_ratio = aspect_ratio

        self.dev: evdev.InputDevice | None = None
        self.fd = 0

    def open(self) -> Sequence[int]:
        for d in evdev.list_devices():
            dev = evdev.InputDevice(d)
            if self.vid and dev.info.vendor not in self.vid:
                continue
            if self.pid and dev.info.product not in self.pid:
                continue
            if self.name and dev.name not in self.name:
                continue
            self.dev = dev
            self.dev.grab()
            self.ranges = {
                a: (i.min, i.max) for a, i in self.dev.capabilities().get(B("EV_ABS"), [])  # type: ignore
            }
            self.fd = dev.fd
            self.started = True
            return [self.fd]

        err = f"Device with the following not found:\n"
        if self.vid:
            err += f"Vendor ID: {hexify(self.vid)}\n"
        if self.pid:
            err += f"Product ID: {hexify(self.pid)}\n"
        if self.name:
            err += f"Name: {self.name}\n"
        logger.error(err)
        return []

    def close(self, exit: bool) -> bool:
        if self.dev:
            self.dev.close()
            self.fd = 0
        return True

    def produce(self, fds: Sequence[int]) -> Sequence[Event]:
        if not self.dev or not self.fd in fds:
            return []

        out: list[Event] = []
        if self.started and self.aspect_ratio is not None:
            self.started = False
            out.append(
                {
                    "type": "configuration",
                    "code": "touchpad_aspect_ratio",
                    "value": self.aspect_ratio,
                }
            )

        while select.select([self.fd], [], [], 0)[0]:
            for e in self.dev.read():
                if e.type == B("EV_KEY"):
                    if e.code in self.btn_map:
                        out.append(
                            {
                                "type": "button",
                                "code": self.btn_map[e.code],
                                "value": bool(e.value),
                            }
                        )
                elif e.type == B("EV_ABS"):
                    if e.code in self.axis_map:
                        # Normalize
                        val = e.value / abs(
                            self.ranges[e.code][1 if e.value >= 0 else 0]
                        )

                        out.append(
                            {
                                "type": "axis",
                                "code": self.axis_map[e.code],
                                "value": val,
                            }
                        )
        return out


KEYBOARD_MAP: dict[int, KeyboardButton] = to_map(
    {
        "key_esc": [B("KEY_ESC")],  # 1
        "key_enter": [B("KEY_ENTER")],  # 28
        "key_leftctrl": [B("KEY_LEFTCTRL")],  # 29
        "key_leftshift": [B("KEY_LEFTSHIFT")],  # 42
        "key_leftalt": [B("KEY_LEFTALT")],  # 56
        "key_rightctrl": [B("KEY_RIGHTCTRL")],  # 97
        "key_rightshift": [B("KEY_RIGHTSHIFT")],  # 54
        "key_rightalt": [B("KEY_RIGHTALT")],  # 100
        "key_leftmeta": [B("KEY_LEFTMETA")],  # 125
        "key_rightmeta": [B("KEY_RIGHTMETA")],  # 126
        "key_capslock": [B("KEY_CAPSLOCK")],  # 58
        "key_numlock": [B("KEY_NUMLOCK")],  # 69
        "key_scrolllock": [B("KEY_SCROLLLOCK")],  # 70
        "key_sysrq": [B("KEY_SYSRQ")],  # 99
        "key_minus": [B("KEY_MINUS")],  # 12
        "key_equal": [B("KEY_EQUAL")],  # 13
        "key_backspace": [B("KEY_BACKSPACE")],  # 14
        "key_tab": [B("KEY_TAB")],  # 15
        "key_leftbrace": [B("KEY_LEFTBRACE")],  # 26
        "key_rightbrace": [B("KEY_RIGHTBRACE")],  # 27
        "key_space": [B("KEY_SPACE")],  # 57
        "key_up": [B("KEY_UP")],  # 103
        "key_left": [B("KEY_LEFT")],  # 105
        "key_right": [B("KEY_RIGHT")],  # 106
        "key_down": [B("KEY_DOWN")],  # 108
        "key_home": [B("KEY_HOME")],  # 102
        "key_end": [B("KEY_END")],  # 107
        "key_pageup": [B("KEY_PAGEUP")],  # 104
        "key_pagedown": [B("KEY_PAGEDOWN")],  # 109
        "key_insert": [B("KEY_INSERT")],  # 110
        "key_delete": [B("KEY_DELETE")],  # 111
        "key_semicolon": [B("KEY_SEMICOLON")],  # 39
        "key_apostrophe": [B("KEY_APOSTROPHE")],  # 40
        "key_grave": [B("KEY_GRAVE")],  # 41
        "key_backslash": [B("KEY_BACKSLASH")],  # 43
        "key_comma": [B("KEY_COMMA")],  # 51
        "key_dot": [B("KEY_DOT")],  # 52
        "key_slash": [B("KEY_SLASH")],  # 53
        "key_102nd": [B("KEY_102ND")],  # 86
        "key_ro": [B("KEY_RO")],  # 89
        "key_power": [B("KEY_POWER")],  # 116
        "key_compose": [B("KEY_COMPOSE")],  # 127
        "key_stop": [B("KEY_STOP")],  # 128
        "key_again": [B("KEY_AGAIN")],  # 129
        "key_props": [B("KEY_PROPS")],  # 130
        "key_undo": [B("KEY_UNDO")],  # 131
        "key_front": [B("KEY_FRONT")],  # 132
        "key_copy": [B("KEY_COPY")],  # 133
        "key_open": [B("KEY_OPEN")],  # 134
        "key_paste": [B("KEY_PASTE")],  # 135
        "key_cut": [B("KEY_CUT")],  # 137
        "key_find": [B("KEY_FIND")],  # 136
        "key_help": [B("KEY_HELP")],  # 138
        "key_calc": [B("KEY_CALC")],  # 140
        "key_sleep": [B("KEY_SLEEP")],  # 142
        "key_www": [B("KEY_WWW")],  # 150
        "key_screenlock": [B("KEY_SCREENLOCK")],  # 152
        "key_back": [B("KEY_BACK")],  # 158
        "key_refresh": [B("KEY_REFRESH")],  # 173
        "key_edit": [B("KEY_EDIT")],  # 176
        "key_scrollup": [B("KEY_SCROLLUP")],  # 177
        "key_scrolldown": [B("KEY_SCROLLDOWN")],  # 178
        "key_1": [B("KEY_1")],  # 2
        "key_2": [B("KEY_2")],  # 3
        "key_3": [B("KEY_3")],  # 4
        "key_4": [B("KEY_4")],  # 5
        "key_5": [B("KEY_5")],  # 6
        "key_6": [B("KEY_6")],  # 7
        "key_7": [B("KEY_7")],  # 8
        "key_8": [B("KEY_8")],  # 9
        "key_9": [B("KEY_9")],  # 10
        "key_0": [B("KEY_0")],  # 11
        "key_a": [B("KEY_A")],  # 30
        "key_b": [B("KEY_B")],  # 48
        "key_c": [B("KEY_C")],  # 46
        "key_d": [B("KEY_D")],  # 32
        "key_e": [B("KEY_E")],  # 18
        "key_f": [B("KEY_F")],  # 33
        "key_g": [B("KEY_G")],  # 34
        "key_h": [B("KEY_H")],  # 35
        "key_i": [B("KEY_I")],  # 23
        "key_j": [B("KEY_J")],  # 36
        "key_k": [B("KEY_K")],  # 37
        "key_l": [B("KEY_L")],  # 38
        "key_m": [B("KEY_M")],  # 50
        "key_n": [B("KEY_N")],  # 49
        "key_o": [B("KEY_O")],  # 24
        "key_p": [B("KEY_P")],  # 25
        "key_q": [B("KEY_Q")],  # 16
        "key_r": [B("KEY_R")],  # 19
        "key_s": [B("KEY_S")],  # 31
        "key_t": [B("KEY_T")],  # 20
        "key_u": [B("KEY_U")],  # 22
        "key_v": [B("KEY_V")],  # 47
        "key_w": [B("KEY_W")],  # 17
        "key_x": [B("KEY_X")],  # 45
        "key_y": [B("KEY_Y")],  # 21
        "key_z": [B("KEY_Z")],  # 44
        "key_kpasterisk": [B("KEY_KPASTERISK")],  # 55
        "key_kpminus": [B("KEY_KPMINUS")],  # 74
        "key_kpplus": [B("KEY_KPPLUS")],  # 78
        "key_kpdot": [B("KEY_KPDOT")],  # 83
        "key_kpjpcomma": [B("KEY_KPJPCOMMA")],  # 95
        "key_kpenter": [B("KEY_KPENTER")],  # 96
        "key_kpslash": [B("KEY_KPSLASH")],  # 98
        "key_kpequal": [B("KEY_KPEQUAL")],  # 117
        "key_kpcomma": [B("KEY_KPCOMMA")],  # 121
        "key_kpleftparen": [B("KEY_KPLEFTPAREN")],  # 179
        "key_kprightparen": [B("KEY_KPRIGHTPAREN")],  # 180
        "key_kp0": [B("KEY_KP0")],  # 82
        "key_kp1": [B("KEY_KP1")],  # 79
        "key_kp2": [B("KEY_KP2")],  # 80
        "key_kp3": [B("KEY_KP3")],  # 81
        "key_kp4": [B("KEY_KP4")],  # 75
        "key_kp5": [B("KEY_KP5")],  # 76
        "key_kp6": [B("KEY_KP6")],  # 77
        "key_kp7": [B("KEY_KP7")],  # 71
        "key_kp8": [B("KEY_KP8")],  # 72
        "key_kp9": [B("KEY_KP9")],  # 73
        "key_f1": [B("KEY_F1")],  # 59
        "key_f2": [B("KEY_F2")],  # 60
        "key_f3": [B("KEY_F3")],  # 61
        "key_f4": [B("KEY_F4")],  # 62
        "key_f5": [B("KEY_F5")],  # 63
        "key_f6": [B("KEY_F6")],  # 64
        "key_f7": [B("KEY_F7")],  # 65
        "key_f8": [B("KEY_F8")],  # 66
        "key_f9": [B("KEY_F9")],  # 67
        "key_f11": [B("KEY_F11")],  # 87
        "key_f12": [B("KEY_F12")],  # 88
        "key_f10": [B("KEY_F10")],  # 68
        "key_f13": [B("KEY_F13")],  # 183
        "key_f14": [B("KEY_F14")],  # 184
        "key_f15": [B("KEY_F15")],  # 185
        "key_f16": [B("KEY_F16")],  # 186
        "key_f17": [B("KEY_F17")],  # 187
        "key_f18": [B("KEY_F18")],  # 188
        "key_f19": [B("KEY_F19")],  # 189
        "key_f20": [B("KEY_F20")],  # 190
        "key_f21": [B("KEY_F21")],  # 191
        "key_f22": [B("KEY_F22")],  # 192
        "key_f23": [B("KEY_F23")],  # 193
        "key_f24": [B("KEY_F24")],  # 194
        "key_playpause": [B("KEY_PLAYPAUSE")],  # 164
        "key_pause": [B("KEY_PAUSE")],  # 119
        "key_mute": [B("KEY_MUTE")],  # 113
        "key_stopcd": [B("KEY_STOPCD")],  # 166
        "key_forward": [B("KEY_FORWARD")],  # 159
        "key_ejectcd": [B("KEY_EJECTCD")],  # 161
        "key_nextsong": [B("KEY_NEXTSONG")],  # 163
        "key_previoussong": [B("KEY_PREVIOUSSONG")],  # 165
        "key_volumedown": [B("KEY_VOLUMEDOWN")],  # 114
        "key_volumeup": [B("KEY_VOLUMEUP")],  # 115
        "key_katakana": [B("KEY_KATAKANA")],  # 90
        "key_hiragana": [B("KEY_HIRAGANA")],  # 91
        "key_henkan": [B("KEY_HENKAN")],  # 92
        "key_katakanahiragana": [B("KEY_KATAKANAHIRAGANA")],  # 93
        "key_muhenkan": [B("KEY_MUHENKAN")],  # 94
        "key_zenkakuhankaku": [B("KEY_ZENKAKUHANKAKU")],  # 85
        "key_hanguel": [B("KEY_HANGUEL")],  # 122
        "key_hanja": [B("KEY_HANJA")],  # 123
        "key_yen": [B("KEY_YEN")],  # 124
        "key_unknown": [B("KEY_UNKNOWN")],  # 240,
    }
)

__all__ = ["GenericGamepadEvdev", "XBOX_BUTTON_MAP", "XBOX_AXIS_MAP", "B", "to_map"]
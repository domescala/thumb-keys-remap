"""Keys, profiles and conversion to the PowerToys Keyboard Manager format."""
import json
import os
from pathlib import Path

TAB, CAPS_LOCK, ESCAPE = 9, 20, 27
WIN, WIN_RIGHT = 91, 92
SHIFT, SHIFT_RIGHT = 160, 161
CTRL, CTRL_RIGHT = 162, 163
ALT, ALT_RIGHT = 164, 165
DISABLED = 256  # special Keyboard Manager target

# Standard mode: what the first, second and third key before the space bar become.
TARGETS = (WIN, ALT, CTRL)
EXPECTED = (CTRL, WIN, ALT)

# Keys whose name is translated: virtual key code -> text identifier in the locale files.
KEY_IDS = {
    CTRL: "ctrl_left", WIN: "win_left", ALT: "alt_left", CTRL_RIGHT: "ctrl_right", WIN_RIGHT: "win_right",
    ALT_RIGHT: "alt_right", SHIFT: "shift_left", SHIFT_RIGHT: "shift_right", CAPS_LOCK: "caps_lock",
    TAB: "tab", ESCAPE: "escape", 32: "space", 13: "enter", 8: "backspace", 46: "delete", 45: "insert",
    36: "home", 35: "end", 33: "page_up", 34: "page_down", 37: "arrow_left", 38: "arrow_up",
    39: "arrow_right", 40: "arrow_down", 93: "menu", 44: "print_screen", 145: "scroll_lock", 19: "pause",
    144: "num_lock", 173: "mute", 174: "volume_down", 175: "volume_up", 176: "next_track",
    177: "previous_track", 178: "stop", 179: "play_pause", DISABLED: "disabled",
}
# Keys whose name is the same in every language.
FIXED_NAMES = {
    **{vk: chr(vk) for vk in range(ord("A"), ord("Z") + 1)},
    **{vk: chr(vk) for vk in range(ord("0"), ord("9") + 1)},
    **{111 + n: f"F{n}" for n in range(1, 25)},
    **{96 + n: f"Num {n}" for n in range(10)},
    106: "Num *", 107: "Num +", 109: "Num -", 110: "Num .", 111: "Num /",
}
# Symbol keys: their character depends on the Windows keyboard layout.
SYMBOL_KEYS = (220, 219, 221, 186, 187, 192, 222, 191, 226, 188, 190, 189)

# Order of the drop-down lists: the most frequently remapped keys come first.
KEY_LIST = [vk for vk in KEY_IDS if vk != DISABLED] + list(FIXED_NAMES) + list(SYMBOL_KEYS)


def standard_rows(keys):
    if len(keys) != 3:
        return []
    return [[source, target] for source, target in zip(keys, TARGETS) if source != target]


def rows_of(config):
    """The [source, target] pairs of a profile."""
    if config["mode"] == "standard":
        return standard_rows(config["keys"])
    return config["rows"]


def rows_error(rows):
    """Why Keyboard Manager would reject the rows, as (text key, virtual key), or None."""
    sources = set()
    for source, target in rows:
        if source is None or target is None:
            return "error.empty_rows", None
        if source == target:
            return "error.same_key", source
        if source in sources:
            return "error.duplicate_source", source
        sources.add(source)
    return None


def altgr_status(config, altgr_keys):
    """None if the profile does not touch AltGr, True if it keeps working, False if it breaks.

    Windows sends AltGr as left Ctrl + right Alt, so remapping left Ctrl affects it.
    The rules that restore it can only be written when left Ctrl becomes a Windows key.
    """
    conversions = dict(rows_of(config))
    new_ctrl = conversions.get(CTRL)
    if not altgr_keys or new_ctrl in (None, CTRL) or ALT_RIGHT in conversions:
        return None
    return new_ctrl in (WIN, WIN_RIGHT)


def _shortcut(source, target):
    return {"originalKeys": ";".join(map(str, source)), "newRemapKeys": ";".join(map(str, target)),
            "operationType": 0, "exactMatch": False}


def altgr_rules(config, altgr_keys):
    """For every AltGr character: "Windows + AltGr + key" becomes "Ctrl + AltGr + key" again."""
    if not altgr_status(config, altgr_keys):
        return []
    new_ctrl = dict(rows_of(config))[CTRL]
    rules = []
    for vk, needs_shift in altgr_keys:
        for shift in ([SHIFT], [SHIFT_RIGHT]) if needs_shift else ([],):
            rules.append(_shortcut([new_ctrl, *shift, ALT_RIGHT, vk], [CTRL, *shift, ALT_RIGHT, vk]))
    return rules


def build_keymap(config, altgr_keys=()):
    """`altgr_keys`: (key, needs Shift) pairs that type a character together with AltGr."""
    shortcuts = altgr_rules(config, altgr_keys)
    if config["ctrl_tab"]:
        shortcuts.append(_shortcut([CTRL, TAB], [ALT, TAB]))
    return {
        "remapKeys": {"inProcess": [{"originalKeys": str(s), "newRemapKeys": str(t)} for s, t in rows_of(config)]},
        "remapKeysToText": {"inProcess": []},
        "remapShortcuts": {"global": shortcuts, "appSpecific": []},
        "remapShortcutsToText": {"global": [], "appSpecific": []},
    }


def signature(keymap):
    """Fingerprint of a mapping, independent of order and formatting."""
    def pairs(section, name):
        entries = (keymap.get(section) or {}).get(name) or []
        return tuple(sorted(f"{e.get('originalKeys')}>{e.get('newRemapKeys', e.get('unicodeText'))}"
                            for e in entries))

    return tuple(pairs(s, n) for s, n in (
        ("remapKeys", "inProcess"), ("remapKeysToText", "inProcess"),
        ("remapShortcuts", "global"), ("remapShortcuts", "appSpecific"),
        ("remapShortcutsToText", "global"), ("remapShortcutsToText", "appSpecific")))


def new_config(name="", keys=(), ctrl_tab=False, builtin=None):
    """A built-in profile has no name of its own: it is translated."""
    return {"builtin": builtin, "name": name, "mode": "standard", "keys": list(keys), "rows": [],
            "ctrl_tab": ctrl_tab}


def default_configs():
    return [new_config(builtin="none"), new_config(builtin="mac", keys=EXPECTED, ctrl_tab=True)]


class ConfigStore:
    """All profiles and settings in a single JSON file next to the program."""

    def __init__(self, file, altgr_keys=()):
        self.file = Path(file)
        self.altgr_keys = list(altgr_keys)
        self.configs = default_configs()
        self.active = None  # index of the last activated profile
        self.language = None
        if self.file.is_file():
            data = json.loads(self.file.read_text(encoding="utf-8-sig"))
            self.configs = [{**new_config(), **c} for c in data["configurations"]]
            self.active = data.get("active")
            self.language = data.get("language")

    def save(self):
        data = {"language": self.language, "active": self.active, "configurations": self.configs}
        temporary = self.file.with_name(self.file.name + ".tmp")
        temporary.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        os.replace(temporary, self.file)

    def find_active(self, current_signature):
        """Index of the profile matching what PowerToys is using, or None."""
        indexes = list(range(len(self.configs)))
        if self.active in indexes:
            indexes.insert(0, self.active)
        return next((i for i in indexes
                     if signature(build_keymap(self.configs[i], self.altgr_keys)) == current_signature), None)

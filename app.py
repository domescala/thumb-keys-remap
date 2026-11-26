"""Mac-style keyboard on Windows, using PowerToys.  Run:  python app.py"""
import ctypes
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import font, messagebox, simpledialog, ttk

if sys.platform != "win32":
    sys.exit("Windows only.")

import i18n  # noqa: E402
import mapping as m  # noqa: E402
import winapi  # noqa: E402

try:
    import widgets as w
except ImportError:
    _t = i18n.Translator(winapi.system_language())
    ctypes.windll.user32.MessageBoxW(None, _t("error.pillow_missing"), _t("app_title"), 0x10)
    sys.exit(1)

CONFIG_FILE = Path(__file__).resolve().parent / "configurations.json"

MODIFIERS = {m.WIN, m.WIN_RIGHT, m.ALT, m.ALT_RIGHT, m.CTRL, m.CTRL_RIGHT, m.SHIFT, m.SHIFT_RIGHT}
TARGET_TEXTS = ("target.windows", "target.alt", "target.ctrl")  # what positions 1, 2 and 3 become


def _row(*keys):
    """A plain item is a key 1 unit wide; a (key, width) pair sets the width."""
    return tuple(k if isinstance(k, tuple) else (k, 1) for k in keys)


def _chars(text):
    return tuple(ord(c) for c in text)


# Full keyboard of the monitor. P0-P2 are the three keys before the space bar.
FULL_KEYBOARD = (
    _row(220, *_chars("1234567890"), 219, 221, (8, 2)),
    _row((9, 1.5), *_chars("QWERTYUIOP"), 186, 187, (13, 1.5)),
    _row((20, 1.75), *_chars("ASDFGHJKL"), 192, 222, 191, (13, 1.25)),
    _row((160, 1.25), 226, *_chars("ZXCVBNM"), 188, 190, 189, (161, 2.75)),
    _row(("P0", 1.25), "FN", ("P1", 1.25), ("P2", 1.25), (32, 5.25), (165, 1.25), (92, 1.25), (93, 1.25),
         (163, 1.25)),
)
# Left side only, used while recording.
LEFT_KEYBOARD = (
    _row((9, 1.5), *_chars("QWERTY")),
    _row((20, 1.75), *_chars("ASDFGH")),
    _row((160, 2.25), *_chars("ZXCVBN")),
    _row(("P0", 1.4), "FN", ("P1", 1.4), ("P2", 1.4), (32, 3.05)),
)


class RecordingDialog(tk.Toplevel):
    """Modal window: the user presses the three keys in order."""

    def __init__(self, app):
        super().__init__(app.root, bg=w.BACKGROUND)
        self.app = app
        self.keys = []
        t = app.t
        self.withdraw()
        self.title(t("recording.window_title"))
        self.resizable(False, False)
        self.transient(app.root)
        self.protocol("WM_DELETE_WINDOW", self.cancel)

        card = w.Card(self, app.scale, padding=16)
        card.pack(fill="both", expand=True, padx=app.px(6), pady=app.px(6))
        body = card.body
        app.label(body, t("recording.title"), 14, bold=True).pack(anchor="w")
        app.label(body, t("recording.subtitle"), color=w.MUTED).pack(anchor="w", pady=(0, app.px(12)))
        unit = app.px(70)
        self.keyboard = w.KeyboardCanvas(body, app.scale, *w.KeyboardCanvas.size(LEFT_KEYBOARD, unit), font_size=9)
        self.keyboard.add_keyboard("left", LEFT_KEYBOARD, unit)
        self.keyboard.pack()
        self.message = app.label(body, "", color=w.ORANGE)
        self.message.pack(anchor="w", pady=app.px(10))

        bar = tk.Frame(body, bg=w.CARD)
        bar.pack(fill="x")
        self.confirm_button = w.Button(bar, app.scale, t("button.confirm"), self.confirm, "primary", "check",
                                       enabled=False)
        self.confirm_button.pack(side="right")
        w.Button(bar, app.scale, t("button.cancel"), self.cancel, icon="cancel").pack(side="right", padx=app.px(6))
        w.Button(bar, app.scale, t("button.restart"), self.restart, icon="restart").pack(side="left")

        self.bind("<Escape>", lambda _e: self.cancel())
        self.bind("<Return>", lambda _e: self.confirm())
        self._draw()
        self.update_idletasks()
        x = app.root.winfo_rootx() + (app.root.winfo_width() - self.winfo_reqwidth()) // 2
        y = app.root.winfo_rooty() + (app.root.winfo_height() - self.winfo_reqheight()) // 3
        self.geometry(f"+{max(0, x)}+{max(0, y)}")
        self.deiconify()
        self.wait_visibility()
        self.grab_set()
        self.focus_force()

    def _draw(self):
        t = self.app.t
        for board, ident in self.keyboard.keys:
            if isinstance(ident, int):
                self.keyboard.set_key(board, ident, self.app.key_label(ident), "off")
            elif ident == "FN":
                self.keyboard.set_key(board, ident, t("recording.fn"), "off")
            else:
                i = int(ident[1])
                text = f"{i + 1}\n{t(TARGET_TEXTS[i])}"
                if i < len(self.keys):
                    text += "\n" + t("recording.slot_key", key=self.app.key_label(self.keys[i]))
                    style = "solid"
                else:
                    style = "waiting" if i == len(self.keys) else "slot"
                self.keyboard.set_key(board, ident, text, style, w.SLOT_COLORS[i])
        complete = len(self.keys) == 3
        self.confirm_button.update_state(enabled=complete)
        if complete:
            self.message.config(text=t("recording.done"), fg=w.GREEN)
        else:
            number = len(self.keys) + 1
            self.message.config(text=t("recording.prompt", number=number, target=t(TARGET_TEXTS[number - 1])),
                                fg=w.TEXT)

    def restart(self):
        if self.app.start_capture(self.on_key):
            self.keys = []
            self._draw()

    def on_key(self, vk):
        if vk == m.ESCAPE:
            self.cancel()
        elif vk not in m.EXPECTED:
            self.message.config(text=self.app.t("recording.invalid", key=self.app.key_name(vk)), fg=w.ORANGE)
        elif vk in self.keys:
            self.message.config(text=self.app.t("recording.duplicate", key=self.app.key_name(vk),
                                                number=len(self.keys) + 1), fg=w.ORANGE)
        else:
            self.keys.append(vk)
            if len(self.keys) == 3:
                self.app.stop_capture()
            self._draw()

    def confirm(self):
        if len(self.keys) == 3:
            self.app.draft["keys"] = list(self.keys)
            self._close()
            self.app.draw_editor()

    def cancel(self):
        self._close()

    def _close(self):
        self.app.stop_capture()
        self.app.dialog = None
        self.grab_release()
        self.destroy()


class App:
    def __init__(self, root, store, translator, powertoys, hook):
        self.root, self.store, self.t, self.powertoys, self.hook = root, store, translator, powertoys, hook
        self.scale = root.winfo_fpixels("1i") / 96
        self.selected = 0
        self.draft = None          # editable copy of the selected profile
        self.in_use = None         # index of the profile active in PowerToys
        self.live = {}             # source -> target that PowerToys is applying
        self.busy = False
        self.capture = None        # function receiving the next captured key
        self.dialog = None         # open recording window
        self.menu = None           # last opened key list
        self.heard = []            # keys Windows considers pressed
        self.physical = []         # keys physically pressed
        self.focused = False       # the window is in the foreground

        for name in ("TkDefaultFont", "TkTextFont", "TkMenuFont"):
            font.nametofont(name, root=root).configure(family=w.FONT, size=10)
        root.configure(bg=w.BACKGROUND, padx=self.px(6), pady=self.px(4))
        self._build()
        self._read_state()
        self._select(self.in_use if self.in_use is not None else 0, confirm=False)
        self._reset_monitor()
        self._loop()

    def px(self, n):
        return round(n * self.scale)

    def label(self, parent, text, size=10, color=w.TEXT, bold=False, **options):
        options.setdefault("justify", "left")
        return tk.Label(parent, text=text, bg=w.CARD, fg=color, bd=0,
                        font=(w.FONT, size, "bold" if bold else "normal"), **options)

    # --- names ----------------------------------------------------------------

    def key_name(self, vk):
        if vk in m.KEY_IDS:
            return self.t(f"key.{m.KEY_IDS[vk]}")
        if vk in m.FIXED_NAMES:
            return m.FIXED_NAMES[vk]
        return winapi.key_character(vk) or self.t("key.unknown", code=vk)

    def key_label(self, vk):
        """Short name written on a drawn key."""
        short = f"short.{m.KEY_IDS.get(vk)}"
        return self.t(short) if self.t.has(short) else self.key_name(vk)

    def config_name(self, config):
        return self.t(f"config.{config['builtin']}") if config["builtin"] else config["name"]

    @property
    def modified(self):
        return self.draft != self.store.configs[self.selected]

    # --- layout ---------------------------------------------------------------

    def _build(self):
        """Creates the whole window in the current language."""
        t, root = self.t, self.root
        root.title(t("app_title"))
        root.columnconfigure(1, weight=1)
        root.rowconfigure(0, weight=1)

        # Profile list
        profiles = w.Card(root, self.scale)
        profiles.grid(row=0, column=0, sticky="nsew")
        header = tk.Frame(profiles.body, bg=w.CARD)
        header.pack(fill="x")
        self.label(header, t("configurations.title"), 13, bold=True).pack(side="left")
        self.language_button = w.Button(header, self.scale, self.t.language.upper(), self._next_language,
                                        icon="globe")
        self.language_button.pack(side="right")
        self.label(profiles.body, t("configurations.subtitle"), color=w.MUTED).pack(anchor="w")
        buttons = tk.Frame(profiles.body, bg=w.CARD)
        buttons.pack(side="bottom", fill="x")
        self.new_button = w.Button(buttons, self.scale, t("button.new"), self._new, icon="add")
        self.new_button.pack(side="left")
        self.delete_button = w.Button(buttons, self.scale, t("button.delete"), self._delete, icon="delete")
        self.delete_button.pack(side="left", padx=self.px(4))
        self.list_frame = tk.Frame(profiles.body, bg=w.CARD)
        self.list_frame.pack(fill="x", pady=self.px(8))

        # Editor
        right = w.Card(root, self.scale)
        right.grid(row=0, column=1, sticky="nsew")
        editor = right.body
        header = tk.Frame(editor, bg=w.CARD)
        header.pack(fill="x")
        self.title_label = self.label(header, "", 13, bold=True)
        self.title_label.pack(side="left")
        self.custom_button = w.Button(header, self.scale, t("button.custom"), lambda: self._set_mode("custom"),
                                      icon="custom")
        self.custom_button.pack(side="right")
        self.standard_button = w.Button(header, self.scale, t("button.standard"),
                                        lambda: self._set_mode("standard"), icon="standard")
        self.standard_button.pack(side="right")

        footer = tk.Frame(editor, bg=w.CARD)
        footer.pack(side="bottom", fill="x")
        self.ctrl_tab_toggle = w.Toggle(footer, self.scale, t("option.ctrl_tab"), False, self._set_ctrl_tab)
        self.ctrl_tab_toggle.pack(anchor="w")
        bar = tk.Frame(footer, bg=w.CARD)
        bar.pack(fill="x", pady=(self.px(4), 0))
        self.save_button = w.Button(bar, self.scale, t("button.save"), self._save, "primary", "save")
        self.save_button.pack(side="right")
        self.revert_button = w.Button(bar, self.scale, t("button.revert"),
                                      lambda: self._select(self.selected, confirm=False), icon="undo")
        self.revert_button.pack(side="right", padx=self.px(4))
        self.status_label = self.label(bar, "", wraplength=self.px(400))
        self.status_label.pack(side="left")

        # Fixed size: the window does not change size when switching profile.
        self.content = tk.Frame(editor, bg=w.CARD, width=self.px(720), height=self.px(210))
        self.content.pack_propagate(False)
        self.content.pack(fill="both", expand=True, pady=self.px(6))

        # Pressed key: the real keyboard on the left, what Windows receives on the right
        monitor = w.Card(root, self.scale)
        monitor.grid(row=1, column=0, columnspan=2, sticky="nsew")
        header = tk.Frame(monitor.body, bg=w.CARD)
        header.pack(fill="x")
        self.label(header, t("monitor.title"), 13, bold=True).pack(side="left")
        self.origin_label = self.label(header, "", color=w.MUTED)
        self.origin_label.pack(side="right")
        area = tk.Frame(monitor.body, bg=w.CARD)
        area.pack(pady=(self.px(6), 0))
        self.keyboards = w.KeyboardPair(area, self.scale, FULL_KEYBOARD)
        # Two columns as wide as the keyboards, so titles and key names line up with them.
        side_width, offset = self.keyboards.keyboard_width, self.keyboards.offset
        gap = offset - side_width
        area.columnconfigure(0, minsize=offset)
        area.columnconfigure(1, minsize=side_width)
        for column, key in enumerate(("monitor.real", "monitor.windows")):
            self.label(area, t(key), color=w.MUTED).grid(row=0, column=column, sticky="w", padx=self.px(3))
        self.keyboards.grid(row=1, column=0, columnspan=2, pady=self.px(4))
        self.real_label = self.label(area, "—", 15, w.TEXT, bold=True)
        self.real_label.grid(row=2, column=0, padx=(0, gap))
        self.heard_label = self.label(area, "—", 15, w.ACCENT, bold=True)
        self.heard_label.grid(row=2, column=1)

    def _next_language(self):
        self._cancel_capture()
        self.t.set_language(self.t.next_language())
        self.store.language = self.t.language
        self.store.save()
        for child in self.root.winfo_children():
            child.destroy()
        self.menu = None
        self.root.minsize(1, 1)
        self._build()
        self._draw_list()
        self.draw_editor()
        self._reset_monitor()
        self.root.update_idletasks()
        self.root.minsize(self.root.winfo_reqwidth(), self.root.winfo_reqheight())

    # --- list -----------------------------------------------------------------

    def _draw_list(self):
        for child in self.list_frame.winfo_children():
            child.destroy()
        for i, config in enumerate(self.store.configs):
            active = i == self.in_use
            w.ConfigRow(self.list_frame, self.scale, self.config_name(config), i == self.selected, active,
                        not self.busy, self.t("button.active" if active else "button.activate"),
                        lambda i=i: self._select(i), lambda i=i: self._activate(i)).pack()
        builtin = self.store.configs[self.selected]["builtin"]
        self.delete_button.update_state(enabled=not builtin and not self.busy)
        self.new_button.update_state(enabled=not self.busy)

    def _can_leave(self):
        return not self.modified or messagebox.askyesno(self.t("app_title"), self.t("dialog.discard"),
                                                        parent=self.root)

    def _select(self, index, confirm=True):
        if confirm and index == self.selected:
            return
        self._cancel_capture()  # before any question: the dialog must receive the keys
        if confirm and not self._can_leave():
            return
        self.selected = index
        original = self.store.configs[index]
        self.draft = {**original, "keys": list(original["keys"]), "rows": [list(r) for r in original["rows"]]}
        self._draw_list()
        self.draw_editor()

    def _new(self):
        self._cancel_capture()
        if not self._can_leave():
            return
        name = simpledialog.askstring(self.t("app_title"), self.t("dialog.new_name"), parent=self.root)
        name = (name or "").strip()[:30]
        if not name:
            return
        self.store.configs.append(m.new_config(name))
        self.store.save()
        self._select(len(self.store.configs) - 1, confirm=False)

    def _delete(self):
        self._cancel_capture()
        i = self.selected
        title = self.t("app_title")
        if i == self.in_use:
            messagebox.showinfo(title, self.t("dialog.delete_active"), parent=self.root)
            return
        if not messagebox.askyesno(title, self.t("dialog.delete", name=self.config_name(self.draft)),
                                   parent=self.root):
            return
        del self.store.configs[i]
        if self.in_use is not None and self.in_use > i:
            self.in_use -= 1
        self.store.active = self.in_use
        self.store.save()
        self.selected, self.draft = i - 1, self.store.configs[i - 1]
        self._select(i - 1, confirm=False)

    # --- editor ---------------------------------------------------------------

    def draw_editor(self):
        self.title_label.config(text=self.config_name(self.draft))
        for child in self.content.winfo_children():
            child.destroy()
        if self.draft["mode"] == "standard":
            self._standard_editor()
        else:
            self._custom_editor()
        self.ctrl_tab_toggle.set(self.draft["ctrl_tab"])
        self._update_status()
        self._update_keyboards()

    def _standard_editor(self):
        t = self.t
        keys = self.draft["keys"]
        if len(keys) == 3:
            pairs = "   ·   ".join(f"{self.key_label(k)} → {t(text).capitalize()}"
                                   for k, text in zip(keys, TARGET_TEXTS))
            detail = t("standard.recorded", keys=pairs)
        else:
            detail = t("standard.not_recorded")
        w.InfoBox(self.content, self.scale, (t("standard.info"), detail), 716).pack(anchor="w")

        bar = tk.Frame(self.content, bg=w.CARD)
        bar.pack(fill="x", pady=self.px(10))
        w.Button(bar, self.scale, t("button.record"), self._record, "primary", "record",
                 enabled=not self.busy).pack(side="left")
        w.Button(bar, self.scale, t("button.clear"), self._clear, icon="clear", enabled=bool(keys)).pack(
            side="left", padx=self.px(4))
        self._altgr_warning()

    def _altgr_warning(self):
        """Shown only when the profile would break AltGr."""
        if m.altgr_status(self.draft, self.store.altgr_keys) is False:
            w.InfoBox(self.content, self.scale, (self.t("warning.altgr"),), 716, "warning").pack(
                side="bottom", anchor="w")

    def _custom_editor(self):
        t = self.t
        bar = tk.Frame(self.content, bg=w.CARD)
        bar.pack(fill="x")
        self.label(bar, t("custom.hint"), color=w.MUTED, wraplength=self.px(520)).pack(side="left")
        w.Button(bar, self.scale, t("button.add_row"), self._add_row, "primary", "add").pack(side="right")
        self._altgr_warning()
        self.capture_label = self.label(self.content, "", color=w.ORANGE)
        self.capture_label.pack(side="bottom", anchor="w")

        # Scrollable list of rows
        area = tk.Frame(self.content, bg=w.CARD)
        area.pack(fill="both", expand=True)
        canvas = tk.Canvas(area, bg=w.CARD, highlightthickness=0, height=self.px(60), width=self.px(600))
        scrollbar = ttk.Scrollbar(area, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        table = tk.Frame(canvas, bg=w.CARD)
        canvas.create_window(0, 0, window=table, anchor="nw")
        table.bind("<Configure>", lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))

        def wheel(event):
            if table.winfo_height() > canvas.winfo_height():
                canvas.yview_scroll(-event.delta // 120, "units")

        canvas.bind("<Enter>", lambda _e: canvas.bind_all("<MouseWheel>", wheel))
        canvas.bind("<Leave>", lambda _e: canvas.unbind_all("<MouseWheel>"))

        for column, key in ((0, "custom.source"), (3, "custom.target")):
            self.label(table, t(key), color=w.MUTED).grid(row=0, column=column, sticky="w", padx=self.px(6))
        for r, row in enumerate(self.draft["rows"]):
            for side, column in ((0, 0), (1, 3)):
                text = t("custom.choose") if row[side] is None else self.key_name(row[side])
                choice = w.Button(table, self.scale, text, lambda: None, trailing="chevron", width=210)
                choice.command = lambda r=r, side=side, b=choice: self._key_menu(b, r, side)
                choice.grid(row=r + 1, column=column)
                w.Button(table, self.scale, "", lambda r=r, side=side: self._capture_row(r, side), icon="keyboard",
                         width=46).grid(row=r + 1, column=column + 1)
            self.label(table, "→").grid(row=r + 1, column=2, padx=self.px(8))
            w.Button(table, self.scale, "", lambda r=r: self._remove_row(r), icon="delete", width=46).grid(
                row=r + 1, column=5, padx=self.px(8))

    def _key_menu(self, button, row, side):
        if self.menu:
            self.menu.destroy()
        self.menu = menu = tk.Menu(self.root, tearoff=0)
        values = ([m.DISABLED] if side else []) + m.KEY_LIST
        for i, vk in enumerate(values):
            menu.add_command(label=self.key_name(vk), columnbreak=bool(i) and i % 30 == 0,
                             command=lambda vk=vk: self._set_row_key(row, side, vk))
        menu.tk_popup(button.winfo_rootx(), button.winfo_rooty() + button.winfo_height())

    def _set_mode(self, mode):
        if mode == self.draft["mode"]:
            return
        self.stop_capture()
        if mode == "custom" and not self.draft["rows"]:
            self.draft["rows"] = [list(r) for r in m.rows_of(self.draft)]
        self.draft["mode"] = mode
        self.draw_editor()

    def _set_ctrl_tab(self, on):
        self.draft["ctrl_tab"] = on
        self._update_status()

    def _set_row_key(self, row, side, vk):
        self.draft["rows"][row][side] = vk
        self.draw_editor()

    def _add_row(self):
        self.stop_capture()
        self.draft["rows"].append([None, None])
        self.draw_editor()

    def _remove_row(self, row):
        self.stop_capture()
        del self.draft["rows"][row]
        self.draw_editor()

    def _error_text(self, error):
        key, vk = error
        return self.t(key) if vk is None else self.t(key, key=self.key_name(vk))

    def _update_status(self):
        error = m.rows_error(m.rows_of(self.draft))
        if self.busy:
            text, color = self.t("status.applying"), w.ACCENT
        elif error:
            text, color = self._error_text(error), w.ORANGE
        elif self.modified:
            text, color = self.t("status.unsaved"), w.ORANGE
        elif self.in_use is None:
            text, color = self.t("status.foreign"), w.ORANGE
        else:
            text, color = "", w.MUTED
        self.status_label.config(text=text, fg=color)
        self.save_button.update_state(enabled=self.modified and not error and not self.busy)
        self.revert_button.update_state(enabled=self.modified)
        for button, mode in ((self.standard_button, "standard"), (self.custom_button, "custom")):
            button.update_state(style="primary" if self.draft["mode"] == mode else "secondary")

    # --- key capture ----------------------------------------------------------

    def start_capture(self, receiver):
        self.stop_capture()
        try:
            self.hook.restart()  # before PowerToys: the real keys arrive here
        except winapi.PlatformError as error:
            self._show_error(error)
            return False
        self._reset_monitor()
        self.capture = receiver
        self.hook.capture = True
        return True

    def stop_capture(self):
        self.hook.capture = False
        self.capture = None
        while not self.hook.captured.empty():
            self.hook.captured.get()

    def _cancel_capture(self):
        if self.capture:
            self.stop_capture()
            self.draw_editor()

    def _clear(self):
        self.stop_capture()
        self.draft["keys"] = []
        self.draw_editor()

    def _record(self):
        self.dialog = RecordingDialog(self)
        self.dialog.restart()

    def _capture_row(self, row, side):
        def receive(vk):
            self.stop_capture()
            self._set_row_key(row, side, vk)

        if self.start_capture(receive):
            self.root.focus_set()
            key = "custom.capture_target" if side else "custom.capture_source"
            self.capture_label.config(text=self.t(key, row=row + 1))

    # --- PowerToys ------------------------------------------------------------

    def _show_error(self, error):
        text = (self.t(error.key, **error.values) if isinstance(error, winapi.PlatformError) else str(error))
        messagebox.showerror(self.t("app_title"), text, parent=self.root)

    def _read_state(self):
        keymap = self.powertoys.current_mapping()
        self.in_use = self.store.find_active(m.signature(keymap))
        self.live = {}
        for entry in (keymap.get("remapKeys") or {}).get("inProcess") or []:
            try:
                self.live[int(entry["originalKeys"])] = int(entry["newRemapKeys"])
            except (KeyError, ValueError):  # conversions to key combinations are not drawn
                pass

    def _refresh_from_powertoys(self):
        """The mapping may have been changed in PowerToys while the window was in the background."""
        before = self.in_use, self.live
        self._read_state()
        if (self.in_use, self.live) != before:
            self._draw_list()
            self._update_status()
            self._update_keyboards()

    def _save(self):
        self.stop_capture()
        index = self.selected
        was_active = index == self.in_use
        if self.draft["mode"] == "standard":
            self.draft["rows"] = []  # custom mode will start again from the standard rows
        self.store.configs[index] = self.draft
        self.store.save()
        self._select(index, confirm=False)
        if was_active:
            self._activate(index)

    def _activate(self, index):
        if self.busy:
            return
        title = self.t("app_title")
        if index == self.selected and self.modified:
            messagebox.showinfo(title, self.t("dialog.save_first"), parent=self.root)
            return
        config = self.store.configs[index]
        invalid = m.rows_error(m.rows_of(config))
        if invalid:
            messagebox.showerror(title, self._error_text(invalid), parent=self.root)
            return
        self.stop_capture()
        self.busy = True
        self.language_button.update_state(enabled=False)
        self._draw_list()
        self.draw_editor()
        failures = []
        keymap = m.build_keymap(config, self.store.altgr_keys)

        def work():
            try:
                self.powertoys.apply(keymap)
            except Exception as error:  # every error must be shown in the window
                failures.append(error)

        thread = threading.Thread(target=work)
        thread.start()

        def check():
            if thread.is_alive():
                self.root.after(100, check)
                return
            self.busy = False
            self.language_button.update_state(enabled=True)
            self.store.active = index
            try:
                self.store.save()
                self._read_state()
                self.hook.restart()
            except Exception as error:
                failures.append(error)
            self._reset_monitor()
            self._draw_list()
            self.draw_editor()
            if failures:
                self._show_error(failures[0])

        check()

    # --- monitor --------------------------------------------------------------

    def _physical_order(self):
        """The three physical keys before the space bar, so the drawing looks like the real keyboard."""
        active = self.store.configs[self.in_use]["keys"] if self.in_use is not None else []
        for keys in (active, self.draft["keys"] if self.draft else []):
            if len(keys) == 3:
                return keys
        return m.EXPECTED

    def _update_keyboards(self):
        """Both keyboards have the same keys: only the highlighted ones differ."""
        order = self._physical_order()
        positions = {}  # virtual key -> identifier on the drawing
        for board, ident in self.keyboards.keys:
            if board == self.keyboards.REAL and ident != "FN":
                positions[order[int(ident[1])] if isinstance(ident, str) else ident] = ident

        # One colour for each target, assigned from the leftmost converted key.
        converted = {s: t for s, t in self.live.items() if t != m.DISABLED}
        drawn = list(positions)
        colors = {}
        for source in sorted(converted, key=lambda vk: (drawn.index(vk) if vk in drawn else len(drawn))):
            colors.setdefault(converted[source], w.PAIR_COLORS[len(colors) % len(w.PAIR_COLORS)])

        real = set(self.physical)
        real.update(r for _, sources, _ in self.heard if len(sources) == 1 for r in sources)
        heard = {vk for vk, _, _ in self.heard}

        for board in (self.keyboards.REAL, self.keyboards.WINDOWS):
            self.keyboards.set_key(board, "FN", self.t("short.fn"), "off")
        for vk, ident in positions.items():
            text = self.key_label(vk)
            # Left: the keys that get converted. Right: the keys they turn into.
            color = colors.get(converted.get(vk))
            if self.live.get(vk) == m.DISABLED:
                self._paint(self.keyboards.REAL, ident, f"✕ {text}", w.DISABLED_COLOR, vk in real)
            else:
                self._paint(self.keyboards.REAL, ident, text, color, vk in real)
            self._paint(self.keyboards.WINDOWS, ident, text, colors.get(vk), vk in heard)
        self.keyboards.set_wires(
            (positions[s], positions[t], colors[t], s in real)
            for s, t in converted.items() if s in positions and t in positions)

    def _paint(self, board, ident, text, color, pressed):
        if color:
            style = "solid" if pressed else "mapped"
        else:
            style = "dim_pressed" if pressed else "dim"
        self.keyboards.set_key(board, ident, text, style, color)

    def _reset_monitor(self):
        self.heard, self.physical = [], []
        self.heard_label.config(text="—")
        self.real_label.config(text="—")
        self.origin_label.config(text=self.t("monitor.idle"))
        self._update_keyboards()

    def _on_key_event(self, vk, pressed, injected, from_powertoys, swallowed, physical):
        """Tracks what Windows receives and which key is really pressed. True if Windows got a new key."""
        if not pressed:
            if not swallowed:
                self.heard = [h for h in self.heard if h[0] != vk]
            if not injected:
                self.physical = [p for p in self.physical if p != vk]
                if self.live.get(vk) is not None:
                    self.heard = [h for h in self.heard if h[0] != self.live[vk]]
                if not self.physical:  # nothing is held, so nothing can still be down
                    self.heard = []
            return False
        if swallowed:  # PowerToys blocks it: it is the real key, the converted one follows
            if injected:
                return False
            if vk not in self.physical:
                self.physical.append(vk)
            if self.live.get(vk) != m.DISABLED:
                return False
            self._hear(m.DISABLED, [vk], "monitor.disabled")
            return True
        if not injected:
            sources, origin = [vk], "monitor.no_conversion"
            if vk not in self.physical:
                self.physical.append(vk)
        elif from_powertoys and m.ALT_RIGHT in self.physical:
            if vk in MODIFIERS:
                return False  # internal steps of the AltGr rules
            sources, origin = [vk], "monitor.altgr"
        elif from_powertoys:
            candidates = [s for s, t in self.live.items() if t == vk]
            sources = [physical] if physical in candidates else (candidates or [vk])
            origin = "monitor.converted" if candidates else "monitor.shortcut"
        else:
            sources, origin = [], "monitor.program"
        self._hear(vk, sources, origin)
        return True

    def _hear(self, vk, sources, origin):
        self.heard = [h for h in self.heard if h[0] != vk] + [(vk, sources, origin)]

    def _show_monitor(self):
        if not self.heard:
            return
        either = f" {self.t('monitor.or')} "
        self.heard_label.config(text=" + ".join(self.key_name(vk) for vk, _, _ in self.heard))
        self.real_label.config(text=" + ".join(
            either.join(self.key_name(s) for s in sources) if sources else "—" for _, sources, _ in self.heard))
        self.origin_label.config(text=self.t(self.heard[-1][2]))

    def _loop(self):
        try:
            while not self.hook.captured.empty():
                vk = self.hook.captured.get()
                if self.capture:
                    self.capture(vk)
            focused = winapi.app_in_foreground()
            if focused and not self.focused and not self.busy:
                self._refresh_from_powertoys()
            self.focused = focused
            if not focused:
                # The recording window waits; the capture of a single row is cancelled instead.
                if self.capture and not self.dialog:
                    self._cancel_capture()
                if self.heard or self.physical:
                    self._reset_monitor()
            changed = new_keys = False
            while not self.hook.events.empty():
                event = self.hook.events.get()
                if not focused:
                    continue
                new_keys = self._on_key_event(*event) or new_keys
                changed = True
                self._show_monitor()  # at every press, even if the release is already queued
            # Win or Alt pressed alone would open Start or the window menu.
            heard = {vk for vk, _, _ in self.heard}
            if new_keys and heard & {m.WIN, m.WIN_RIGHT, m.ALT} and heard <= MODIFIERS:
                winapi.send_neutral_key()
            if changed:
                self._update_keyboards()
        finally:
            self.root.after(15, self._loop)


def main():
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)  # sharp text on high density screens
    except (AttributeError, OSError):
        pass
    root = tk.Tk()
    root.withdraw()
    translator = i18n.Translator(winapi.system_language())
    try:
        store = m.ConfigStore(CONFIG_FILE, winapi.altgr_keys())
        if store.language:
            translator.set_language(store.language)
        if not CONFIG_FILE.is_file():
            store.save()
    except (OSError, ValueError, KeyError, TypeError) as error:
        messagebox.showerror(translator("app_title"),
                             translator("error.config_file", file=CONFIG_FILE.name, detail=error))
        return
    hook = winapi.KeyboardHook()
    try:
        hook.start()
    except winapi.PlatformError as error:
        messagebox.showerror(translator("app_title"), translator(error.key, **error.values))
        return
    try:
        App(root, store, translator, winapi.PowerToys(), hook)
        root.update_idletasks()
        root.minsize(root.winfo_reqwidth(), root.winfo_reqheight())
        root.deiconify()
        root.mainloop()
    finally:
        hook.stop()


if __name__ == "__main__":
    main()

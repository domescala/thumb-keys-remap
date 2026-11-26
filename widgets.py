"""Widgets with rounded corners and shadows, drawn with Pillow."""
import tkinter as tk
from tkinter import font

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageTk

BACKGROUND, CARD, TEXT, MUTED = "#edf0f5", "#ffffff", "#111827", "#6b7280"
ACCENT, GREEN, ORANGE = "#2563eb", "#16a34a", "#b45309"
SLOT_COLORS = ("#2563eb", "#7c3aed", "#db2777")
# One colour for each converted key, shared by the two keyboards and the wire joining them.
PAIR_COLORS = ("#2563eb", "#db2777", "#16a34a", "#ea580c", "#7c3aed", "#0891b2", "#ca8a04", "#dc2626")
DISABLED_COLOR = "#57534e"  # a key that the mapping turns off
FONT = "Segoe UI"

# Glyphs of the Windows icon fonts
ICONS = {
    "add": "", "delete": "", "save": "", "undo": "", "record": "",
    "clear": "", "keyboard": "", "globe": "", "check": "", "cancel": "",
    "restart": "", "power": "", "standard": "", "custom": "", "info": "",
    "chevron": "", "warning": "",
}

_images = {}  # Tk does not keep images alive: they are stored here
_icon_font = None


def icon_font(widget):
    """Windows 11 ships "Segoe Fluent Icons", Windows 10 "Segoe MDL2 Assets": same glyphs."""
    global _icon_font
    if _icon_font is None:
        families = set(font.families(widget))
        _icon_font = "Segoe Fluent Icons" if "Segoe Fluent Icons" in families else "Segoe MDL2 Assets"
    return _icon_font


def text_width(widget, text, family=FONT, size=10, weight="normal"):
    return font.Font(root=widget, family=family, size=size, weight=weight).measure(text)


def mix(color, other, amount):
    """`color` moved towards `other` by `amount` (0-1)."""
    a, b = (tuple(int(c[i:i + 2], 16) for i in (1, 3, 5)) for c in (color, other))
    return "#" + "".join(f"{round(x + (y - x) * amount):02x}" for x, y in zip(a, b))


def render_rounded(width, height, radius, background, fill, outline=None, line=1, shadow=None, margin=0):
    """Rounded rectangle over `background`. `shadow` is (blur, vertical offset, opacity 0-255)."""
    base = Image.new("RGBA", (width, height), background)
    x1, y1, x2, y2 = margin, margin, width - margin, height - margin
    if shadow:
        blur, drop, opacity = shadow
        mask = Image.new("L", base.size, 0)
        ImageDraw.Draw(mask).rounded_rectangle((x1, y1 + drop, x2 - 1, y2 - 1 + drop), radius, fill=opacity)
        mask = mask.filter(ImageFilter.GaussianBlur(blur))
        base = Image.composite(Image.new("RGBA", base.size, "#1e293b"), base, mask)
    k = 3  # drawn three times larger and then reduced: smooth edges
    body = Image.new("RGBA", ((x2 - x1) * k, (y2 - y1) * k), (0, 0, 0, 0))
    ImageDraw.Draw(body).rounded_rectangle((0, 0, body.width - 1, body.height - 1), radius * k,
                                           fill=fill, outline=outline, width=line * k if outline else 0)
    base.alpha_composite(body.resize((x2 - x1, y2 - y1), Image.LANCZOS), (x1, y1))
    return base


def photo(*arguments):
    """Like render_rounded(), ready for Tk and reused."""
    if arguments not in _images:
        _images[arguments] = ImageTk.PhotoImage(render_rounded(*arguments))
    return _images[arguments]


class Card(tk.Frame):
    """White rounded panel with a shadow. Put the content in .body"""

    def __init__(self, parent, scale, padding=12):
        super().__init__(parent, bg=BACKGROUND)
        self.scale = scale
        self._photo = None
        self._size = None
        self._backdrop = tk.Label(self, bd=0, bg=BACKGROUND)
        self._backdrop.place(x=0, y=0, relwidth=1, relheight=1)
        self.body = tk.Frame(self, bg=CARD)
        distance = round((10 + padding) * scale)
        self.body.pack(fill="both", expand=True, padx=distance, pady=distance)
        self.bind("<Configure>", self._redraw)

    def _redraw(self, event):
        size = (event.width, event.height)
        s = self.scale
        if size == self._size or min(size) < 40 * s:
            return
        self._size = size
        self._photo = ImageTk.PhotoImage(render_rounded(
            *size, round(18 * s), BACKGROUND, CARD, "#e6e9f0", 1, (round(6 * s), round(3 * s), 34), round(10 * s)))
        self._backdrop.config(image=self._photo)


class Button(tk.Canvas):
    # style -> (fill, fill on hover, outline, text)
    STYLES = {
        "primary": (ACCENT, "#1d4ed8", None, "#ffffff"),
        "secondary": ("#ffffff", "#f1f5f9", "#d5dae4", TEXT),
        "off": ("#f0f2f5", "#f0f2f5", None, "#a3a9b5"),
    }

    def __init__(self, parent, scale, text, command, style="secondary", icon=None, trailing=None, width=None,
                 enabled=True, background=CARD):
        self.scale, self.text, self.command, self.style = scale, text, command, style
        self.enabled, self.background = enabled, background
        self.icon, self.trailing = icon, trailing
        self.align_left = trailing is not None
        gap = round(8 * scale)
        self.icon_width = text_width(parent, ICONS[icon], icon_font(parent), 11) if icon else 0
        content = self.icon_width + (gap if icon and text else 0)
        content += text_width(parent, text) if text else 0
        self.content = content
        self.width = round(width * scale) if width else content + round(34 * scale)
        self.height = round(40 * scale)
        super().__init__(parent, width=self.width, height=self.height, bg=background, highlightthickness=0,
                         takefocus=1)
        self._hover = self._focus = False
        self.bind("<Enter>", lambda _e: self._set_hover(True))
        self.bind("<Leave>", lambda _e: self._set_hover(False))
        self.bind("<ButtonRelease-1>", self._release)
        for event in ("<Return>", "<space>"):
            self.bind(event, lambda _e: self._invoke())
        self.bind("<FocusIn>", lambda _e: self._set_focus(True))
        self.bind("<FocusOut>", lambda _e: self._set_focus(False))
        self._draw()

    def update_state(self, style=None, enabled=None):
        new = (self.style if style is None else style, self.enabled if enabled is None else enabled)
        if new != (self.style, self.enabled):
            self.style, self.enabled = new
            self._draw()

    def _set_hover(self, hover):
        self._hover = hover
        self._draw()

    def _set_focus(self, focus):
        self._focus = focus
        self._draw()

    def _release(self, event):
        if 0 <= event.x < self.width and 0 <= event.y < self.height:
            self._invoke()

    def _invoke(self):
        if self.enabled:
            self.command()

    def _draw(self):
        s = self.scale
        fill, hover, outline, color = self.STYLES[self.style if self.enabled else "off"]
        line = 1
        if self.enabled and self._focus:
            outline, line = "#93b4fb", 2
        image = photo(self.width, self.height, round(11 * s), self.background,
                      hover if self._hover and self.enabled else fill, outline, line,
                      (round(2 * s), round(2 * s), 45) if self.enabled else None, round(4 * s))
        self.delete("all")
        self.create_image(0, 0, image=image, anchor="nw")
        x = round(16 * s) if self.align_left else (self.width - self.content) / 2
        y = self.height / 2
        if self.icon:
            self.create_text(x, y, text=ICONS[self.icon], fill=color, font=(icon_font(self), 11), anchor="w")
            x += self.icon_width + round(8 * s)
        if self.text:
            self.create_text(x, y, text=self.text, fill=color, font=(FONT, 10), anchor="w")
        if self.trailing:
            self.create_text(self.width - round(16 * s), y, text=ICONS[self.trailing], fill=color,
                             font=(icon_font(self), 8), anchor="e")
        self.config(cursor="hand2" if self.enabled else "")


class Toggle(tk.Canvas):
    """On/off switch with its label."""

    def __init__(self, parent, scale, text, on, command):
        self.scale, self.text, self.on, self.command = scale, text, on, command
        super().__init__(parent, width=text_width(parent, text) + round(60 * scale), height=round(30 * scale),
                         bg=CARD, highlightthickness=0, cursor="hand2", takefocus=1)
        for event in ("<ButtonRelease-1>", "<Return>", "<space>"):
            self.bind(event, lambda _e: self._switch())
        self._draw()

    def set(self, on):
        self.on = on
        self._draw()

    def _switch(self):
        self.set(not self.on)
        self.command(self.on)

    def _draw(self):
        def p(n):
            return round(n * self.scale)

        key = ("toggle", p(40), self.on)
        if key not in _images:
            track = render_rounded(p(40), p(22), p(11), CARD, ACCENT if self.on else "#c6ccd8")
            knob = render_rounded(p(20), p(20), p(8), "#00000000", "#ffffff", None, 1, (p(1), p(1), 80), p(2))
            track.alpha_composite(knob, (p(19) if self.on else p(1), p(1)))
            _images[key] = ImageTk.PhotoImage(track)
        self.delete("all")
        self.create_image(0, p(4), anchor="nw", image=_images[key])
        self.create_text(p(50), p(15), text=self.text, anchor="w", fill=TEXT, font=(FONT, 10))


class InfoBox(tk.Canvas):
    """Tinted box with an icon: it informs, it cannot be clicked."""

    # kind -> (icon, fill, outline, icon colour)
    KINDS = {
        "info": ("info", "#eef4ff", "#cfdefc", ACCENT),
        "warning": ("warning", "#fff7ed", "#fed7aa", ORANGE),
    }

    def __init__(self, parent, scale, lines, width, kind="info"):
        def p(n):
            return round(n * scale)

        super().__init__(parent, width=p(width), bg=CARD, highlightthickness=0)
        icon, fill, outline, color = self.KINDS[kind]
        y = p(12)
        for i, line in enumerate(lines):
            item = self.create_text(p(48), y, text=line, anchor="nw", width=p(width - 62), font=(FONT, 10),
                                    fill=TEXT if i == 0 else MUTED)
            y = self.bbox(item)[3] + p(4)
        height = y + p(8)
        self.config(height=height)
        background = self.create_image(0, 0, anchor="nw",
                                       image=photo(p(width), height, p(12), CARD, fill, outline))
        self.tag_lower(background)
        self.create_text(p(24), p(22), text=ICONS[icon], fill=color, font=(icon_font(self), 13))


class ConfigRow(tk.Canvas):
    """A profile in the list, with the button that activates it."""

    def __init__(self, parent, scale, name, selected, active, enabled, label, on_select, on_activate):
        def p(n):
            return round(n * scale)

        width, height, pill = p(264), p(54), p(104)
        super().__init__(parent, width=width, height=height, bg=CARD, highlightthickness=0, cursor="hand2")
        self.create_image(0, 0, anchor="nw", image=photo(
            width, height, p(13), CARD, "#eaf1ff" if selected else "#ffffff",
            "#93b4fb" if selected else "#e2e5ec", 1, (p(2), p(2), 40), p(4)))
        weight = "bold" if selected else "normal"
        room = width - pill - p(36)
        if text_width(self, name, weight=weight) > room:
            while name and text_width(self, name + "…", weight=weight) > room:
                name = name[:-1]
            name += "…"
        self.create_text(p(18), height / 2, text=name, anchor="w", fill=TEXT, font=(FONT, 10, weight))
        left = width - pill - p(12)
        self.create_image(left, p(11), anchor="nw", tags="pill", image=photo(
            pill, p(32), p(16), "#eaf1ff" if selected else "#ffffff", GREEN if active else "#eceff3"))
        color = "#ffffff" if active else (TEXT if enabled else "#a3a9b5")
        icon = ICONS["check" if active else "power"]
        icon_width = text_width(self, icon, icon_font(self), 10)
        content = icon_width + p(6) + text_width(self, label, size=9)
        x = left + (pill - content) / 2
        self.create_text(x, height / 2, text=icon, anchor="w", fill=color, font=(icon_font(self), 10), tags="pill")
        self.create_text(x + icon_width + p(6), height / 2, text=label, anchor="w", fill=color, font=(FONT, 9),
                         tags="pill")

        def click(event):
            if event.x >= left:
                if enabled:
                    on_activate()
            else:
                on_select()

        self.bind("<ButtonRelease-1>", click)


class KeyboardCanvas(tk.Canvas):
    """Canvas holding one or more keyboards made of rounded keys.

    A keyboard is a list of rows of (identifier, width in units) pairs.
    """

    def __init__(self, parent, scale, width, height, font_size=8):
        self.scale = scale
        super().__init__(parent, width=width, height=height, bg=CARD, highlightthickness=0)
        self.font = (FONT, font_size)
        self.keys = {}  # (keyboard, identifier) -> list of drawn keys
        self.states = {}  # (keyboard, identifier) -> (text, style, colour)

    @staticmethod
    def size(rows, unit):
        return max(round(sum(width for _, width in row) * unit) for row in rows), len(rows) * unit

    def add_keyboard(self, board, rows, unit, x=0, y=0):
        for r, row in enumerate(rows):
            position = 0
            for ident, width in row:
                x1, x2 = x + round(position * unit), x + round((position + width) * unit)
                image = self.create_image(x1, y + r * unit, anchor="nw")
                label = self.create_text((x1 + x2) / 2, y + r * unit + unit / 2, font=self.font, justify="center")
                self.keys.setdefault((board, ident), []).append(
                    {"image": image, "label": label, "width": x2 - x1, "height": unit,
                     "left": x1, "top": y + r * unit, "centre": (x1 + x2) / 2, "bottom": y + (r + 1) * unit})
                position += width

    def _look(self, style, color):
        """(fill, outline, outline width, text colour, shadow) of a key style."""
        thick = max(1, round(2 * self.scale))
        return {
            "off": ("#f2f3f6", None, 1, "#b7bdc8", False),
            "dim": ("#dde1e8", None, 1, "#8a93a3", False),
            "dim_pressed": ("#374151", None, 1, "#ffffff", True),
            "slot": ("#ffffff", color, thick, color, True),
            "waiting": ("#fef3c7", color, thick, color, True),
            "mapped": (mix(color or ACCENT, "#ffffff", 0.78), color, thick, mix(color or ACCENT, "#000000", 0.35),
                       True),
            "solid": (color, None, 1, "#ffffff", True),
        }[style]

    def set_key(self, board, ident, text, style, color=None):
        if self.states.get((board, ident)) == (text, style, color):
            return
        self.states[(board, ident)] = (text, style, color)
        s = self.scale
        fill, outline, line, text_color, shadow = self._look(style, color)
        for key in self.keys[(board, ident)]:
            self.itemconfig(key["image"], image=photo(
                key["width"], key["height"], round(8 * s), CARD, fill, outline, line,
                (max(1, round(2 * s)), max(1, round(2 * s)), 55) if shadow else None, max(1, round(3 * s))))
            self.itemconfig(key["label"], text=text, fill=text_color)


class KeyboardPair(KeyboardCanvas):
    """Two identical keyboards side by side, with wires joining each converted key to its result."""

    REAL, WINDOWS = "real", "windows"

    def __init__(self, parent, scale, rows, unit=34, gap=40, wire_room=52):
        unit, gap, room = round(unit * scale), round(gap * scale), round(wire_room * scale)
        keyboard_width, keyboard_height = self.size(rows, unit)
        self.keyboard_width, self.offset = keyboard_width, keyboard_width + gap
        self.total = (self.offset + keyboard_width, keyboard_height + room)
        super().__init__(parent, scale, *self.total)
        self.keyboard_height, self.room = keyboard_height, room
        self.add_keyboard(self.REAL, rows, unit)
        self.add_keyboard(self.WINDOWS, rows, unit, x=self.offset)
        self._overlay = self.create_image(0, 0, anchor="nw")
        self._wires = None
        self._wire_images = {}

    def set_wires(self, wires):
        """`wires`: (source identifier, target identifier, colour, pressed) tuples."""
        wires = tuple(wires)
        if wires == self._wires:
            return
        self._wires = wires
        if wires not in self._wire_images:
            if len(self._wire_images) > 60:
                self._wire_images.clear()
            self._wire_images[wires] = ImageTk.PhotoImage(self._draw_wires(wires))
        self.itemconfig(self._overlay, image=self._wire_images[wires])
        self.tag_raise(self._overlay)

    def _draw_wires(self, wires):
        s, k = self.scale, 3
        image = Image.new("RGBA", (self.total[0] * k, self.total[1] * k), (0, 0, 0, 0))
        ends = [(self.keys[(self.REAL, a)][0], self.keys[(self.WINDOWS, b)][0], color, pressed)
                for a, b, color, pressed in wires]
        # The rightmost source gets the highest lane: this limits the crossings.
        ends.sort(key=lambda w: -w[0]["centre"])
        step = min(10 * s, (self.room - 16 * s) / max(1, len(ends) - 1))
        for lane, (source, target, color, pressed) in enumerate(ends):
            layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
            pen = ImageDraw.Draw(layer)
            rgb = mix(color, "#000000", 0.25)
            ink = tuple(int(rgb[i:i + 2], 16) for i in (1, 3, 5)) + (255 if pressed else 150,)
            width = round((4 if pressed else 2.4) * s * k)
            y = (self.keyboard_height + 8 * s + lane * step) * k
            x1, x2 = source["centre"] * k, target["centre"] * k
            y1, y2 = (source["bottom"] - 4 * s) * k, (target["bottom"] - 4 * s) * k
            radius = max(1, min(9 * s * k, y - y1, y - y2, (x2 - x1) / 2))
            half = width / 2
            # Down from the source, across, and up into the target, with rounded corners.
            pen.line((x1, y1, x1, y - radius), fill=ink, width=width)
            pen.arc((x1 - half, y - 2 * radius - half, x1 + 2 * radius + half, y + half), 90, 180, fill=ink,
                    width=width)
            pen.line((x1 + radius, y, x2 - radius, y), fill=ink, width=width)
            pen.arc((x2 - 2 * radius - half, y - 2 * radius - half, x2 + half, y + half), 0, 90, fill=ink,
                    width=width)
            pen.line((x2, y - radius, x2, y2), fill=ink, width=width)
            dot = width * 1.1
            for x, end in ((x1, y1), (x2, y2)):
                pen.ellipse((x - dot, end - dot, x + dot, end + dot), fill=ink)
            self._fade_over_keys(layer, (source, target), k)
            image.alpha_composite(layer)
        return image.resize(self.total, Image.LANCZOS)

    def _fade_over_keys(self, layer, ends, k):
        """A wire crossing other keys becomes faint there, so their labels stay readable."""
        mask = Image.new("L", layer.size, 255)
        pen = ImageDraw.Draw(mask)
        margin = 3 * self.scale
        for keys in self.keys.values():
            for key in keys:
                if key not in ends:
                    pen.rounded_rectangle(
                        ((key["left"] + margin) * k, (key["top"] + margin) * k,
                         (key["left"] + key["width"] - margin) * k, (key["bottom"] - margin) * k),
                        8 * self.scale * k, fill=70)
        layer.putalpha(ImageChops.multiply(layer.getchannel("A"), mask))

# ArchViz Presentation Sheet Generator 2026 May-June => (26.06)

import customtkinter as ctk
from tkinter import filedialog, colorchooser, messagebox
from PIL import Image, ImageDraw, ImageFont
import threading, sys, os, copy
from pathlib import Path
from datetime import datetime


def resource_path(relative_path):
    base_path = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)


# ═══════════════════════════════════════════════════════════════
#  PROCESSING ENGINE
# ═══════════════════════════════════════════════════════════════

SUPPORTED_EXT = {".jpg", ".jpeg", ".png", ".tif", ".tiff"}


def load_font(path, size, fallbacks=None):
    candidates = (
        ([path] if path else [])
        + (fallbacks or [])
        + [
            r"C:\Windows\Fonts\calibri.ttf",
            r"C:\Windows\Fonts\arial.ttf",
            "DejaVuSans.ttf",
            "LiberationSans-Regular.ttf",
            "FreeSans.ttf",
        ]
    )
    for c in candidates:
        if not c:
            continue
        try:
            return ImageFont.truetype(c, size)
        except:
            continue
    return ImageFont.load_default()


def make_watermark_strip(render_w, cfg):
    font = load_font(cfg["watermark_font_path"], cfg["watermark_font_size"])
    unit = cfg["watermark_text"] + cfg["watermark_separator"]
    track = cfg["watermark_tracking"]
    dummy = Image.new("RGBA", (1, 1))
    dd = ImageDraw.Draw(dummy)
    bbox = dd.textbbox((0, 0), unit, font=font)
    unit_w = bbox[2] - bbox[0] + track * len(unit)
    unit_h = bbox[3] - bbox[1]
    strip_h = unit_h + 14
    tile_w = render_w + unit_w * 2
    strip = Image.new("RGBA", (tile_w, strip_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(strip)
    x = 0
    color = cfg["watermark_color"] + (cfg["watermark_opacity"],)
    while x < tile_w:
        for ch in unit:
            cb = draw.textbbox((0, 0), ch, font=font)
            draw.text((x, 7), ch, font=font, fill=color)
            x += (cb[2] - cb[0]) + track
        if x > tile_w:
            break
    if cfg["watermark_angle"] != 0:
        strip = strip.rotate(-cfg["watermark_angle"], expand=False)
    return strip.crop((0, 0, render_w, strip_h))


def draw_watermarks(render, cfg):
    if render.mode != "RGBA":
        render = render.convert("RGBA")
    rw, rh = render.size
    x_offset = int(float(cfg.get("watermark_x", 0.0)) * rw)
    for frac in cfg["watermark_positions"]:
        frac = frac[0] if isinstance(frac, (list, tuple)) else frac
        strip = make_watermark_strip(rw - x_offset, cfg)
        y = int(float(frac) * rh) - strip.size[1] // 2
        render.paste(strip, (x_offset, y), strip)
    return render


def draw_bottom_bar(draw, bx, by, bw, bh, cfg, sheet):
    fl = load_font(cfg["body_font_path"], cfg["label_font_size"])
    fv = load_font(cfg["body_font_bold"], cfg["value_font_size"])
    cx = bx + 40
    cg = 60
    lh = draw.textbbox((0, 0), "A", font=fl)[3]
    vh = draw.textbbox((0, 0), "A", font=fv)[3]
    tbh = lh + 8 + vh
    ty = by + (bh - tbh) // 2
    for field in cfg["fields"]:
        lbl = field["label"].upper()
        val = field["value"]
        draw.text((cx, ty), lbl, font=fl, fill=cfg["label_color"])
        draw.text((cx, ty + lh + 8), val, font=fv, fill=cfg["value_color"])
        vb = draw.textbbox((0, 0), val, font=fv)
        lb = draw.textbbox((0, 0), lbl, font=fl)
        cx += max(vb[2], lb[2]) + cg
    fr = load_font(cfg["body_font_path"], cfg["studio_role_size"])
    fs = load_font(
        cfg["studio_font_path"] or cfg["body_font_bold"], cfg["studio_name_size"]
    )
    fb = load_font(cfg["body_font_path"], cfg["studio_sub_size"])
    logo_img = None
    logo_w = 0
    if cfg["logo_path"] and os.path.exists(cfg["logo_path"]):
        try:
            logo_img = Image.open(cfg["logo_path"]).convert("RGBA")
            logo_img = logo_img.resize(cfg["logo_size"], Image.LANCZOS)
            logo_w = logo_img.size[0] + 16
        except:
            logo_img = None
    rb = draw.textbbox((0, 0), cfg["studio_role"], font=fr)
    nb = draw.textbbox((0, 0), cfg["studio_name"], font=fs)
    sb = draw.textbbox((0, 0), cfg["studio_sub"], font=fb)
    tw = max(rb[2], nb[2], sb[2])
    tx = bx + bw - 40 - tw - logo_w
    rh_ = rb[3]
    nh = nb[3]
    sh = sb[3]
    tth = rh_ + 4 + nh + 4 + sh
    tty = by + (bh - tth) // 2
    draw.text((tx, tty), cfg["studio_role"], font=fr, fill=cfg["label_color"])
    draw.text(
        (tx, tty + rh_ + 4), cfg["studio_name"], font=fs, fill=cfg["studio_color"]
    )
    draw.text(
        (tx, tty + rh_ + 4 + nh + 4),
        cfg["studio_sub"],
        font=fb,
        fill=cfg.get("studio_sub_color", cfg["label_color"]),
    )
    if logo_img:
        ly = by + (bh - logo_img.size[1]) // 2
        sheet.paste(logo_img, (tx + tw + 16, ly), logo_img)


def build_sheet(img_source, cfg):
    render = Image.open(img_source) if isinstance(img_source, Path) else img_source
    if render.mode not in ("RGB", "RGBA"):
        render = render.convert("RGB")
    rw, rh = render.size
    top_h = int(rh * cfg["top_border_ratio"])
    bot_h = int(rh * cfg["bottom_border_ratio"])
    side_p = int(rw * cfg["side_pad_ratio"])
    sep = cfg["separator_thickness"]
    sw = rw + side_p * 2
    sh = top_h + sep + rh + sep + bot_h
    sheet = Image.new("RGB", (sw, sh), cfg["sheet_bg"])
    render_rgba = draw_watermarks(render.convert("RGBA"), cfg)
    sheet.paste(render_rgba.convert("RGB"), (side_p, top_h + sep))
    draw = ImageDraw.Draw(sheet)
    lc = cfg["separator_color"]
    draw.rectangle([0, top_h, sw, top_h + sep - 1], fill=lc)
    bsy = top_h + sep + rh
    draw.rectangle([0, bsy, sw, bsy + sep - 1], fill=lc)
    fh = load_font(cfg["heading_font_path"], cfg["heading_font_size"])
    hb = draw.textbbox((0, 0), cfg["heading_text"], font=fh)
    draw.text(
        (sw - (hb[2] - hb[0]) - 40, (top_h - (hb[3] - hb[1])) // 2),
        cfg["heading_text"],
        font=fh,
        fill=cfg["heading_color"],
    )
    draw_bottom_bar(draw, 0, bsy + sep, sw, bot_h, cfg, sheet)
    return sheet


def synthetic_render(w=1120, h=680):
    img = Image.new("RGB", (w, h))
    d = ImageDraw.Draw(img)
    for y in range(h):
        t = y / h
        r = int(100 + 80 * t)
        g = int(130 + 50 * t)
        b = int(160 + 30 * t)
        d.line([(0, y), (w, y)], fill=(r, g, b))
    return img


# ═══════════════════════════════════════════════════════════════
#  DEFAULT CONFIG
# ═══════════════════════════════════════════════════════════════

DEFAULT_CFG = {
    "input_folder": r"C:\PresSheet\input",
    "output_folder": r"C:\PresSheet\output",
    "heading_text": "Visuals...",
    "heading_font_path": r"C:\PresSheet\fonts\tekton.ttf",
    "heading_font_size": 72,
    "heading_color": (20, 20, 20),
    "watermark_text": "EXAMPLE DESIGN STUDIO",
    "watermark_separator": " | ",
    "watermark_positions": [0.33, 0.67],
    "watermark_font_path": r"C:\PresSheet\fonts\bankgothic.otf",
    "watermark_font_size": 26,
    "watermark_color": (255, 255, 255),
    "watermark_opacity": 140,
    "watermark_tracking": 8,
    "watermark_angle": 0,
    "watermark_x": 0,
    "fields": [
        {"label": "PROJECT", "value": "Resort Location"},
        {"label": "CLIENT", "value": "Client Name"},
        {"label": "ARCHITECTS", "value": "Project Architect"},
    ],
    "studio_role": "LANDSCAPE ARCHITECT",
    "studio_name": "Studio Name",
    "studio_sub": "Design Consultants",
    "studio_color": (74, 103, 65),
    "studio_sub_color": (74, 103, 65),
    "logo_path": r"C:\PresSheet\logo.png",
    "logo_size": (56, 56),
    "studio_font_path": r"C:\PresSheet\fonts\ltckennerley.ttf",
    "body_font_path": r"C:\PresSheet\fonts\gilroy.ttf",
    "body_font_bold": r"C:\PresSheet\fonts\gilroy-bold.ttf",
    "top_border_ratio": 0.095,
    "bottom_border_ratio": 0.095,
    "side_pad_ratio": 0,
    "sheet_bg": (255, 255, 255),
    "separator_color": (255, 255, 255),
    "separator_thickness": 2,
    "label_color": (160, 160, 160),
    "value_color": (20, 20, 20),
    "label_font_size": 18,
    "value_font_size": 26,
    "studio_role_size": 16,
    "studio_name_size": 38,
    "studio_sub_size": 18,
    "output_format": "",
    "jpeg_quality": 70,
    "overwrite": True,
}

# ═══════════════════════════════════════════════════════════════
#  THEME CONSTANTS  (Architectural drafting palette)
# ═══════════════════════════════════════════════════════════════

ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")

C_HEADER_BG = "#181816"  # graphite / drafting-table black
C_HEADER_FG = "#f4f2ec"  # paper white
C_SEC_BG = "#f4f2ec"  # section header sits flush on paper, no fill
C_SEC_FG = "#181816"
C_WIN_BG = "#eae7df"  # warm concrete / paper background
C_PANEL_BG = "#fbfaf6"  # panel interior, off-white paper
C_PANEL_BDR = "#cdc8ba"  # hairline border, like a drawn rule
C_SIDEBAR_BG = "#eae7df"
C_ROW_ALT = "#f1efe7"  # faint alternating row tint
C_LABEL_FG = "#7a7468"  # warm graphite gray
C_VALUE_FG = "#181816"  # near-black ink
C_BTN_PROC = "#181816"  # primary action — graphite
C_BTN_PREV = "#b5530c"  # ink-orange accent (drafting redline)
C_BTN_RESET = "#9a9486"
C_PROGRESS = "#b5530c"
C_LOG_BG = "#181816"  # command-line black, CAD console feel
C_LOG_FG = "#e3dfd3"
C_ACCENT = "#b5530c"  # single system accent
C_ACCENT_RED = "#a4322a"  # error/failed
C_ACCENT_GRN = "#4c7a4f"  # success — muted architectural green
FONT_UI = ("Consolas", 11)
FONT_LABEL = ("Consolas", 10)
FONT_SECTION = ("Consolas", 10, "bold")
FONT_HEADER = ("Consolas", 13, "bold")
FONT_MONO = ("Consolas", 10)


def spaced(text):
    return " ".join(text.upper())


# ═══════════════════════════════════════════════════════════════
#  REUSABLE WIDGETS
# ═══════════════════════════════════════════════════════════════


class SectionHeader(ctk.CTkFrame):
    """Title-block style section caption — letter-spaced label over a
    hairline rule, accent tick at the left, like a drawing sheet header."""

    def __init__(self, master, text, **kw):
        super().__init__(master, fg_color=C_SEC_BG, corner_radius=0, height=28, **kw)
        self.pack_propagate(False)
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="both", expand=True)
        ctk.CTkFrame(row, fg_color=C_ACCENT, width=3, corner_radius=0).pack(
            side="left", fill="y", padx=(0, 8), pady=4
        )
        ctk.CTkLabel(
            row,
            text=spaced(text),
            font=FONT_SECTION,
            text_color=C_SEC_FG,
            fg_color="transparent",
        ).pack(side="left", pady=4)
        rule = ctk.CTkFrame(self, fg_color=C_PANEL_BDR, height=1, corner_radius=0)
        rule.pack(fill="x", side="bottom")


class FieldRow(ctk.CTkFrame):
    """Label + Entry pair in a single row."""

    def __init__(
        self,
        master,
        label,
        default="",
        entry_width=220,
        browse=None,
        alt_row=False,
        **kw,
    ):
        bg = C_ROW_ALT if alt_row else C_PANEL_BG
        super().__init__(master, fg_color=bg, corner_radius=0, height=30, **kw)
        self.pack_propagate(False)
        ctk.CTkLabel(
            self,
            text=label,
            font=FONT_LABEL,
            text_color=C_LABEL_FG,
            width=170,
            anchor="w",
            fg_color="transparent",
        ).pack(side="left", padx=(10, 4), pady=4)
        self.var = ctk.StringVar(value=str(default))
        self._entry = ctk.CTkEntry(
            self,
            textvariable=self.var,
            width=entry_width,
            height=22,
            corner_radius=0,
            fg_color=C_PANEL_BG,
            border_color=C_PANEL_BDR,
            font=FONT_UI,
            text_color=C_VALUE_FG,
            border_width=1,
        )
        self._entry.pack(side="left", padx=(0, 4))
        if browse:
            ctk.CTkButton(
                self,
                text="...",
                width=28,
                height=22,
                corner_radius=0,
                fg_color="#e8e4d9",
                hover_color=C_PANEL_BDR,
                text_color=C_VALUE_FG,
                font=FONT_LABEL,
                command=browse,
            ).pack(side="left")

    def get(self):
        return self.var.get()

    def set(self, v):
        self.var.set(str(v))


class SliderRow(ctk.CTkFrame):
    def __init__(
        self, master, label, from_, to, default, integer=True, alt_row=False, **kw
    ):
        bg = C_ROW_ALT if alt_row else C_PANEL_BG
        super().__init__(master, fg_color=bg, corner_radius=0, height=30, **kw)
        self.pack_propagate(False)
        self.integer = integer
        ctk.CTkLabel(
            self,
            text=label,
            font=FONT_LABEL,
            text_color=C_LABEL_FG,
            width=170,
            anchor="w",
            fg_color="transparent",
        ).pack(side="left", padx=(10, 4), pady=4)
        self.var = ctk.DoubleVar(value=default)
        self.val_lbl = ctk.CTkLabel(
            self,
            text=str(default),
            width=38,
            font=FONT_LABEL,
            text_color=C_VALUE_FG,
            fg_color="transparent",
        )
        ctk.CTkSlider(
            self,
            from_=from_,
            to=to,
            variable=self.var,
            width=200,
            height=14,
            command=self._upd,
            button_color=C_ACCENT,
            button_hover_color=C_HEADER_BG,
            progress_color=C_ACCENT,
            fg_color="#d8d3c4",
        ).pack(side="left", padx=(0, 6))
        self.val_lbl.pack(side="left")

    def _upd(self, v):
        v = int(v) if self.integer else round(float(v), 2)
        self.val_lbl.configure(text=str(v))

    def get(self):
        v = self.var.get()
        if isinstance(v, (list, tuple)):
            v = v[0]
        return int(v) if self.integer else round(float(v), 3)


class ColorRow(ctk.CTkFrame):
    def __init__(self, master, label, default_rgb=(74, 103, 65), alt_row=False, **kw):
        bg = C_ROW_ALT if alt_row else C_PANEL_BG
        super().__init__(master, fg_color=bg, corner_radius=0, height=30, **kw)
        self.pack_propagate(False)
        self.rgb = default_rgb
        ctk.CTkLabel(
            self,
            text=label,
            font=FONT_LABEL,
            text_color=C_LABEL_FG,
            width=170,
            anchor="w",
            fg_color="transparent",
        ).pack(side="left", padx=(10, 4), pady=4)
        self.swatch = ctk.CTkButton(
            self,
            text="",
            width=52,
            height=20,
            corner_radius=0,
            fg_color=self._hex(default_rgb),
            hover_color=self._hex(default_rgb),
            border_width=1,
            border_color=C_PANEL_BDR,
            command=self._pick,
        )
        self.swatch.pack(side="left", padx=(0, 6))
        self.hex_lbl = ctk.CTkLabel(
            self,
            text=self._hex(default_rgb),
            font=("Courier New", 10),
            text_color=C_LABEL_FG,
            fg_color="transparent",
        )
        self.hex_lbl.pack(side="left")

    def _hex(self, rgb):
        return "#{:02x}{:02x}{:02x}".format(*rgb)

    def _pick(self):
        r = colorchooser.askcolor(color=self._hex(self.rgb), title="Pick color")
        if r[0]:
            self.rgb = tuple(int(x) for x in r[0])
            self.swatch.configure(
                fg_color=self._hex(self.rgb), hover_color=self._hex(self.rgb)
            )
            self.hex_lbl.configure(text=self._hex(self.rgb))

    def get(self):
        return self.rgb


class CheckRow(ctk.CTkFrame):
    def __init__(self, master, label, default=False, alt_row=False, **kw):
        bg = C_ROW_ALT if alt_row else C_PANEL_BG
        super().__init__(master, fg_color=bg, corner_radius=0, height=30, **kw)
        self.pack_propagate(False)
        ctk.CTkLabel(
            self,
            text=label,
            font=FONT_LABEL,
            text_color=C_LABEL_FG,
            width=170,
            anchor="w",
            fg_color="transparent",
        ).pack(side="left", padx=(10, 4), pady=4)
        self.var = ctk.BooleanVar(value=default)
        ctk.CTkCheckBox(
            self,
            variable=self.var,
            text="",
            checkbox_width=16,
            checkbox_height=16,
            fg_color=C_ACCENT,
            hover_color=C_HEADER_BG,
            border_color=C_PANEL_BDR,
            corner_radius=0,
        ).pack(side="left")

    def get(self):
        return self.var.get()


def panel(master, pady=(0, 8)):
    """White bordered panel container."""
    f = ctk.CTkFrame(
        master,
        fg_color=C_PANEL_BG,
        corner_radius=0,
        border_width=1,
        border_color=C_PANEL_BDR,
    )
    f.pack(fill="x", pady=pady, padx=0)
    return f


# ═══════════════════════════════════════════════════════════════
#  MAIN APPLICATION
# ═══════════════════════════════════════════════════════════════


class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("PresSheet — by Oliver")
        self.geometry("1200x800")
        self.minsize(1200, 800)
        # self.state("zoomed")
        self.after(10, lambda: self.state("zoomed"))
        self.configure(fg_color=C_WIN_BG)
        try:
            self.iconbitmap(resource_path("icon.ico"))
        except Exception:
            pass  # icon missing — fails silently
        self._preview_ref = None
        self._build()

    # ─── LAYOUT ─────────────────────────────────────────────────
    def _build(self):
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self._build_header()

        # Body row
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.grid(row=1, column=0, sticky="nsew", padx=10, pady=(6, 0))
        body.grid_columnconfigure(0, weight=1)
        body.grid_columnconfigure(1, minsize=300, weight=0)
        body.grid_rowconfigure(0, weight=1)

        self._build_settings(body)
        self._build_log_panel(body)
        self._build_statusbar()

    # ─── HEADER BAR ─────────────────────────────────────────────
    def _build_header(self):
        hdr = ctk.CTkFrame(self, fg_color=C_HEADER_BG, corner_radius=0, height=55)
        hdr.grid(row=0, column=0, sticky="ew")
        hdr.pack_propagate(False)

        ctk.CTkFrame(hdr, fg_color=C_ACCENT, width=4, corner_radius=0).pack(
            side="left", fill="y", padx=(0, 12)
        )

        ctk.CTkLabel(
            hdr,
            text=("Batch Sheet Generator 26.06"),
            font=("Consolas", 18, "bold"),
            text_color=C_HEADER_FG,
            fg_color="transparent",
            anchor="w",
        ).pack(side="left", pady=2)

        # Right-side header buttons
        for txt, cmd, col, outline in [
            ("PREVIEW", self._run_preview, "transparent", True),
            ("PROCESS", self._start_batch, C_ACCENT, False),
            ("RESET", self._reset, "transparent", True),
        ]:
            ctk.CTkButton(
                hdr,
                text=(txt),
                width=100,
                height=30,
                corner_radius=0,
                fg_color=col,
                hover_color=(self._darken(col) if col != "transparent" else "#2a2a26"),
                border_width=1 if outline else 0,
                border_color="#4a463c",
                font=("Consolas", 9, "bold"),
                text_color=C_HEADER_FG,
                command=cmd,
            ).pack(side="right", padx=(0, 8), pady=7)

    def _darken(self, hex_col):
        r, g, b = int(hex_col[1:3], 16), int(hex_col[3:5], 16), int(hex_col[5:7], 16)
        return "#{:02x}{:02x}{:02x}".format(
            max(0, r - 30), max(0, g - 30), max(0, b - 30)
        )

    # ─── LEFT SETTINGS PANEL ────────────────────────────────────
    def _build_settings(self, parent):
        outer = ctk.CTkFrame(parent, fg_color=C_WIN_BG, corner_radius=0)
        outer.grid(row=0, column=0, sticky="nsew", padx=(0, 8))

        scroll = ctk.CTkScrollableFrame(
            outer,
            fg_color=C_WIN_BG,
            corner_radius=0,
            scrollbar_button_color=C_PANEL_BDR,
            scrollbar_button_hover_color=C_SEC_BG,
        )
        scroll.pack(fill="both", expand=True)

        def sec(title, rows_fn):
            p = panel(scroll)
            SectionHeader(p, title).pack(fill="x")
            rows_fn(p)

        # ── Folders ──
        def folders(p):
            self.inp_folder = self._folder_row(
                p, "Input Folder", alt=True, default=DEFAULT_CFG["input_folder"]
            )
            self.out_folder = self._folder_row(
                p, "Output Folder", alt=True, default=DEFAULT_CFG["output_folder"]
            )

        sec("Folders", folders)

        # ── Heading ──
        def heading(p):
            self.heading_text = FieldRow(
                p, "Heading text", DEFAULT_CFG["heading_text"], entry_width=200
            )
            self.heading_text.pack(fill="x")
            self.heading_font = FieldRow(
                p,
                "Font path (.ttf)",
                DEFAULT_CFG["heading_font_path"],
                entry_width=280,
                browse=lambda: self._browse_font(self.heading_font),
                alt_row=True,
            )
            self.heading_font.pack(fill="x")
            self.heading_size = SliderRow(
                p, "Font size", 36, 120, DEFAULT_CFG["heading_font_size"], alt_row=False
            )
            self.heading_size.pack(fill="x")
            self.heading_color = ColorRow(
                p, "Color", DEFAULT_CFG["heading_color"], alt_row=True
            )
            self.heading_color.pack(fill="x")

        sec('Top-Right Heading  ("Visuals...")', heading)

        # ── Watermark ──
        def wm(p):
            self.wm_text = FieldRow(
                p, "Watermark text", DEFAULT_CFG["watermark_text"], entry_width=240
            )
            self.wm_text.pack(fill="x")
            self.wm_sep = FieldRow(
                p,
                "Separator",
                DEFAULT_CFG["watermark_separator"],
                entry_width=100,
                alt_row=True,
            )
            self.wm_sep.pack(fill="x")
            self.wm_pos1 = SliderRow(
                p, "Strip 1 position", 0.1, 0.9, 0.33, integer=False
            )
            self.wm_pos1.pack(fill="x")
            self.wm_pos2 = SliderRow(
                p, "Strip 2 position", 0.1, 0.9, 0.67, integer=False, alt_row=True
            )
            self.wm_pos2.pack(fill="x")

            self.watermark_font = FieldRow(
                p,
                "Font path (.ttf)",
                DEFAULT_CFG["watermark_font_path"],
                entry_width=280,
                browse=lambda: self._browse_font(self.watermark_font),
                alt_row=True,
            )
            self.watermark_font.pack(fill="x")

            self.wm_size = SliderRow(
                p, "Font size", 14, 48, DEFAULT_CFG["watermark_font_size"]
            )
            self.wm_size.pack(fill="x")
            self.wm_opacity = SliderRow(
                p,
                "Opacity (0–255)",
                0,
                255,
                DEFAULT_CFG["watermark_opacity"],
                alt_row=True,
            )
            self.wm_opacity.pack(fill="x")
            self.wm_track = SliderRow(
                p, "Letter spacing", 0, 30, DEFAULT_CFG["watermark_tracking"]
            )
            self.wm_track.pack(fill="x")
            self.wm_x = SliderRow(
                p,
                "X offset (0=left)",
                0.0,
                0.9,
                DEFAULT_CFG["watermark_x"],
                integer=False,
                alt_row=True,
            )
            self.wm_x.pack(fill="x")

        sec("Watermark Strips", wm)

        # ── Project fields ──
        def proj(p):
            self.field_rows = []
            for i, field in enumerate(DEFAULT_CFG["fields"]):
                row = ctk.CTkFrame(
                    p,
                    fg_color=C_ROW_ALT if i % 2 else C_PANEL_BG,
                    corner_radius=0,
                    height=30,
                )
                row.pack(fill="x")
                row.pack_propagate(False)
                ctk.CTkLabel(
                    row,
                    text="Label",
                    font=FONT_LABEL,
                    text_color=C_LABEL_FG,
                    width=60,
                    anchor="w",
                    fg_color="transparent",
                ).pack(side="left", padx=(10, 2), pady=4)
                lvar = ctk.StringVar(value=field["label"])
                le = ctk.CTkEntry(
                    row,
                    textvariable=lvar,
                    width=100,
                    height=22,
                    corner_radius=0,
                    fg_color=C_PANEL_BG,
                    border_color=C_PANEL_BDR,
                    font=FONT_UI,
                    text_color=C_VALUE_FG,
                    border_width=1,
                )
                le.pack(side="left", padx=(0, 10))
                ctk.CTkLabel(
                    row,
                    text="Value",
                    font=FONT_LABEL,
                    text_color=C_LABEL_FG,
                    width=40,
                    anchor="w",
                    fg_color="transparent",
                ).pack(side="left", padx=(0, 2))
                vvar = ctk.StringVar(value=field["value"])
                ve = ctk.CTkEntry(
                    row,
                    textvariable=vvar,
                    width=240,
                    height=22,
                    corner_radius=0,
                    fg_color=C_PANEL_BG,
                    border_color=C_PANEL_BDR,
                    font=FONT_UI,
                    text_color=C_VALUE_FG,
                    border_width=1,
                )
                ve.pack(side="left")

                class Pair:
                    def __init__(s, lv, vv):
                        s.lv = lv
                        s.vv = vv

                    def get(s):
                        return s.lv.get(), s.vv.get()

                self.field_rows.append(Pair(lvar, vvar))

        sec("Project Info  —  Bottom Left", proj)

        # ── Studio ──
        def studio(p):
            self.studio_role = FieldRow(
                p, "Role label", DEFAULT_CFG["studio_role"], entry_width=200
            )
            self.studio_role.pack(fill="x")
            self.studio_name = FieldRow(
                p,
                "Studio name",
                DEFAULT_CFG["studio_name"],
                entry_width=200,
                alt_row=True,
            )
            self.studio_name.pack(fill="x")
            self.studio_sub = FieldRow(
                p, "Subtitle", DEFAULT_CFG["studio_sub"], entry_width=200
            )
            self.studio_sub.pack(fill="x")
            self.studio_color = ColorRow(
                p, "Brand color", DEFAULT_CFG["studio_color"], alt_row=True
            )
            self.studio_color.pack(fill="x")
            self.studio_sub_color = ColorRow(
                p, "Subtitle color", DEFAULT_CFG["studio_sub_color"]
            )
            self.studio_sub_color.pack(fill="x")
            self.studio_font = FieldRow(
                p,
                "Studio font (.ttf)",
                DEFAULT_CFG["studio_font_path"],
                entry_width=220,
                browse=lambda: self._browse_font(self.studio_font),
            )
            self.studio_font.pack(fill="x")
            self.logo_path = FieldRow(
                p,
                "Logo PNG path",
                DEFAULT_CFG["logo_path"],
                entry_width=220,
                alt_row=True,
                browse=self._browse_logo,
            )
            self.logo_path.pack(fill="x")

        sec("Studio Block  —  Bottom Right", studio)

        # ── Fonts ──
        def fonts(p):
            self.body_font = FieldRow(
                p,
                "Body regular",
                DEFAULT_CFG["body_font_path"],
                entry_width=280,
                browse=lambda: self._browse_font(self.body_font),
            )
            self.body_font.pack(fill="x")
            self.body_font_bold = FieldRow(
                p,
                "Body bold",
                DEFAULT_CFG["body_font_bold"],
                entry_width=280,
                alt_row=True,
                browse=lambda: self._browse_font(self.body_font_bold),
            )
            self.body_font_bold.pack(fill="x")

        sec("Body Fonts", fonts)

        # ── Sheet style ──
        def style(p):
            self.top_ratio = SliderRow(
                p,
                "Top border size",
                0.03,
                0.20,
                DEFAULT_CFG["top_border_ratio"],
                integer=False,
            )
            self.top_ratio.pack(fill="x")
            self.bot_ratio = SliderRow(
                p,
                "Bottom bar size",
                0.04,
                0.20,
                DEFAULT_CFG["bottom_border_ratio"],
                integer=False,
                alt_row=True,
            )
            self.bot_ratio.pack(fill="x")
            self.sep_thick = SliderRow(
                p, "Separator thickness", 1, 6, DEFAULT_CFG["separator_thickness"]
            )
            self.sep_thick.pack(fill="x")
            self.sep_color = ColorRow(
                p, "Separator color", DEFAULT_CFG["separator_color"], alt_row=True
            )
            self.sep_color.pack(fill="x")
            self.label_color = ColorRow(
                p, "Label text color", DEFAULT_CFG["label_color"]
            )
            self.label_color.pack(fill="x")
            self.value_color = ColorRow(
                p, "Value text color", DEFAULT_CFG["value_color"], alt_row=True
            )
            self.value_color.pack(fill="x")

        sec("Sheet Style", style)

        # ── Output ──
        def output(p):
            self.out_fmt = FieldRow(
                p,
                "Format (jpg / png / '')",
                DEFAULT_CFG["output_format"],
                entry_width=80,
            )
            self.out_fmt.pack(fill="x")
            self.jpeg_qual = SliderRow(
                p, "JPEG quality", 60, 100, DEFAULT_CFG["jpeg_quality"], alt_row=True
            )
            self.jpeg_qual.pack(fill="x")
            self.overwrite = CheckRow(p, "Overwrite existing files")
            self.overwrite.pack(fill="x")

        sec("Output", output)

    def _folder_row(self, parent, label, alt=False, default=""):
        """Special folder row with Browse returning directory."""
        bg = C_ROW_ALT if alt else C_PANEL_BG
        f = ctk.CTkFrame(parent, fg_color=bg, corner_radius=0, height=30)
        f.pack(fill="x")
        f.pack_propagate(False)
        ctk.CTkLabel(
            f,
            text=label,
            font=FONT_LABEL,
            text_color=C_LABEL_FG,
            width=110,
            anchor="w",
            fg_color="transparent",
        ).pack(side="left", padx=(10, 4), pady=4)
        var = ctk.StringVar(value=default)
        ctk.CTkEntry(
            f,
            textvariable=var,
            width=320,
            height=22,
            corner_radius=0,
            fg_color=C_PANEL_BG,
            border_color=C_PANEL_BDR,
            font=FONT_UI,
            text_color=C_VALUE_FG,
            border_width=1,
        ).pack(side="left", padx=(0, 4))
        ctk.CTkButton(
            f,
            text="...",
            width=28,
            height=22,
            corner_radius=0,
            fg_color="#e8e4d9",
            hover_color=C_PANEL_BDR,
            text_color=C_VALUE_FG,
            font=FONT_LABEL,
            command=lambda v=var: v.set(filedialog.askdirectory() or v.get()),
        ).pack(side="left")
        f.var = var
        return f

    # ─── RIGHT LOG PANEL ────────────────────────────────────────
    def _build_log_panel(self, parent):
        outer = ctk.CTkFrame(
            parent,
            fg_color=C_PANEL_BG,
            corner_radius=0,
            border_width=1,
            border_color=C_PANEL_BDR,
        )
        outer.grid(row=0, column=1, sticky="nsew")
        outer.grid_rowconfigure(2, weight=1)
        outer.grid_columnconfigure(0, weight=1)

        # Section header
        SectionHeader(outer, "Logs").grid(row=0, column=0, sticky="ew")

        # Stats strip
        stats = ctk.CTkFrame(
            outer, fg_color="#f1efe7", corner_radius=0, border_width=0, height=58
        )
        stats.grid(row=1, column=0, sticky="ew")
        stats.grid_propagate(False)
        stats.grid_columnconfigure((0, 1, 2, 3), weight=1)

        def stat_cell(col, label, init="—", color=C_VALUE_FG):
            f = ctk.CTkFrame(stats, fg_color="transparent")
            f.grid(row=0, column=col, padx=4, pady=6, sticky="nsew")
            v = ctk.CTkLabel(
                f,
                text=init,
                font=("Consolas", 18, "bold"),
                text_color=color,
                fg_color="transparent",
            )
            v.pack()
            ctk.CTkLabel(
                f,
                text=label,
                font=("Consolas", 8),
                text_color=C_LABEL_FG,
                fg_color="transparent",
            ).pack()
            return v

        self.stat_total = stat_cell(0, "TOTAL")
        self.stat_done = stat_cell(1, "DONE", color=C_ACCENT_GRN)
        self.stat_skipped = stat_cell(2, "SKIP", color="#e67e22")
        self.stat_failed = stat_cell(3, "FAILED", color=C_ACCENT_RED)

        # Log text box
        self.log_box = ctk.CTkTextbox(
            outer,
            fg_color=C_LOG_BG,
            corner_radius=0,
            font=FONT_MONO,
            text_color=C_LOG_FG,
            border_width=0,
            wrap="word",
        )
        self.log_box.grid(row=2, column=0, sticky="nsew", padx=0, pady=0)

        # Log controls
        ctrl = ctk.CTkFrame(outer, fg_color="#f1efe7", corner_radius=0, height=36)
        ctrl.grid(row=3, column=0, sticky="ew")
        ctrl.grid_propagate(False)
        ctk.CTkButton(
            ctrl,
            text="Clear Log",
            width=90,
            height=24,
            corner_radius=0,
            fg_color="#e8e4d9",
            hover_color=C_PANEL_BDR,
            text_color=C_VALUE_FG,
            font=FONT_LABEL,
            command=lambda: self.log_box.delete("1.0", "end"),
        ).pack(side="right", padx=8, pady=6)
        self.log_time = ctk.CTkLabel(
            ctrl,
            text="",
            font=("Consolas", 9),
            text_color=C_LABEL_FG,
            fg_color="transparent",
        )
        self.log_time.pack(side="left", padx=8)

    # ─── BOTTOM STATUS BAR ──────────────────────────────────────
    def _build_statusbar(self):
        bar = ctk.CTkFrame(self, fg_color="#d8d3c4", corner_radius=0, height=44)
        bar.grid(row=2, column=0, sticky="ew")
        bar.grid_propagate(False)
        bar.grid_columnconfigure(0, weight=1)

        self.progress = ctk.CTkProgressBar(
            bar,
            height=12,
            corner_radius=0,
            progress_color=C_PROGRESS,
            fg_color=C_PANEL_BDR,
        )
        self.progress.set(0)
        self.progress.grid(row=0, column=0, sticky="ew", padx=(10, 10), pady=(8, 2))
        self.prog_lbl = ctk.CTkLabel(
            bar,
            text="Ready",
            font=("Consolas", 9),
            text_color=C_LABEL_FG,
            fg_color="transparent",
        )
        self.prog_lbl.grid(row=1, column=0, sticky="w", padx=12, pady=(0, 4))

    # ─── HELPERS ────────────────────────────────────────────────
    def _browse_font(self, target_row):
        p = filedialog.askopenfilename(
            filetypes=[("Font files", "*.ttf *.otf"), ("All", "*.*")]
        )
        if p:
            target_row.set(p)

    def _browse_logo(self):
        p = filedialog.askopenfilename(
            filetypes=[("PNG files", "*.png"), ("All", "*.*")]
        )
        if p:
            self.logo_path.set(p)

    def _reset(self):
        if messagebox.askyesno("Reset", "Reset all fields to defaults?"):
            self.destroy()
            App().mainloop()

    def _collect_cfg(self):
        cfg = copy.deepcopy(DEFAULT_CFG)
        cfg["input_folder"] = self.inp_folder.var.get()
        cfg["output_folder"] = self.out_folder.var.get()
        cfg["heading_text"] = self.heading_text.get()
        cfg["heading_font_path"] = self.heading_font.get()
        cfg["heading_font_size"] = self.heading_size.get()
        cfg["heading_color"] = self.heading_color.get()
        cfg["watermark_text"] = self.wm_text.get()
        cfg["watermark_separator"] = self.wm_sep.get()
        cfg["watermark_positions"] = [self.wm_pos1.get(), self.wm_pos2.get()]
        cfg["watermark_font_path"] = self.watermark_font.get()
        cfg["watermark_font_size"] = self.wm_size.get()
        cfg["watermark_opacity"] = self.wm_opacity.get()
        cfg["watermark_tracking"] = self.wm_track.get()
        cfg["watermark_x"] = float(self.wm_x.get())
        cfg["fields"] = [
            {"label": l, "value": v} for l, v in [p.get() for p in self.field_rows]
        ]
        cfg["studio_role"] = self.studio_role.get()
        cfg["studio_name"] = self.studio_name.get()
        cfg["studio_sub"] = self.studio_sub.get()
        cfg["studio_color"] = self.studio_color.get()
        cfg["studio_sub_color"] = self.studio_sub_color.get()
        cfg["studio_font_path"] = self.studio_font.get()
        cfg["logo_path"] = self.logo_path.get()
        cfg["body_font_path"] = self.body_font.get()
        cfg["body_font_bold"] = self.body_font_bold.get()
        cfg["top_border_ratio"] = self.top_ratio.get()
        cfg["bottom_border_ratio"] = self.bot_ratio.get()
        cfg["separator_thickness"] = self.sep_thick.get()
        cfg["separator_color"] = self.sep_color.get()
        cfg["label_color"] = self.label_color.get()
        cfg["value_color"] = self.value_color.get()
        cfg["output_format"] = self.out_fmt.get()
        cfg["jpeg_quality"] = self.jpeg_qual.get()
        cfg["overwrite"] = self.overwrite.get()
        return cfg

    # ─── PREVIEW ────────────────────────────────────────────────
    def _run_preview(self):
        cfg = self._collect_cfg()
        threading.Thread(target=self._preview_worker, args=(cfg,), daemon=True).start()

    def _preview_worker(self, cfg):
        try:
            src = None
            inp = Path(cfg["input_folder"])
            if inp.exists():
                for f in inp.iterdir():
                    if f.suffix.lower() in SUPPORTED_EXT:
                        src = f
                        break
            render = Image.open(src) if src else synthetic_render()
            sheet = build_sheet(render, cfg)
            # Show in popup window
            self.after(0, self._show_preview_window, sheet)
        except Exception as e:
            self.after(0, lambda: messagebox.showerror("Preview error", str(e)))

    def _show_preview_window(self, sheet):
        win = ctk.CTkToplevel(self)
        win.title("Sheet Preview")
        win.configure(fg_color=C_WIN_BG)
        win.grab_set()

        # Header
        hdr = ctk.CTkFrame(win, fg_color=C_HEADER_BG, corner_radius=0, height=36)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        ctk.CTkLabel(
            hdr,
            text=f"  Preview  —  sheet {sheet.size[0]}×{sheet.size[1]}px",
            font=FONT_HEADER,
            text_color=C_HEADER_FG,
            fg_color="transparent",
        ).pack(side="left", pady=6)
        ctk.CTkButton(
            hdr,
            text="Close",
            width=70,
            height=24,
            corner_radius=0,
            fg_color=C_BTN_RESET,
            command=win.destroy,
        ).pack(side="right", padx=8, pady=6)

        sheet.thumbnail((1000, 680), Image.LANCZOS)
        img_ref = ctk.CTkImage(light_image=sheet, dark_image=sheet, size=sheet.size)
        self._preview_ref = img_ref
        lbl = ctk.CTkLabel(win, image=img_ref, text="", fg_color="#111")
        lbl.pack(padx=10, pady=10)

    # ─── BATCH ──────────────────────────────────────────────────
    def _start_batch(self):
        cfg = self._collect_cfg()
        if not cfg["input_folder"]:
            messagebox.showwarning("Missing", "Set an input folder first.")
            return
        if not cfg["output_folder"]:
            messagebox.showwarning("Missing", "Set an output folder first.")
            return
        self.log_box.delete("1.0", "end")
        self.progress.set(0)
        threading.Thread(target=self._batch_worker, args=(cfg,), daemon=True).start()

    def _batch_worker(self, cfg):
        inp = Path(cfg["input_folder"])
        out = Path(cfg["output_folder"])
        out.mkdir(parents=True, exist_ok=True)
        images = [
            f
            for f in inp.iterdir()
            if f.is_file() and f.suffix.lower() in SUPPORTED_EXT
        ]
        total = len(images)
        self.after(0, self.stat_total.configure, {"text": str(total)})
        self._log(f"Starting  •  {total} image(s) found\n{'─'*34}")
        if not images:
            self._log("No supported images found.")
            return

        success = skipped = failed = 0
        start_t = datetime.now()

        for i, img_path in enumerate(images, 1):
            ext = (
                cfg["output_format"].lstrip(".")
                if cfg["output_format"]
                else img_path.suffix.lstrip(".")
            )
            out_path = out / f"{img_path.stem}_sheet.{ext}"

            if out_path.exists() and not cfg["overwrite"]:
                self._log(f"  SKIP   {img_path.name}")
                skipped += 1
            else:
                try:
                    sheet = build_sheet(img_path, cfg)
                    kw = {}
                    if ext.lower() in ("jpg", "jpeg"):
                        kw = {
                            "quality": cfg["jpeg_quality"],
                            "optimize": True,
                            "subsampling": 0,
                        }
                    sheet.save(out_path, **kw)
                    self._log(f"  ✓  {img_path.name}")
                    success += 1
                except Exception as e:
                    self._log(f"  ✗  {img_path.name}\n     {e}")
                    failed += 1

            pct = i / total
            self.after(0, self.progress.set, pct)
            self.after(
                0,
                self.prog_lbl.configure,
                {"text": f"Processing  {i}/{total}  ({int(pct*100)}%)"},
            )
            self.after(0, self.stat_done.configure, {"text": str(success)})
            self.after(0, self.stat_skipped.configure, {"text": str(skipped)})
            self.after(0, self.stat_failed.configure, {"text": str(failed)})

        elapsed = (datetime.now() - start_t).seconds
        self._log(
            f"{'─'*34}\nDone  ✓{success}  skip {skipped}  ✗{failed}  [{elapsed}s]"
        )
        self.after(
            0, self.prog_lbl.configure, {"text": f"Done  —  {success} sheets saved"}
        )
        self.after(
            0,
            self.log_time.configure,
            {"text": f"Last run: {datetime.now().strftime('%H:%M:%S')}"},
        )

    def _log(self, msg):
        self.after(0, self._append_log, msg + "\n")

    def _append_log(self, msg):
        self.log_box.insert("end", msg)
        self.log_box.see("end")


if __name__ == "__main__":
    app = App()
    app.mainloop()

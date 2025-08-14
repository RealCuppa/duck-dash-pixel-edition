import tkinter as tk
from tkinter import messagebox, simpledialog
import random
import time
import json
import os
import math
import tempfile
import atexit

# Optional: background music via pygame.mixer (auto-disabled if pygame not installed)
try:
    import pygame
    PYGAME_AVAILABLE = True
except Exception:
    PYGAME_AVAILABLE = False

"""
Duck Dash — Pixel Edition (Single File)
--------------------------------------
• Pixel-art UI (Mario-esque world) + Minecraft-y block look
• Start Menu, Instructions, Settings, Leaderboard
• Chiptune-style background music (procedurally generated, no external files)
• Uses your dict-style movement: alien_0 = { 'x_position', 'y_position', 'speed' }
• Click the duck to score; 60-second rounds; leaderboard saved to leaderboard.json

Dependencies: Tkinter (standard), optional pygame (for music)
Run: python duck_dash_pixel.py
"""

LEADERBOARD_FILE = "leaderboard.json"
GAME_SECONDS = 60
WINDOW_W, WINDOW_H = 960, 560
GROUND_Y = 440

# Difficulty presets affect base speed mapping
DIFFICULTY_PRESETS = {
    "Easy":  {"slow": 1, "medium": 2, "fast": 3},
    "Normal":{"slow": 2, "medium": 3, "fast": 4},
    "Hard":  {"slow": 3, "medium": 4, "fast": 5}
}

DEFAULT_SETTINGS = {
    "music_on": True,
    "difficulty": "Normal",
    "pixel_size": 4
}

# ---------------- Pixel Art Definitions ---------------- #
# Simple pixel maps using characters to represent colors.
# '.' = transparent
# Colors map below in PALETTE

DUCK_PIX = [
    "................",
    ".....YYYYYY.....",
    "...YYYYYYYYYY...",
    "..YYYYYYYYYYYY..",
    ".YYYYYYOYYYYYYY.",
    ".YYYYOOOYYYYYYY.",
    "..YYYYYYYYYYYY..",
    "....YYYBYYY.....",
    "......YBY.......",
    ".......Y........",
    "................",
]

PIPE_PIX = [
    "GGGGGGGGGGGGGGGG",
    "GGGGGGGGGGGGGGGG",
    "GGGGGGGGGGGGGGGG",
    "GGGGGGGGGGGGGGGG",
    "GGGGGGGGGGGGGGGG",
    "GGGGGGGGGGGGGGGG",
]

BUSH_PIX = [
    "..gggggggggg..",
    ".gggggggggggg.",
    "gggggggggggggg",
    ".gggggggggggg.",
    "..gggggggggg..",
]

CLOUD_PIX = [
    "....wwwww....",
    "..wwwwwwwww..",
    ".wwwwwwwwwww.",
    "..wwwwwwwww..",
    "....wwwww....",
]

BLOCK_PIX = [
    "RRRRRRRR",
    "R..R..RR",
    "RRRRRRRR",
    "R..RR..R",
    "RRRRRRRR",
]

SUN_PIX = [
    "..OOO..",
    ".OOOOO.",
    "OOOOOOO",
    ".OOOOO.",
    "..OOO..",
]

PALETTE = {
    'Y': "#f4d03f",  # duck yellow
    'O': "#f39c12",  # beak/orange
    'B': "#6d4c41",  # brown (wing detail)
    'G': "#388e3c",  # pipe green
    'g': "#66bb6a",  # bush light green
    'w': "#ffffff",  # cloud white
    'R': "#b5651d",  # block brick
}

SKY_COLORS = ["#9be7ff", "#8fd8ff", "#84caff", "#79bcff"]
WATER_COLOR = "#64b5f6"
GROUND_COLOR = "#4db6ac"

# ---------------- Utility ---------------- #

def load_leaderboard():
    if not os.path.exists(LEADERBOARD_FILE):
        return []
    try:
        with open(LEADERBOARD_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return data
        return []
    except Exception:
        return []


def save_leaderboard(entries):
    try:
        with open(LEADERBOARD_FILE, "w", encoding="utf-8") as f:
            json.dump(entries[:20], f, indent=2)
    except Exception:
        pass


def add_score_to_leaderboard(name, score):
    entries = load_leaderboard()
    entries.append({"name": name or "Player", "score": int(score)})
    entries.sort(key=lambda e: e["score"], reverse=True)
    save_leaderboard(entries)


# Procedurally generate a short chiptune-like loop and return a temp filename
# Uses simple square wave notes.

def generate_chiptune_wav(duration_sec=8, bpm=140):
    try:
        import wave
        import struct
        sr = 22050
        temp = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
        fname = temp.name
        temp.close()

        melody = [
            523.25, 523.25, 659.25, 523.25, 0, 523.25,
            587.33, 659.25, 587.33, 523.25, 0, 392.00,
            440.00, 523.25, 440.00, 392.00, 0, 349.23,
        ]
        beat = 60.0 / bpm
        note_len = beat * 0.5  # eighth notes

        samples = []
        for freq in melody:
            length = int(sr * note_len)
            for i in range(length):
                if freq <= 0:
                    samples.append(0)
                else:
                    # square wave
                    t = i / sr
                    val = 0.3 if math.sin(2*math.pi*freq*t) >= 0 else -0.3
                    samples.append(val)
        # pad/loop fill to duration
        total_len = int(sr * duration_sec)
        while len(samples) < total_len:
            samples.extend(samples)
        samples = samples[:total_len]

        with wave.open(fname, 'w') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sr)
            frames = b''.join([struct.pack('<h', int(s*32767)) for s in samples])
            wf.writeframes(frames)
        return fname
    except Exception:
        return None


# --------------- Main Game Class ---------------- #

class DuckDashPixel:
    def __init__(self, root):
        self.root = root
        self.root.title("Duck Dash — Pixel Edition")
        self.root.geometry(f"{WINDOW_W}x{WINDOW_H}")
        self.root.resizable(False, False)

        # State
        self.settings = DEFAULT_SETTINGS.copy()
        self.score = 0
        self.game_over = False
        self.start_time = 0.0
        self.speed_map = DIFFICULTY_PRESETS[self.settings["difficulty"]].copy()

        # Your dict-style movement state
        self.alien_0 = {'x_position': 60, 'y_position': GROUND_Y - 52, 'speed': 'slow'}
        self.vx_extra = 0.0
        self.vy = 0.4
        self.vy_dir = 1

        # Music
        self._music_file = None
        self._music_init()

        # Top HUD
        self.hud = tk.Frame(root, bg="#0a2540")
        self.hud.pack(fill=tk.X)
        self.score_var = tk.StringVar()
        self.time_var = tk.StringVar()
        self.speed_var = tk.StringVar()
        tk.Label(self.hud, textvariable=self.score_var, fg="white", bg="#0a2540", font=("Helvetica", 12, "bold")).pack(side=tk.LEFT, padx=10, pady=6)
        tk.Label(self.hud, textvariable=self.time_var, fg="white", bg="#0a2540", font=("Helvetica", 12, "bold")).pack(side=tk.LEFT, padx=10)
        tk.Label(self.hud, textvariable=self.speed_var, fg="white", bg="#0a2540", font=("Helvetica", 12, "bold")).pack(side=tk.LEFT, padx=10)
        tk.Button(self.hud, text="Main Menu", command=self.show_menu).pack(side=tk.RIGHT, padx=10)

        # Screens
        self.container = tk.Frame(root)
        self.container.pack(fill=tk.BOTH, expand=True)

        self.menu_frame = tk.Frame(self.container, bg="#74c0fc")
        self.instructions_frame = tk.Frame(self.container, bg="#74c0fc")
        self.settings_frame = tk.Frame(self.container, bg="#74c0fc")
        self.leaderboard_frame = tk.Frame(self.container, bg="#74c0fc")
        self.game_canvas = tk.Canvas(self.container, width=WINDOW_W, height=WINDOW_H-40, bg="#87cefa", highlightthickness=0)

        self._build_menu()
        self._build_instructions()
        self._build_settings()
        self._build_leaderboard()

        self.bindings()
        self.show_menu()

    # ------------- Music ------------- #
    def _music_init(self):
        if not PYGAME_AVAILABLE:
            return
        try:
            pygame.mixer.init()
            self._music_file = generate_chiptune_wav()
            if self._music_file and self.settings["music_on"]:
                pygame.mixer.music.load(self._music_file)
                # ensure temp file cleaned up on exit
                atexit.register(lambda: os.path.exists(self._music_file) and os.remove(self._music_file))
        except Exception:
            pass

    def _music_play(self):
        if not PYGAME_AVAILABLE or not self._music_file:
            return
        if self.settings["music_on"]:
            try:
                pygame.mixer.music.play(-1)
            except Exception:
                pass

    def _music_stop(self):
        if not PYGAME_AVAILABLE:
            return
        try:
            pygame.mixer.music.stop()
        except Exception:
            pass

    # ------------- UI Screens ------------- #
    def _clear_container(self):
        for w in self.container.winfo_children():
            w.pack_forget()

    def _pixel_title(self, parent, text):
        return tk.Label(parent, text=text, font=("Courier New", 22, "bold"), bg="#74c0fc")

    def _build_menu(self):
        self.menu_frame.configure(bg="#74c0fc")
        for w in self.menu_frame.winfo_children():
            w.destroy()
        # Decorative canvas background
        c = tk.Canvas(self.menu_frame, width=WINDOW_W, height=WINDOW_H-40, bg="#87ceeb", highlightthickness=0)
        c.pack(fill=tk.BOTH, expand=True)
        self._draw_sky(c)
        self._draw_ground(c)
        self._draw_clouds(c)
        self._draw_pipes(c)

        # Overlay panel
        panel = tk.Frame(c, bg="#ffffff", bd=0, highlightthickness=0)
        c.create_window(WINDOW_W//2, 180, window=panel)
        self._pixel_title(panel, "Duck Dash — Pixel Edition").pack(pady=8)
        for text, cmd in [
            ("Start Game", self.start_game),
            ("Instructions", self.show_instructions),
            ("Settings", self.show_settings),
            ("Leaderboard", self.show_leaderboard),
            ("Quit", self.root.destroy)
        ]:
            tk.Button(panel, text=text, width=20, height=1, command=cmd).pack(pady=6)

    def _build_instructions(self):
        for w in self.instructions_frame.winfo_children():
            w.destroy()
        self._pixel_title(self.instructions_frame, "Instructions").pack(pady=10)
        text = (
            """• Click the duck to score
• Avoid obstacles
• Score as much as possible before time runs out"""
        )
        tk.Label(self.instructions_frame, text=text, bg="#74c0fc", font=("Courier New", 12)).pack(pady=6)
        tk.Button(self.instructions_frame, text="Back", command=self.show_menu).pack(pady=10)

    def _build_settings(self):
        for w in self.settings_frame.winfo_children():
            w.destroy()
        self._pixel_title(self.settings_frame, "Settings").pack(pady=10)

        # Music toggle
        music_var = tk.BooleanVar(value=self.settings["music_on"])
        def toggle_music():
            self.settings["music_on"] = music_var.get()
            if self.settings["music_on"]:
                self._music_play()
            else:
                self._music_stop()
        tk.Checkbutton(self.settings_frame, text="Music ON", variable=music_var, command=toggle_music, bg="#74c0fc").pack(pady=6)

        # Difficulty
        tk.Label(self.settings_frame, text="Difficulty:", bg="#74c0fc", font=("Courier New", 12, "bold")).pack(pady=(12,4))
        diff_var = tk.StringVar(value=self.settings["difficulty"])
        def set_diff():
            self.settings["difficulty"] = diff_var.get()
            self.speed_map = DIFFICULTY_PRESETS[self.settings["difficulty"]].copy()
        for d in DIFFICULTY_PRESETS.keys():
            tk.Radiobutton(self.settings_frame, text=d, value=d, variable=diff_var, command=set_diff, bg="#74c0fc").pack(anchor="w", padx=50)

        # Pixel size
        tk.Label(self.settings_frame, text="Pixel Size:", bg="#74c0fc", font=("Courier New", 12, "bold")).pack(pady=(12,4))
        ps = tk.Scale(self.settings_frame, from_=2, to=8, orient=tk.HORIZONTAL, bg="#74c0fc", highlightthickness=0)
        ps.set(self.settings["pixel_size"])
        def change_ps(val):
            self.settings["pixel_size"] = int(float(val))
        ps.configure(command=change_ps)
        ps.pack(pady=6)

        tk.Button(self.settings_frame, text="Back", command=self.show_menu).pack(pady=10)

    def _build_leaderboard(self):
        for w in self.leaderboard_frame.winfo_children():
            w.destroy()
        self._pixel_title(self.leaderboard_frame, "Leaderboard (Top 10)").pack(pady=10)
        entries = load_leaderboard()[:10]
        if not entries:
            tk.Label(self.leaderboard_frame, text="No scores yet.", bg="#74c0fc").pack(pady=10)
        else:
            for i, e in enumerate(entries, 1):
                tk.Label(self.leaderboard_frame, text=f"{i:2d}. {e['name']} — {e['score']}", bg="#74c0fc", font=("Courier New", 12)).pack(anchor="w", padx=40)
        tk.Button(self.leaderboard_frame, text="Back", command=self.show_menu).pack(pady=12)

    # ------------- Navigation ------------- #
    def show_menu(self):
        self._music_stop()
        self._clear_container()
        self.menu_frame.pack(fill=tk.BOTH, expand=True)
        self._build_menu()
        self._update_hud()  # keep HUD synced

    def show_instructions(self):
        self._clear_container()
        self.instructions_frame.pack(fill=tk.BOTH, expand=True)
        self._build_instructions()
        self._update_hud()

    def show_settings(self):
        self._clear_container()
        self.settings_frame.pack(fill=tk.BOTH, expand=True)
        self._build_settings()
        self._update_hud()

    def show_leaderboard(self):
        self._clear_container()
        self.leaderboard_frame.pack(fill=tk.BOTH, expand=True)
        self._build_leaderboard()
        self._update_hud()

    # ------------- Game ------------- #
    def start_game(self):
        self._clear_container()
        self.game_canvas.pack(fill=tk.BOTH, expand=True)
        self.score = 0
        self.game_over = False
        self.start_time = time.time()
        self.alien_0['x_position'] = 60
        self.alien_0['y_position'] = GROUND_Y - 52
        self.alien_0['speed'] = 'slow'
        self.vx_extra = 0.0
        self.vy = 0.4
        self.vy_dir = 1
        self._music_play()

        self._draw_background(self.game_canvas)
        self._spawn_pipes()
        self._draw_duck()
        self._update_hud()

        self.game_loop()

    def game_loop(self):
        self._update_hud()

        if not self.game_over:
            # Update movement like your logic
            base = self.speed_map.get(self.alien_0['speed'], 1)
            x_inc = base + self.vx_extra
            self.vx_extra *= 0.96

            # Bobbing
            self.alien_0['y_position'] += self.vy * self.vy_dir
            if self.alien_0['y_position'] < GROUND_Y - 70:
                self.vy_dir = 1
            elif self.alien_0['y_position'] > GROUND_Y - 40:
                self.vy_dir = -1

            self.alien_0['x_position'] += x_inc
            if self.alien_0['x_position'] > WINDOW_W + 30:
                self.alien_0['x_position'] = -120
                self.alien_0['y_position'] = GROUND_Y - 52 + random.randint(-10, 10)

            self._draw_background(self.game_canvas)
            self._draw_pipes_instances()
            self._draw_duck()

            # Timer
            if time.time() - self.start_time >= GAME_SECONDS:
                self.end_game()

        self.root.after(16, self.game_loop)

    def end_game(self):
        self.game_over = True
        self._music_stop()
        name = simpledialog.askstring("Game Over", f"Final score: {self.score} Enter your name:")
        add_score_to_leaderboard(name or "Player", self.score)
        self.show_leaderboard()

    # ------------- Drawing Helpers ------------- #
    def _draw_sky(self, c):
        band_h = (WINDOW_H-40)//8
        for i, col in enumerate(SKY_COLORS):
            c.create_rectangle(0, i*band_h, WINDOW_W, (i+1)*band_h, fill=col, outline="")
        # Sun
        self._draw_pixel_sprite(c, SUN_PIX, 60, 60, self.settings["pixel_size"])  # top-left

    def _draw_ground(self, c):
        c.create_rectangle(0, GROUND_Y, WINDOW_W, WINDOW_H, fill=WATER_COLOR, outline="")
        # Grass strip
        c.create_rectangle(0, GROUND_Y-24, WINDOW_W, GROUND_Y, fill=GROUND_COLOR, outline="")
        # Blocks row
        ps = self.settings["pixel_size"]
        for x in range(0, WINDOW_W, len(BLOCK_PIX[0])*ps):
            self._draw_pixel_sprite(c, BLOCK_PIX, x, GROUND_Y-24 - len(BLOCK_PIX)*ps, ps)

    def _draw_clouds(self, c):
        ps = self.settings["pixel_size"]
        for x in [120, 380, 700]:
            self._draw_pixel_sprite(c, CLOUD_PIX, x, 80 + random.randint(-10,10), ps)

    def _draw_pipes(self, c=None):
        tgt = c or self.game_canvas
        ps = self.settings["pixel_size"]
        for x in [200, 520, 820]:
            self._draw_pixel_sprite(tgt, PIPE_PIX, x, GROUND_Y - len(PIPE_PIX)*ps, ps)

    def _draw_background(self, c):
        c.delete("bg")
        band_h = (WINDOW_H-40)//8
        for i, col in enumerate(SKY_COLORS):
            c.create_rectangle(0, i*band_h, WINDOW_W, (i+1)*band_h, fill=col, outline="", tags="bg")
        self._draw_pixel_sprite(c, SUN_PIX, 60, 60, self.settings["pixel_size"], tag="bg")
        # clouds move slowly to the left
        self._ensure_clouds_cached(c)
        for cloud in self._clouds:
            x, y = cloud["pos"]
            x -= 0.3
            if x < -200:
                x = WINDOW_W + 50
                y = 80 + random.randint(-10,10)
            cloud["pos"] = (x, y)
            self._draw_pixel_sprite(c, CLOUD_PIX, int(x), int(y), self.settings["pixel_size"], tag="bg")

        # ground and decorative pipes/bushes
        c.create_rectangle(0, GROUND_Y, WINDOW_W, WINDOW_H, fill=WATER_COLOR, outline="", tags="bg")
        c.create_rectangle(0, GROUND_Y-24, WINDOW_W, GROUND_Y, fill=GROUND_COLOR, outline="", tags="bg")
        ps = self.settings["pixel_size"]
        for x in range(0, WINDOW_W, len(BLOCK_PIX[0])*ps):
            self._draw_pixel_sprite(c, BLOCK_PIX, x, GROUND_Y-24 - len(BLOCK_PIX)*ps, ps, tag="bg")

    def _ensure_clouds_cached(self, c):
        if hasattr(self, "_clouds"):
            return
        self._clouds = [{"pos": (x, 80 + random.randint(-10,10))} for x in [120, 380, 700]]

    def _spawn_pipes(self):
        # Static visual pipes along bottom (not collisions for click game)
        self._pipes = [200, 520, 820]

    def _draw_pipes_instances(self):
        ps = self.settings["pixel_size"]
        for x in self._pipes:
            self._draw_pixel_sprite(self.game_canvas, PIPE_PIX, x, GROUND_Y - len(PIPE_PIX)*ps, ps)
        # Random bushes
        for bx in [100, 420, 740]:
            self._draw_pixel_sprite(self.game_canvas, BUSH_PIX, bx, GROUND_Y - len(BUSH_PIX)*ps, ps)

    def _draw_duck(self):
        # Bind clicking to score
        self.game_canvas.delete("duck")
        ps = self.settings["pixel_size"]
        x = int(self.alien_0['x_position'])
        y = int(self.alien_0['y_position'])
        self._draw_pixel_sprite(self.game_canvas, DUCK_PIX, x, y, ps, tag="duck")
        # Rough click area
        w = len(DUCK_PIX[0]) * ps
        h = len(DUCK_PIX) * ps
        # Create transparent rectangle to catch clicks
        rid = self.game_canvas.create_rectangle(x, y, x+w, y+h, outline="", fill="", tags=("duck", "duck_hit"))
        self.game_canvas.tag_bind("duck_hit", "<Button-1>", self._hit_duck)

    def _hit_duck(self, _evt=None):
        if self.game_over:
            return
        self.score += 1
        self.vx_extra += 0.5
        self.alien_0['y_position'] -= 6
        self.vy_dir = -1
        self._update_hud()

    # ------------- Drawing Primitive ------------- #
    def _draw_pixel_sprite(self, c, pixmap, x, y, ps, tag=None):
        for row, line in enumerate(pixmap):
            for col, ch in enumerate(line):
                if ch == '.':
                    continue
                color = PALETTE.get(ch, None)
                if not color:
                    continue
                c.create_rectangle(x+col*ps, y+row*ps, x+(col+1)*ps, y+(row+1)*ps, fill=color, outline=color, tags=tag)

    # ------------- HUD & Bindings ------------- #
    def _update_hud(self):
        remaining = max(0, int(GAME_SECONDS - (time.time() - self.start_time))) if self.start_time else GAME_SECONDS
        self.score_var.set(f"Score: {self.score}")
        self.time_var.set(f"Time: {remaining}s")
        self.speed_var.set(f"Speed: {self.alien_0['speed']} ({self.settings['difficulty']})")

    def bindings(self):
        self.root.bind("1", lambda e: self._set_speed('slow'))
        self.root.bind("2", lambda e: self._set_speed('medium'))
        self.root.bind("3", lambda e: self._set_speed('fast'))
        self.root.bind("s", lambda e: self._set_speed('slow'))
        self.root.bind("m", lambda e: self._set_speed('medium'))
        self.root.bind("f", lambda e: self._set_speed('fast'))
        self.root.bind("<space>", self._dash)
        self.root.bind("r", lambda e: (not self.game_over) and self._restart_round())

    def _set_speed(self, s):
        self.alien_0['speed'] = s

    def _dash(self, _evt=None):
        self.vx_extra += 3.0

    def _restart_round(self):
        self.start_game()


# ----------------- main ----------------- #

def main():
    root = tk.Tk()
    app = DuckDashPixel(root)
    root.mainloop()

if __name__ == "__main__":
    main()

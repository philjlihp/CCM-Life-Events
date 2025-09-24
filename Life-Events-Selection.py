import os
import json
import configparser
from datetime import datetime, timedelta
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, Menu, Toplevel
from ttkthemes import ThemedTk
from mutagen.id3 import ID3, COMM

SETTINGS_FILE = "life-events.ini"
SELECTIONS_FILE = "life-events.json"

song_mapping = {}

# --- Date functions ---
def get_upcoming_dates(months=3):
    today = datetime.today().date()
    end_date = today + timedelta(days=months * 30)
    dates = []
    current = today
    while current <= end_date:
        dates.append(current.strftime("%d/%m/%Y - %a"))
        current += timedelta(days=1)
    return dates

def extract_date(date_label):
    return date_label.split(" - ")[0]

# --- Mutagen helpers ---
def read_intro_comment(mp3_path):
    try:
        audio = ID3(mp3_path)
        comments = audio.getall("COMM")
        for comment in comments:
            if "IntroBeforeVocals" in comment.text[0]:
                return comment.text[0].split('=')[1].strip().lower()
    except:
        pass
    return None

# --- File listing ---
def list_files(folder):
    if not os.path.isdir(folder):
        return {}
    mapping = {}
    valid_exts = (".mp3", ".wav", ".flac", ".ogg", ".xspf")
    for f in os.listdir(folder):
        full_path = os.path.join(folder, f)
        if os.path.isfile(full_path) and f.lower().endswith(valid_exts):
            display_name = os.path.splitext(f)[0]
            if f.lower().endswith(".xspf"):
                display_name += " 🎵"
            if f.lower().endswith(".mp3") and read_intro_comment(full_path) == "yes":
                display_name += " 🎹"
            mapping[display_name] = full_path
    return mapping

def clean_display_name(name):
    return name.replace(" 🎵", "").replace(" 🎹", "")

def get_relative_path(full_path, resources_folder):
    if not full_path:
        return ""
    full_path = os.path.normpath(full_path)
    if full_path.startswith(resources_folder):
        trimmed = full_path[len(resources_folder):].lstrip("\\/")
        return "\\" + trimmed
    elif resources_folder in full_path:
        parts = full_path.split(resources_folder, 1)
        return "\\" + parts[1].lstrip("\\/")
    else:
        return "\\" + os.path.basename(full_path)

# --- Config ---
def get_config_folder():
    if os.name == "nt":
        return Path(os.getenv("APPDATA")) / "CCM"
    else:
        return Path.home() / ".config" / "CCM"

def load_folder_paths():
    config_file = get_config_folder() / SETTINGS_FILE
    if config_file.exists():
        config = configparser.ConfigParser()
        config.read(config_file)
        music_folder_var.set(config.get('Folders', 'music_folder', fallback=""))
        save_folder_var.set(config.get('Folders', 'save_folder', fallback=""))
        update_dropdowns()

def save_folder_paths():
    folder = get_config_folder()
    folder.mkdir(parents=True, exist_ok=True)
    config_file = folder / SETTINGS_FILE
    config = configparser.ConfigParser()
    config['Folders'] = {
        'music_folder': music_folder_var.get(),
        'save_folder': save_folder_var.get()
    }
    with open(config_file, 'w') as f:
        config.write(f)
    show_status("Settings saved successfully!")

# --- Status helper ---
def show_status(msg, color="blue", delay=3000):
    status_label.config(text=msg, fg=color)
    root.after(delay, lambda: status_label.config(text=""))

# --- Save/Load selections ---
def save_selections():
    selections = {}
    save_path = Path(save_folder_var.get() or os.getcwd())
    save_path.mkdir(parents=True, exist_ok=True)
    json_file = save_path / SELECTIONS_FILE

    if json_file.exists():
        try:
            with open(json_file, 'r') as f:
                selections = json.load(f)
        except:
            selections = {}

    event_date = extract_date(date_var.get())
    resources_folder = os.path.dirname(music_folder_var.get())

    def path_for(var):
        return get_relative_path(song_mapping.get(var.get(), ""), resources_folder)

    def intro_for(var):
        path = song_mapping.get(var.get(), "")
        return read_intro_comment(path)

    selections[event_date] = {
        "type": event_type_var.get(),
        "comment": comment_var.get(),
        "entrance": clean_display_name(entrance_var.get()),
        "entrancepath": path_for(entrance_var),
        "song1": clean_display_name(song1_var.get()),
        "song1path": path_for(song1_var),
        "song1intro": intro_for(song1_var),
        "song2": clean_display_name(song2_var.get()),
        "song2path": path_for(song2_var),
        "song2intro": intro_for(song2_var),
        "song3": clean_display_name(song3_var.get()),
        "song3path": path_for(song3_var),
        "song3intro": intro_for(song3_var),
        "song4": clean_display_name(song4_var.get()),
        "song4path": path_for(song4_var),
        "song4intro": intro_for(song4_var),
        "exit": clean_display_name(exit_var.get()),
        "exitpath": path_for(exit_var),
        "saved_at": datetime.now().isoformat()
    }

    with open(json_file, 'w') as f:
        json.dump(selections, f, indent=4)

    show_status("Selections saved successfully!")
    mark_existing_dates()

def replace_pl_with_song_icon(song_name):
    for key in song_mapping:
        if clean_display_name(key) == song_name:
            return key
    return song_name

def load_selections():
    for var in [entrance_var, exit_var, song1_var, song2_var, song3_var, song4_var]:
        var.set("")
    event_type_var.set("General")
    comment_var.set("")

    save_path = Path(save_folder_var.get() or os.getcwd())
    json_file = save_path / SELECTIONS_FILE
    date_str = extract_date(date_var.get())

    if json_file.exists():
        try:
            with open(json_file, 'r') as f:
                selections = json.load(f)
        except:
            selections = {}

        if date_str in selections:
            sel = selections[date_str]
            entrance_var.set(replace_pl_with_song_icon(sel.get("entrance", "")))
            exit_var.set(replace_pl_with_song_icon(sel.get("exit", "")))
            song1_var.set(replace_pl_with_song_icon(sel.get("song1", "")))
            song2_var.set(replace_pl_with_song_icon(sel.get("song2", "")))
            song3_var.set(replace_pl_with_song_icon(sel.get("song3", "")))
            song4_var.set(replace_pl_with_song_icon(sel.get("song4", "")))
            event_type_var.set(sel.get("type", "General"))
            comment_var.set(sel.get("comment", ""))

# --- UI helpers ---
def update_dropdowns():
    global song_mapping
    if not music_folder_var.get():
        return
    song_mapping = list_files(music_folder_var.get())
    options = [""] + list(song_mapping.keys())
    for dropdown in [entrance_dropdown, exit_dropdown, song1_dropdown, song2_dropdown, song3_dropdown, song4_dropdown]:
        dropdown["values"] = options
    mark_existing_dates()
    load_selections()

def browse_folder(entry_var):
    folder = filedialog.askdirectory()
    if folder:
        entry_var.set(folder)
        update_dropdowns()

def mark_existing_dates():
    save_path = Path(save_folder_var.get() or os.getcwd())
    json_file = save_path / SELECTIONS_FILE
    base_dates = get_upcoming_dates()
    marked = []
    selections = {}
    if json_file.exists():
        try:
            with open(json_file, 'r') as f:
                selections = json.load(f)
        except:
            selections = {}
    for d in base_dates:
        date_str = extract_date(d)
        if date_str in selections:
            marked.append(d + " ✓")
        else:
            marked.append(d)
    date_dropdown["values"] = marked

# --- Main window ---
root = ThemedTk()
root.title("Christ Church Life Events")
root.geometry("650x820")
root.set_theme("clam")

music_folder_var = tk.StringVar()
save_folder_var = tk.StringVar()
date_var = tk.StringVar()
entrance_var = tk.StringVar()
exit_var = tk.StringVar()
song1_var = tk.StringVar()
song2_var = tk.StringVar()
song3_var = tk.StringVar()
song4_var = tk.StringVar()
event_type_var = tk.StringVar(value="General")
comment_var = tk.StringVar()

menubar = Menu(root)
root.config(menu=menubar)
settings_menu = Menu(menubar, tearoff=0)
menubar.add_cascade(label="Settings", menu=settings_menu)
settings_menu.add_command(label="Select Folders", command=lambda: open_settings_window())

main_frame = tk.Frame(root, padx=20, pady=20, bg="#f7f7f7")
main_frame.pack(fill="both", expand=True)

tk.Label(main_frame, text="Christ Church Life Events", font=("Arial", 16, "bold"), bg="#f7f7f7").pack(pady=10)

# Date selection
tk.Label(main_frame, text="Select Date:", font=("Arial", 12), bg="#f7f7f7").pack(anchor="w", pady=5)
date_dropdown = ttk.Combobox(main_frame, textvariable=date_var, width=40, font=("Arial", 12))
date_dropdown.pack(fill="x", pady=5)
date_var.set(get_upcoming_dates()[0])
date_dropdown.bind("<<ComboboxSelected>>", lambda e: load_selections())

# Event type
tk.Label(main_frame, text="Event Type:", font=("Arial", 12), bg="#f7f7f7").pack(anchor="w", pady=(10, 0))
event_frame = tk.Frame(main_frame, bg="#f7f7f7")
event_frame.pack(anchor="w", pady=5)
tk.Radiobutton(event_frame, text="Wedding", variable=event_type_var, value="Wedding", bg="#f7f7f7").pack(side="left", padx=5)
tk.Radiobutton(event_frame, text="Funeral", variable=event_type_var, value="Funeral", bg="#f7f7f7").pack(side="left", padx=5)
tk.Radiobutton(event_frame, text="General", variable=event_type_var, value="General", bg="#f7f7f7").pack(side="left", padx=5)

# Comment
tk.Label(main_frame, text="Comment:", font=("Arial", 12), bg="#f7f7f7").pack(anchor="w", pady=(10, 0))
tk.Entry(main_frame, textvariable=comment_var, width=50, font=("Arial", 12)).pack(fill="x", pady=5)

# Song dropdown helper
def create_song_dropdown(label, var):
    tk.Label(main_frame, text=label, font=("Arial", 12), bg="#f7f7f7").pack(anchor="w", pady=5)
    dropdown = ttk.Combobox(main_frame, textvariable=var, width=40, font=("Arial", 12))
    dropdown.pack(fill="x", pady=5)
    return dropdown

entrance_dropdown = create_song_dropdown("Entrance Music:", entrance_var)
exit_dropdown = create_song_dropdown("Exit Music:", exit_var)
song1_dropdown = create_song_dropdown("Song 1:", song1_var)
song2_dropdown = create_song_dropdown("Song 2:", song2_var)
song3_dropdown = create_song_dropdown("Song 3:", song3_var)
song4_dropdown = create_song_dropdown("Song 4:", song4_var)

save_button = tk.Button(main_frame, text="Save Selection", font=("Arial", 14), bg="#1E90FF", fg="white", command=save_selections)
save_button.pack(pady=15, fill="x")

status_label = tk.Label(main_frame, text="", fg="blue", font=("Arial", 12), bg="#f7f7f7")
status_label.pack(pady=10)

# --- Settings window ---
def open_settings_window():
    win = Toplevel(root)
    win.title("Settings")
    win.geometry("520x300")
    win.grab_set()
    frame = tk.Frame(win, padx=20, pady=20)
    frame.pack(fill="both", expand=True)

    for label, var in [("Music Folder:", music_folder_var), ("Save Folder:", save_folder_var)]:
        tk.Label(frame, text=label, font=("Arial", 12)).pack(anchor="w", pady=5)
        tk.Entry(frame, textvariable=var, width=50, font=("Arial", 12)).pack(fill="x", pady=5)
        tk.Button(frame, text="Browse...", font=("Arial", 12), command=lambda v=var: browse_folder(v)).pack()

    tk.Button(frame, text="Save Settings", font=("Arial", 14), bg="#1E90FF", fg="white", command=save_folder_paths).pack(pady=10)

load_folder_paths()
mark_existing_dates()
root.mainloop()

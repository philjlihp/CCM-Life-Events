import requests
import json
import os
import configparser
import subprocess
import psutil
import sys
import webbrowser
from urllib.parse import quote
from datetime import datetime, date
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
import re

# --- IP validation helper ---
def is_valid_ip(ip):
    pattern = re.compile(r"^(?:[0-9]{1,3}\.){3}[0-9]{1,3}$")
    if not pattern.match(ip):
        return False
    return all(0 <= int(part) <= 255 for part in ip.split("."))

class LifeEventsActivationApp:
    def __init__(self, force_activate=False, force_buttons=False, force_vlc=None):
        appdata = os.getenv("APPDATA")
        if not appdata:
            appdata = os.path.join(os.path.expanduser("~"), ".config")
        self.config_folder = os.path.join(appdata, "CCM")
        self.config_file = os.path.join(self.config_folder, "life-events.ini")
        self.config = configparser.ConfigParser()

        # Attributes
        self.companion_page_number = "001"
        self.show_refresh_button = True
        self.show_buttons_button = False
        self.show_control_buttons_button = False
        self.companion_buttons_url = ""
        self.auto_launch_buttons = False
        self.force_activate = force_activate
        self.force_buttons = force_buttons
        self.force_vlc = force_vlc  # True/False/None
        self.launch_vlc_on_startup = True

        self.data = {}
        self.json_path = ""
        self.api_url = ""

        # GUI attributes
        self.root = None
        self.date_var = None
        self.date_dropdown = None
        self.song_vars = {}
        self.event_type_var = None
        self.comment_var = None
        self.feedback_label = None
        self.upload_button = None
        self.refresh_button = None
        self.buttons_button = None
        self.control_button = None

        self.load_config()
        comp_ip = self.get_config_value('Companion', 'CompanionIP', '')
        if comp_ip:
            self.api_url = f"http://{comp_ip}:8000/api/custom-variable/{{}}/value?value={{}}"

    # --- Config ---
    def load_config(self):
        if not os.path.exists(self.config_file):
            os.makedirs(self.config_folder, exist_ok=True)
            self.config['Paths'] = {
                'SaveFolderPath': '',
                'VLCPath': 'C:\\Program Files\\VideoLAN\\VLC\\vlc.exe',
                'LaunchVLC': 'yes'
            }
            self.config['Companion'] = {
                'CompanionIP': '',
                'CompanionPageNumber': '001',
                'ShowRefreshButton': 'yes',
                'CompanionButtonsURL': '',
                'ShowButtonsButton': 'no',
                'AutoLaunchButtons': 'no',
                'ShowControlButtonsButton': 'no'
            }
            self.save_config()
        self.config.read(self.config_file)
        self.companion_page_number = self.get_config_value('Companion', 'CompanionPageNumber', '001')
        self.show_refresh_button = self.get_config_value('Companion', 'ShowRefreshButton', 'yes').lower() == 'yes'
        self.show_buttons_button = self.get_config_value('Companion', 'ShowButtonsButton', 'no').lower() == 'yes'
        self.show_control_buttons_button = self.get_config_value('Companion', 'ShowControlButtonsButton', 'no').lower() == 'yes'
        self.companion_buttons_url = self.get_config_value('Companion', 'CompanionButtonsURL', '')
        self.auto_launch_buttons = self.get_config_value('Companion', 'AutoLaunchButtons', 'no').lower() == 'yes'
        self.launch_vlc_on_startup = self.get_config_value('Paths', 'LaunchVLC', 'yes').lower() == 'yes'

    def save_config(self):
        self.set_config_value('Companion', 'CompanionPageNumber', self.companion_page_number)
        self.set_config_value('Companion', 'ShowRefreshButton', 'yes' if self.show_refresh_button else 'no')
        self.set_config_value('Companion', 'CompanionButtonsURL', self.companion_buttons_url or '')
        self.set_config_value('Companion', 'ShowButtonsButton', 'yes' if self.show_buttons_button else 'no')
        self.set_config_value('Companion', 'AutoLaunchButtons', 'yes' if self.auto_launch_buttons else 'no')
        self.set_config_value('Companion', 'ShowControlButtonsButton', 'yes' if self.show_control_buttons_button else 'no')
        self.set_config_value('Paths', 'LaunchVLC', 'yes' if self.launch_vlc_on_startup else 'no')
        with open(self.config_file, 'w') as f:
            self.config.write(f)

    def get_config_value(self, section, key, fallback=None):
        return self.config.get(section, key, fallback=fallback)

    def set_config_value(self, section, key, value):
        if not self.config.has_section(section):
            self.config.add_section(section)
        self.config.set(section, key, value)

    # --- JSON ---
    def fetch_json(self, filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            root = tk.Tk(); root.withdraw()
            messagebox.showerror("Error Loading JSON", f"Failed to load {filepath}:\n{e}")
            root.destroy()
            return None

    def ensure_json_file(self):
        while True:
            sf = self.get_config_value('Paths', 'SaveFolderPath')
            if not sf:
                root = tk.Tk(); root.withdraw()
                messagebox.showwarning("Save Folder Not Set","Please select folder containing life-events.json.")
                folder = filedialog.askdirectory(title="Select folder containing life-events.json")
                root.destroy()
                if not folder: sys.exit(0)
                self.set_config_value('Paths','SaveFolderPath', folder)
                self.save_config()
                sf = folder

            self.json_path = os.path.join(sf, "life-events.json")
            if os.path.exists(self.json_path): break

            root = tk.Tk(); root.withdraw()
            messagebox.showwarning("JSON Not Found",f"Could not find life-events.json in:\n{sf}\nSelect folder.")
            folder = filedialog.askdirectory(title="Select folder containing life-events.json")
            root.destroy()
            if not folder: sys.exit(0)
            self.set_config_value('Paths','SaveFolderPath', folder)
            self.save_config()
            sf = folder

    def ensure_companion_ip(self):
        cip = self.get_config_value('Companion', 'CompanionIP', '').strip()
        if not is_valid_ip(cip):
            messagebox.showwarning(
                "Invalid Companion IP",
                "No valid Companion IP found in settings.\n\n"
                "Defaulting to 127.0.0.1"
            )
            cip = "127.0.0.1"
            self.set_config_value('Companion', 'CompanionIP', cip)
            self.save_config()
        self.api_url = f"http://{cip}:8000/api/custom-variable/{{}}/value?value={{}}"

    # --- Event/song methods ---
    def extract_song_data(self, event_data):
        keys = ['entrance','exit','song1','song2','song3','song4',
                'entrancepath','exitpath','song1path','song2path','song3path','song4path',
                'song1intro','song2intro','song3intro','song4intro']
        return {k: event_data.get(k, '') for k in keys}

    def get_intro_icon(self, raw):
        return ' 🎹' if (raw or '').strip().lower() == 'yes' else ''

    def send_post_requests(self, song_data, event_date_str):
        if not self.api_url: return
        vars_map = {
            'entrance':'LE_EntranceMusic','exit':'LE_ExitMusic',
            'song1':'LE_Song1','song2':'LE_Song2','song3':'LE_Song3','song4':'LE_Song4',
            'entrancepath':'LE_EntranceMusicPath','exitpath':'LE_ExitMusicPath',
            'song1path':'LE_Song1Path','song2path':'LE_Song2Path',
            'song3path':'LE_Song3Path','song4path':'LE_Song4Path'
        }
        try: requests.post(self.api_url.format("LE_LifeEventDate", quote(event_date_str)), timeout=5)
        except: pass
        for k,v in song_data.items():
            if k in vars_map:
                try: requests.post(self.api_url.format(vars_map[k], quote(str(v))), timeout=5)
                except: pass
        for key in ['song1','song2','song3','song4']:
            icon = self.get_intro_icon(song_data.get(f"{key}intro"))
            try: requests.post(self.api_url.format(vars_map[key]+'Intro', quote(icon)), timeout=5)
            except: pass
        try: requests.post(self.api_url.format('LE_surface_page_number', quote(self.companion_page_number)), timeout=5)
        except: pass
        try: requests.post(self.api_url.format('LE_EventType', quote(self.event_type_var.get())), timeout=5)
        except: pass
        try: requests.post(self.api_url.format('LE_EventComment', quote(self.comment_var.get())), timeout=5)
        except: pass

    def update_song_display(self, event_date_str):
        data = self.data.get(event_date_str, {})
        songs = self.extract_song_data(data)
        for k,var in self.song_vars.items():
            val = songs.get(k,'')
            var.set(val + self.get_intro_icon(songs.get(f'{k}intro')))
        event_type = data.get('type','General')
        self.event_type_var.set(event_type)
        self.comment_var.set(data.get('comment',''))
        if self.upload_button:
            if event_type.lower()=='wedding': self.upload_button.config(text="Activate Wedding")
            elif event_type.lower()=='funeral': self.upload_button.config(text="Activate Funeral")
            else: self.upload_button.config(text="Activate Life Event")

    # --- GUI ---
    def setup_ui(self):
        self.root = tk.Tk()
        self.root.title("Christ Church Life Events Buttons")
        lbl_font=("Arial",13)

        menu_bar = tk.Menu(self.root)
        self.root.config(menu=menu_bar)
        settings_menu = tk.Menu(menu_bar, tearoff=0)
        menu_bar.add_cascade(label="Settings", menu=settings_menu)
        settings_menu.add_command(label="Open Settings", command=self.open_settings_menu)
        settings_menu.add_command(label="Help / Info", command=self.show_help)

        ttk.Label(self.root,text="Christ Church Life Events Buttons",font=("Arial",16)).pack(pady=10)

        df = ttk.Frame(self.root); df.pack(pady=5)
        ttk.Label(df,text="Select Date:",font=lbl_font).pack(side='left', padx=5)
        self.date_var = tk.StringVar()
        dates = sorted(self.data.keys(), key=lambda x: datetime.strptime(x,'%d/%m/%Y'))
        self.date_dropdown = ttk.Combobox(df,textvariable=self.date_var,values=dates,state="readonly", font=lbl_font, width=15)
        self.date_dropdown.bind("<<ComboboxSelected>>", self.on_date_change); self.date_dropdown.pack(side='left', padx=5)

        self.event_type_var = tk.StringVar(); self.comment_var = tk.StringVar()
        ttk.Label(self.root,text="Event Type:",font=lbl_font).pack(anchor='w', padx=20)
        ttk.Label(self.root,textvariable=self.event_type_var,font=lbl_font,foreground="darkblue").pack(anchor='w', padx=40)
        ttk.Label(self.root,text="Comment:",font=lbl_font).pack(anchor='w', padx=20)
        ttk.Label(self.root,textvariable=self.comment_var,font=lbl_font,foreground="darkgreen").pack(anchor='w', padx=40)

        self.song_vars = {k: tk.StringVar() for k in ['entrance','exit','song1','song2','song3','song4']}
        for k in ['entrance','exit','song1','song2','song3','song4']:
            f = ttk.Frame(self.root); f.pack(fill='x', padx=20, pady=2)
            ttk.Label(f,text=f"{k.capitalize()}:",font=lbl_font).pack(side='left')
            ttk.Label(f,textvariable=self.song_vars[k],font=lbl_font).pack(side='left', padx=5)

        self.feedback_label = ttk.Label(self.root,text="",font=lbl_font,foreground="blue"); self.feedback_label.pack(pady=5)
        self.upload_button = tk.Button(self.root,text="Activate Life Event",command=self.upload_data,width=25,bg="blue",fg="white",font=lbl_font)
        self.upload_button.pack(pady=5)

        self.refresh_button = ttk.Button(self.root,text="Refresh Data",command=self.refresh_json)
        if self.show_refresh_button: self.refresh_button.pack(pady=5)

        self.buttons_button = tk.Button(self.root,text="Launch Buttons",command=self.launch_buttons,width=25,bg="green",fg="white",font=lbl_font)
        if self.show_buttons_button: self.buttons_button.pack(pady=5)

        self.control_button = tk.Button(self.root,text="Control Buttons",command=self.launch_buttons,width=25,bg="purple",fg="white",font=lbl_font)
        if self.show_control_buttons_button: self.control_button.pack(pady=5)

    def on_date_change(self, event):
        self.update_song_display(self.date_var.get())

    # --- Center window helper ---
    def center_window(self, win, width, height):
        win.update_idletasks()
        screen_w = win.winfo_screenwidth()
        screen_h = win.winfo_screenheight()
        x = (screen_w // 2) - (width // 2)
        y = (screen_h // 2) - (height // 2)
        win.geometry(f"{width}x{height}+{x}+{y}")

    # --- Custom activation prompt ---
    def ask_activate_event(self, event_date, event_type, comment):
        win = tk.Toplevel(self.root)
        win.title("Activate Upcoming Life Event")
        self.center_window(win, 400, 220)
        win.transient(self.root)
        win.grab_set()

        lbl_font = ("Arial", 14)

        ttk.Label(win, text=f"Life Event - {event_date}", font=("Arial", 16, "bold")).pack(pady=10)
        ttk.Label(win, text=event_type, font=lbl_font, foreground="darkblue").pack(pady=5)
        ttk.Label(win, text=comment, font=lbl_font, foreground="darkgreen").pack(pady=5)
        ttk.Label(win, text="Activate this?", font=("Arial", 14)).pack(pady=10)

        response = {"answer": False}
        def yes(): response.update(answer=True); win.destroy()
        def no(): response.update(answer=False); win.destroy()

        btn_frame = ttk.Frame(win); btn_frame.pack(pady=10)
        ttk.Button(btn_frame, text="Yes", command=yes).pack(side="left", padx=20)
        ttk.Button(btn_frame, text="No", command=no).pack(side="left", padx=20)

        win.wait_window()
        return response["answer"]

    # --- Settings ---
    def open_settings_menu(self):
        win = tk.Toplevel(self.root)
        win.title("Settings Menu"); self.center_window(win, 600, 420)
        win.resizable(False, False)
        win.transient(self.root); win.grab_set()
        frame = ttk.Frame(win,padding=20); frame.pack(fill='both',expand=True)
        lbl_width = 20

        ttk.Label(frame,text="Save Folder Path:",width=lbl_width).grid(row=0,column=0,sticky='w', pady=5)
        save_entry = ttk.Entry(frame,width=50); save_entry.insert(0,self.get_config_value('Paths','SaveFolderPath','')); save_entry.grid(row=0,column=1,padx=5)
        ttk.Button(frame,text="Browse",command=lambda:self.browse_save_folder(save_entry)).grid(row=0,column=2)

        ttk.Label(frame,text="VLC Path:",width=lbl_width).grid(row=1,column=0,sticky='w', pady=5)
        vlc_entry = ttk.Entry(frame,width=50); vlc_entry.insert(0,self.get_config_value('Paths','VLCPath','C:\\Program Files\\VideoLAN\\VLC\\vlc.exe')); vlc_entry.grid(row=1,column=1,padx=5)
        ttk.Button(frame,text="Browse",command=lambda:self.browse_vlc_path(vlc_entry)).grid(row=1,column=2)

        ttk.Label(frame,text="Companion IP:",width=lbl_width).grid(row=2,column=0,sticky='w', pady=5)
        comp_entry = ttk.Entry(frame,width=50); comp_entry.insert(0,self.get_config_value('Companion','CompanionIP','')); comp_entry.grid(row=2,column=1,padx=5)

        ttk.Label(frame,text="Companion Page Number:",width=lbl_width).grid(row=3,column=0,sticky='w', pady=5)
        page_entry = ttk.Entry(frame,width=10); page_entry.insert(0,self.companion_page_number); page_entry.grid(row=3,column=1,padx=5, sticky='w')

        ttk.Label(frame,text="Companion Buttons URL:",width=lbl_width).grid(row=4,column=0,sticky='w', pady=5)
        url_entry = ttk.Entry(frame,width=50); url_entry.insert(0,self.companion_buttons_url); url_entry.grid(row=4,column=1,padx=5)

        self.refresh_var = tk.BooleanVar(value=self.show_refresh_button)
        ttk.Checkbutton(frame,text="Show Refresh Data Button",variable=self.refresh_var).grid(row=5,column=0,columnspan=2, pady=5, sticky='w')

        self.buttons_var = tk.BooleanVar(value=self.show_buttons_button)
        ttk.Checkbutton(frame,text="Show Launch Buttons Button",variable=self.buttons_var).grid(row=6,column=0,columnspan=2, pady=5, sticky='w')

        self.control_var = tk.BooleanVar(value=self.show_control_buttons_button)
        ttk.Checkbutton(frame,text="Show Control Buttons Button",variable=self.control_var).grid(row=7,column=0,columnspan=2, pady=5, sticky='w')

        self.vlc_var = tk.BooleanVar(value=self.launch_vlc_on_startup)
        ttk.Checkbutton(frame,text="Launch VLC on Startup",variable=self.vlc_var).grid(row=8,column=0,columnspan=2, pady=5, sticky='w')

        self.auto_launch_var = tk.BooleanVar(value=self.auto_launch_buttons)
        ttk.Checkbutton(frame,text="Auto Launch Buttons on Activation",variable=self.auto_launch_var).grid(row=9,column=0,columnspan=2, pady=5, sticky='w')

        def save_settings():
            cip = comp_entry.get().strip()
            if not is_valid_ip(cip):
                messagebox.showwarning(
                    "Invalid Companion IP",
                    "The Companion IP you entered is invalid.\n\nDefaulting to 127.0.0.1"
                )
                cip = "127.0.0.1"

            self.set_config_value('Paths','SaveFolderPath',save_entry.get())
            self.set_config_value('Paths','VLCPath',vlc_entry.get())
            self.set_config_value('Companion','CompanionIP',cip)
            self.companion_page_number = page_entry.get().zfill(3)
            self.companion_buttons_url = url_entry.get()

            self.show_refresh_button = self.refresh_var.get()
            self.show_buttons_button = self.buttons_var.get()
            self.show_control_buttons_button = self.control_var.get()
            self.launch_vlc_on_startup = self.vlc_var.get()
            self.auto_launch_buttons = self.auto_launch_var.get()

            self.save_config()
            self.api_url = f"http://{cip}:8000/api/custom-variable/{{}}/value?value={{}}"

            # Refresh visible buttons
            self.refresh_button.pack_forget()
            self.buttons_button.pack_forget()
            if self.control_button: self.control_button.pack_forget()
            if self.show_refresh_button: self.refresh_button.pack(pady=5)
            if self.show_buttons_button: self.buttons_button.pack(pady=5)
            if self.show_control_buttons_button:
                if not self.control_button:
                    self.control_button = tk.Button(
                        self.root, text="Control Buttons",
                        command=self.launch_buttons, width=25,
                        bg="purple", fg="white", font=("Arial",13)
                    )
                self.control_button.pack(pady=5)

            messagebox.showinfo("Settings","Settings saved successfully")
            win.destroy()

        ttk.Button(frame,text="Save Settings",command=save_settings).grid(row=10,column=0,columnspan=3,pady=10)

    # --- Misc helpers ---
    def browse_save_folder(self, entry):
        folder = filedialog.askdirectory(title="Select folder containing life-events.json")
        if folder:
            entry.delete(0, tk.END)
            entry.insert(0, folder)

    def browse_vlc_path(self, entry):
        path = filedialog.askopenfilename(title="Select VLC Executable")
        if path:
            entry.delete(0, tk.END)
            entry.insert(0, path)

    def show_help(self):
        win = tk.Toplevel(self.root)
        win.title("Help / Info"); self.center_window(win, 600, 420)
        win.resizable(True, True)
        frame = ttk.Frame(win,padding=10); frame.pack(fill='both',expand=True)
        txt = scrolledtext.ScrolledText(frame, wrap='word')
        txt.pack(fill='both',expand=True)
        help_text = f"""
Christ Church Life Events Buttons App

Usage:
 -f or --force    : Force activate upcoming event without prompt
 -b or --buttons  : Launch Companion Buttons after activation
 -vlc             : Force VLC to launch at startup
 -novlc           : Prevent VLC from launching at startup

Requirements in Companion:
 - Custom Variables:
   LE_EntranceMusic, LE_ExitMusic, LE_Song1..LE_Song4
   LE_EntranceMusicPath, LE_ExitMusicPath, LE_Song1Path..LE_Song4Path
   LE_Song1Intro..LE_Song4Intro
   LE_LifeEventDate, LE_surface_page_number, LE_EventType, LE_EventComment

Config Path:
 {self.config_file}
"""
        txt.insert('1.0', help_text)
        txt.config(state='disabled')

    # --- Companion Buttons ---
    def launch_buttons(self):
        if self.companion_buttons_url:
            webbrowser.open(self.companion_buttons_url)
        else:
            messagebox.showwarning("No URL", "No Companion Buttons Emulator URL set in Settings.")

    # --- Data actions ---
    def refresh_json(self):
        prev = self.date_var.get()
        new_data = self.fetch_json(self.json_path)
        if new_data is not None:
            self.data = new_data
            opts = sorted(self.data.keys(), key=lambda x: datetime.strptime(x,'%d/%m/%Y'))
            self.date_dropdown['values'] = opts
            if prev in opts: self.date_var.set(prev)
            elif opts: self.date_var.set(opts[0])
            self.update_song_display(self.date_var.get())
            self.feedback_label.config(text="✅ Data refreshed successfully.", foreground="blue")
        else:
            self.feedback_label.config(text="❌ Failed to refresh data.", foreground="red")

    def upload_data(self):
        self.upload_button.config(state="disabled", text="Activating...")
        date_str = self.date_var.get()
        song_data = self.extract_song_data(self.data.get(date_str, {}))
        self.send_post_requests(song_data, date_str)
        self.upload_button.config(state="normal")
        self.update_song_display(date_str)
        self.feedback_label.config(text=f"Life Event for {date_str} activated!", foreground="blue")
        # Launch buttons after activation if requested via -b or settings
        if self.force_buttons or self.auto_launch_buttons:
            if self.root:
                self.root.after(1500, self.launch_buttons)
            else:
                self.launch_buttons()

    # --- VLC ---
    def is_vlc_running(self):
        for p in psutil.process_iter(['name']):
            if 'vlc' in (p.info.get('name') or '').lower(): return True
        return False

    def start_vlc(self):
        vlc = self.get_config_value('Paths','VLCPath','C:\\Program Files\\VideoLAN\\VLC\\vlc.exe')
        if vlc and os.path.exists(vlc):
            subprocess.Popen([vlc])
        else:
            messagebox.showwarning("VLC Not Found", f"VLC executable not found at:\n{vlc}")

    # --- Run ---
    def run(self):
        self.ensure_json_file()
        self.data = self.fetch_json(self.json_path) or {}
        self.ensure_companion_ip()
        self.setup_ui()

        # VLC launch
        vlc_launch = self.launch_vlc_on_startup if self.force_vlc is None else self.force_vlc
        if vlc_launch and not self.is_vlc_running():
            self.start_vlc()

        # Next event
        today = date.today()
        future_dates = sorted(
            [d for d in self.data.keys() if datetime.strptime(d,'%d/%m/%Y').date() >= today],
            key=lambda x: datetime.strptime(x,'%d/%m/%Y')
        )

        if future_dates:
            next_event = future_dates[0]
            self.date_var.set(next_event)
            self.update_song_display(next_event)
            if self.force_activate or self.ask_activate_event(next_event, self.event_type_var.get(), self.comment_var.get()):
                self.upload_data()
        else:
            self.date_var.set("")
            if self.api_url:
                try:
                    requests.post(self.api_url.format("LE_LifeEventDate","NO EVENT FOUND"), timeout=5)
                except:
                    pass
            messagebox.showinfo("No Event Found", "No upcoming life events were found.")

        # Always launch buttons if -b is passed, regardless of activation
        if self.force_buttons:
            if self.root:
                self.root.after(1500, self.launch_buttons)
            else:
                self.launch_buttons()

        self.root.mainloop()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Christ Church Life Events Buttons App")
    parser.add_argument("-f","--force", action="store_true", help="Force activate upcoming event without prompt")
    parser.add_argument("-b","--buttons", action="store_true", help="Launch Companion Buttons after activation")
    parser.add_argument("-vlc", action="store_true", help="Force VLC to launch at startup")
    parser.add_argument("-novlc", action="store_true", help="Prevent VLC from launching at startup")
    args = parser.parse_args()

    force_vlc = True if args.vlc else False if args.novlc else None

    app = LifeEventsActivationApp(force_activate=args.force, force_buttons=args.buttons, force_vlc=force_vlc)
    app.run()

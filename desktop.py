"""Native desktop interface for Render Workshop. No browser required."""
import io
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import tempfile
import threading
import tkinter as tk
from tkinter import filedialog, ttk, font
from PIL import Image, ImageTk
from renderfix import inspect_dds, normalize

BG = '#101523'
PANEL = '#1a2234'
TEXT = '#f0f4ff'
MUTED = '#aebbd2'
ACCENT = '#9eb6ff'
SUPPORTED = {'.dds', '.png', '.jpg', '.jpeg', '.webp', '.tga'}


class Workshop:
    def __init__(self, root):
        self.root = root
        self.files = []
        self.base = None
        self.images = []
        self.events = queue.Queue()
        self.busy = False
        self.output = None
        root.title('Render Workshop — WWE 2K26')
        root.geometry('1120x820')
        root.minsize(1000, 760)
        root.configure(bg=BG)
        families = {name.casefold(): name for name in font.families(root)}
        self.font = next((families[name] for name in ('segoe ui', 'dejavu sans', 'nimbus sans l', 'helvetica') if name in families), 'TkDefaultFont')
        root.option_add('*Font', (self.font, 11))
        style = ttk.Style(root)
        style.theme_use('clam')
        style.configure('TProgressbar', background=ACCENT, troughcolor=PANEL, borderwidth=0)
        outer = tk.Frame(root, bg=BG, padx=30, pady=24)
        outer.pack(fill='both', expand=True)
        self.label(outer, 'RENDER WORKSHOP', 12, ACCENT, bold=True).pack(anchor='w')
        self.label(outer, 'Your renders. Ready for the next step.', 26, bold=True).pack(anchor='w', pady=(12, 6))
        self.label(outer, 'Choose your folder, check the files, then save converted copies.', 12, MUTED).pack(anchor='w')
        steps = tk.Frame(outer, bg=BG)
        steps.pack(fill='x', pady=22)
        for text in ('1   Choose renders', '2   Check results', '3   Save new copies'):
            self.label(steps, text, 12, ACCENT, bold=True).pack(side='left', padx=(0, 45))
        body = tk.Frame(outer, bg=BG)
        body.pack(fill='both', expand=True)
        left = tk.Frame(body, bg=PANEL, padx=18, pady=18)
        left.pack(side='left', fill='both', expand=True, padx=(0, 18))
        bar = tk.Frame(left, bg=PANEL)
        bar.pack(fill='x')
        self.label(bar, 'Your render files', 16, bold=True).pack(side='left')
        self.count = self.label(bar, 'No files selected', 10, MUTED)
        self.count.pack(side='right')
        buttons = tk.Frame(left, bg=PANEL)
        buttons.pack(fill='x', pady=16)
        self.folder_button = self.button(buttons, 'Choose folder', self.choose_folder, primary=True)
        self.folder_button.pack(side='left', padx=(0, 10))
        self.file_button = self.button(buttons, 'Choose files', self.choose_files)
        self.file_button.pack(side='left')
        scroll = tk.Frame(left, bg=PANEL)
        scroll.pack(fill='both', expand=True)
        self.canvas = tk.Canvas(scroll, bg=PANEL, highlightthickness=0)
        scrollbar = ttk.Scrollbar(scroll, orient='vertical', command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side='right', fill='y')
        self.canvas.pack(side='left', fill='both', expand=True)
        self.rows = tk.Frame(self.canvas, bg=PANEL)
        window = self.canvas.create_window((0, 0), window=self.rows, anchor='nw')
        self.rows.bind('<Configure>', lambda e: self.canvas.configure(scrollregion=self.canvas.bbox('all')))
        self.canvas.bind('<Configure>', lambda e: self.canvas.itemconfigure(window, width=e.width))
        self.canvas.bind_all('<MouseWheel>', lambda e: self.canvas.yview_scroll(int(-e.delta / 120), 'units'))
        self.empty()
        right = tk.Frame(body, bg=PANEL, width=310, padx=20, pady=22)
        right.pack(side='right', fill='y')
        right.pack_propagate(False)
        self.label(right, 'Save settings', 17, bold=True).pack(anchor='w')
        self.label(right, 'Working ODB profile', 13, ACCENT, bold=True).pack(anchor='w', pady=(16, 8))
        self.label(right, 'Based on your working ODB render.', 11, MUTED).pack(anchor='w')
        self.label(right, 'DDS (DXT5) with transparency', 11, MUTED).pack(anchor='w', pady=(18, 8))
        self.advanced = tk.Toplevel(root)
        self.advanced.withdraw()
        self.advanced.title('Advanced output settings')
        self.advanced.geometry('420x280')
        self.advanced.resizable(False, False)
        self.advanced.configure(bg=PANEL)
        self.advanced.transient(root)
        self.advanced.protocol('WM_DELETE_WINDOW', self.advanced.withdraw)
        options = tk.Frame(self.advanced, bg=PANEL, padx=22, pady=20)
        options.pack(fill='both', expand=True)
        self.label(options, 'Advanced settings', 16, bold=True).pack(anchor='w', pady=(0, 20))
        self.size = tk.StringVar(value='1024')
        size_row = tk.Frame(options, bg=PANEL)
        size_row.pack(fill='x')
        self.label(size_row, 'Image size', 11, MUTED).pack(side='left')
        self.size_box = ttk.Combobox(size_row, textvariable=self.size, values=('1024', 'Keep original', '512', '2048'), state='readonly', width=13)
        self.size_box.pack(side='right')
        self.mips = tk.BooleanVar(value=False)
        self.mip_check = tk.Checkbutton(options, text='Add smaller image levels', variable=self.mips, bg=PANEL, fg=TEXT, selectcolor=BG, activebackground=PANEL, activeforeground=TEXT)
        self.mip_check.pack(anchor='w', pady=14)
        self.label(options, 'Default: 1024 pixels, one image level (ODB profile).', 10, MUTED).pack(anchor='w')
        self.button(options, 'Done', self.advanced.withdraw, primary=True).pack(anchor='e', pady=14)
        self.advanced_button = self.button(right, 'Advanced options…', self.advanced.deiconify)
        self.advanced_button.pack(fill='x', pady=(18, 12))
        self.summary = tk.StringVar(value='1024 × 1024 pixels · 1 image level')
        self.label(right, '', 10, MUTED, textvariable=self.summary, wraplength=260).pack(anchor='w')
        def update_summary(*args):
            dimensions = 'Original dimensions' if self.size.get() == 'Keep original' else f'{self.size.get()} × {self.size.get()} pixels'
            self.summary.set(dimensions + (' · smaller levels added' if self.mips.get() else ' · 1 image level'))
        self.size.trace_add('write', update_summary)
        self.mips.trace_add('write', update_summary)
        self.save_button = self.button(right, 'Save converted renders', self.save, primary=True)
        self.save_button.pack(fill='x', pady=(18, 12))
        self.save_button.configure(state='disabled')
        self.open_button = self.button(right, 'Open output folder', self.open_output)
        self.open_button.pack(fill='x')
        self.open_button.configure(state='disabled')
        self.progress = ttk.Progressbar(outer, mode='determinate')
        self.progress.pack(fill='x', pady=(20, 10))
        self.message = tk.StringVar(value='Start by choosing a folder or a few render files.')
        self.label(outer, '', 11, TEXT, textvariable=self.message, wraplength=1020).pack(anchor='w')
        self.label(outer, 'Converts image files only. Does not bake or install mods. Test a copy in game before replacing installed renders.', 10, MUTED, wraplength=1020).pack(anchor='w', pady=(14, 0))
        root.after(80, self.poll)

    def label(self, parent, text, size=11, color=TEXT, bold=False, **kwargs):
        return tk.Label(parent, text=text, bg=parent.cget('bg'), fg=color, font=(self.font, size, 'bold' if bold else 'normal'), justify='left', **kwargs)

    def button(self, parent, text, command, primary=False):
        return tk.Button(parent, text=text, command=command, bg=ACCENT if primary else '#2b3853', fg='#101523' if primary else TEXT, activebackground='#bdd0ff', activeforeground=BG, relief='flat', bd=0, padx=16, pady=12, cursor='hand2', disabledforeground='#70809b', font=(self.font, 11, 'bold'))

    def empty(self):
        self.label(self.rows, 'Your renders will appear here', 18, bold=True).pack(anchor='w', pady=(55, 12))
        self.label(self.rows, 'Select a folder to check all its images.\nDDS, PNG, JPG, TGA and WEBP are supported.', 12, MUTED).pack(anchor='w')

    def choose_folder(self):
        folder = filedialog.askdirectory(title='Choose your render folder')
        if not folder:
            return
        try:
            base = Path(folder)
            files = sorted(p for p in base.rglob('*') if p.is_file() and p.suffix.lower() in SUPPORTED)
            self.load(files, base)
        except OSError as exc:
            self.message.set(f'Could not read this folder: {exc}')

    def choose_files(self):
        files = filedialog.askopenfilenames(title='Choose render files', filetypes=[('Render images', '*.dds *.png *.jpg *.jpeg *.tga *.webp')])
        if files:
            self.load([Path(p) for p in files], None)

    def set_busy(self, value):
        self.busy = value
        for button in (self.folder_button, self.file_button, self.advanced_button):
            button.configure(state='disabled' if value else 'normal')
        self.save_button.configure(state='normal' if self.files and not value else 'disabled')
        self.size_box.configure(state='disabled' if value else 'readonly')
        self.mip_check.configure(state='disabled' if value else 'normal')

    def load(self, files, base):
        if self.busy:
            return
        self.files, self.base = files, base
        self.output = None
        self.open_button.configure(state='disabled')
        self.images.clear()
        for child in self.rows.winfo_children():
            child.destroy()
        self.count.configure(text=f'{len(files)} files')
        if not files:
            self.empty()
            self.message.set('No supported images found. Try another folder.')
            self.set_busy(False)
            return
        self.set_busy(True)
        self.progress.configure(value=0, maximum=len(files))
        self.message.set('Checking your images…')
        threading.Thread(target=self.scan, args=(files,), daemon=True).start()

    def scan(self, files):
        good = 0
        for index, path in enumerate(files):
            try:
                data = path.read_bytes()
                info = inspect_dds(data) if path.suffix.lower() == '.dds' else None
                with Image.open(io.BytesIO(data)) as im:
                    im.load()
                    summary = f'{im.width} × {im.height}  ·  {info["format"] if info else im.format}'
                    im.thumbnail((70, 90))
                    preview = im.convert('RGBA')
                    buf = io.BytesIO()
                    preview.save(buf, format='PNG')
                self.events.put(('row', (path, summary, buf.getvalue(), None, index + 1)))
                good += 1
            except Exception as exc:
                self.events.put(('row', (path, '', None, str(exc), index + 1)))
        self.events.put(('scanned', f'{good} of {len(files)} images opened. Save converted copies, then test them in game.'))

    def save(self):
        if self.busy or not self.files:
            return
        destination = filedialog.askdirectory(title='Where should the converted folder be saved?')
        if not destination:
            return
        size = 0 if self.size.get() == 'Keep original' else int(self.size.get())
        mipmaps = self.mips.get()
        self.set_busy(True)
        self.progress.configure(value=0, maximum=len(self.files))
        self.message.set('Converting renders. Your originals will stay untouched…')
        threading.Thread(target=self.convert, args=(Path(destination), size, mipmaps), daemon=True).start()

    def convert(self, destination, size, mipmaps):
        try:
            output = Path(tempfile.mkdtemp(prefix='Converted-renders-', dir=destination))
            report, used = [], set()
            for index, path in enumerate(self.files):
                try:
                    relative = path.relative_to(self.base) if self.base else Path(path.name)
                    target = output / relative.with_suffix('.dds')
                    key = str(target).casefold()
                    if key in used:
                        raise ValueError('Output name conflicts with another file; rename one source and try again')
                    used.add(key)
                    data, detail = normalize(path.read_bytes(), size, mipmaps)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with target.open('xb') as file:
                        file.write(data)
                    report.append(dict(name=str(relative), ok=True, **detail))
                except Exception as exc:
                    report.append(dict(name=str(path), ok=False, error=str(exc)))
                self.events.put(('progress', index + 1))
            (output / 'conversion-report.json').write_text(json.dumps(dict(note='Not verified in game. Original files unchanged.', files=report), indent=2), encoding='utf-8')
            successes = sum(row['ok'] for row in report)
            self.events.put(('saved', (output, f'Saved {successes} renders. {len(report) - successes} could not be converted. Open the output folder for your files and report.')))
        except Exception as exc:
            self.events.put(('failed', f'Could not save: {exc}'))

    def poll(self):
        try:
            while True:
                event, value = self.events.get_nowait()
                if event == 'row':
                    path, summary, preview, error, index = value
                    row = tk.Frame(self.rows, bg='#222e43', padx=12, pady=12)
                    row.pack(fill='x', pady=(0, 8))
                    if preview:
                        image = ImageTk.PhotoImage(Image.open(io.BytesIO(preview)))
                        self.images.append(image)
                        tk.Label(row, image=image, bg='#222e43', width=74, height=85).pack(side='left', padx=(0, 12))
                    text = tk.Frame(row, bg='#222e43')
                    text.pack(side='left', fill='x', expand=True)
                    self.label(text, path.name, 12, bold=True, wraplength=340).pack(anchor='w')
                    self.label(text, 'Could not open' if error else summary, 10, '#ffb6ad' if error else MUTED, wraplength=340).pack(anchor='w', pady=7)
                    self.label(text, error or 'Opened successfully · game compatibility not checked', 10, '#ffb6ad' if error else '#b3d8c4', wraplength=340).pack(anchor='w')
                    self.progress.configure(value=index)
                elif event == 'progress':
                    self.progress.configure(value=value)
                elif event in ('scanned', 'failed'):
                    self.message.set(value)
                    self.set_busy(False)
                elif event == 'saved':
                    self.output, message = value
                    self.message.set(message)
                    self.set_busy(False)
                    self.open_button.configure(state='normal')
        except queue.Empty:
            pass
        self.root.after(80, self.poll)

    def open_output(self):
        if not self.output:
            return
        try:
            if sys.platform == 'win32':
                os.startfile(self.output)
            else:
                subprocess.Popen(['open' if sys.platform == 'darwin' else 'xdg-open', str(self.output)])
        except OSError as exc:
            self.message.set(f'Your files are in {self.output}. Could not open the folder: {exc}')


if __name__ == '__main__':
    root = tk.Tk()
    Workshop(root)
    root.mainloop()

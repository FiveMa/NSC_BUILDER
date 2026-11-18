"""NSCB Studio — desktop frontend for Squirrel and the original launchers."""
import os
from pathlib import Path
from queue import Empty, Queue
import subprocess
import sys
from threading import Event, Thread
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from studio.core import build_arguments, load_catalog
from studio.runner import engine_environment, execute
from studio.workflows import WORKFLOWS, build_jobs

ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / 'py' / 'ztools' / 'squirrel.py'
BG, PANEL, TEXT, MUTED, ACCENT = '#101721', '#1a2635', '#eaf1fa', '#a8b9ce', '#8ce8cf'


class Studio:
    def __init__(self, root):
        self.root = root
        self.options = load_catalog(ENGINE)
        self.files = []
        self.custom = {}
        self.events = Queue(maxsize=500)
        self.stop = None
        self.keys = None
        self.out = tk.StringVar(value=str(Path.home() / 'Documents' / 'NSCB Studio'))
        self.choice = tk.StringVar()
        self.filter = tk.StringVar()
        self.status = tk.StringVar(value='Prêt')
        self.keys_label = tk.StringVar(value='Aucun fichier externe sélectionné')
        root.title('NSCB Studio')
        root.geometry('1120x800')
        root.minsize(980, 700)
        root.configure(bg=BG)
        root.protocol('WM_DELETE_WINDOW', self.close)
        style = ttk.Style(root)
        style.theme_use('clam')
        style.configure('.', background=BG, foreground=TEXT, font=('Segoe UI', 10))
        style.configure('TButton', background=PANEL, padding=(12, 7), bordercolor='#334960')
        style.map('TButton', background=[('active', '#2e4055')], foreground=[('disabled', MUTED)])
        style.configure('Accent.TButton', background=ACCENT, foreground='#10251f')
        style.map('Accent.TButton', background=[('active', '#b6f6e4')])
        style.configure('TEntry', fieldbackground=PANEL, insertcolor=TEXT, bordercolor='#334960')
        style.configure('TCombobox', fieldbackground=PANEL, arrowcolor=TEXT)
        style.map('TCombobox', fieldbackground=[('readonly', PANEL)], foreground=[('readonly', TEXT)])
        style.configure('TNotebook', borderwidth=0)
        style.configure('TNotebook.Tab', background=PANEL, foreground=MUTED, padding=(18, 11))
        style.map('TNotebook.Tab', background=[('selected', '#293b4d')], foreground=[('selected', TEXT)])
        style.configure('TProgressbar', background=ACCENT, troughcolor=PANEL, bordercolor=BG)
        self.style_label('Hero', TEXT, 27, 'bold')
        self.style_label('Heading', TEXT, 15, 'bold')
        self.style_label('Muted', MUTED, 10)
        self.style_label('Brand', ACCENT, 10, 'bold')

        shell = ttk.Frame(root, padding=(23, 16))
        shell.pack(fill='both', expand=True)
        ttk.Label(shell, text='ATELIER LOCAL   /   NINTENDO SWITCH', style='Brand.TLabel').pack(anchor='w')
        ttk.Label(shell, text='NSCB Studio', style='Hero.TLabel').pack(anchor='w')
        ttk.Label(shell, text='Prépare tes fichiers, choisis une opération et suis le résultat en direct.', style='Muted.TLabel').pack(anchor='w', pady=(0, 14))
        self.tabs = ttk.Notebook(shell)
        self.tabs.pack(fill='both', expand=True)
        guide = ttk.Frame(self.tabs, padding=(13, 10))
        expert = ttk.Frame(self.tabs, padding=(13, 10))
        compat = ttk.Frame(self.tabs, padding=(17, 13))
        self.tabs.add(guide, text='Opérations')
        self.tabs.add(expert, text='Catalogue Squirrel')
        self.tabs.add(compat, text='Réglages & modes classiques')
        self.setup_guide(guide)
        self.setup_expert(expert)
        self.setup_compat(compat)

        row = ttk.Frame(shell)
        row.pack(fill='x', pady=(12, 4))
        ttk.Label(row, text='Journal d’activité', style='Heading.TLabel').pack(side='left')
        self.cancel_button = ttk.Button(row, text='Arrêter', command=self.cancel, state='disabled')
        self.cancel_button.pack(side='right')
        ttk.Button(row, text='Copier le journal', command=self.copy_log).pack(side='right', padx=7)
        ttk.Button(row, text='Effacer', command=self.clear_log).pack(side='right')
        self.log = self.textbox(shell, 6, readonly=True)
        foot = ttk.Frame(shell)
        foot.pack(fill='x', pady=(8, 0))
        ttk.Label(foot, textvariable=self.status, style='Brand.TLabel').pack(side='left')
        self.progress = ttk.Progressbar(foot, mode='indeterminate', length=130)
        self.progress.pack(side='right')
        self.select_workflow()
        self.root.after(60, self.poll)

    def style_label(self, name, color, size, weight='normal'):
        ttk.Style().configure(name + '.TLabel', foreground=color, font=('Segoe UI', size, weight))

    def listbox(self, parent, height, **kw):
        box = ttk.Frame(parent)
        box.pack(fill='both', expand=True)
        scroll = ttk.Scrollbar(box)
        scroll.pack(side='right', fill='y')
        lst = tk.Listbox(box, height=height, background=PANEL, foreground=TEXT, bd=0,
                         highlightthickness=1, highlightbackground='#334960', highlightcolor=ACCENT,
                         selectbackground='#365d70', selectforeground='#ffffff', font=('Segoe UI', 10),
                         activestyle='none', exportselection=False, yscrollcommand=scroll.set, **kw)
        lst.pack(side='left', fill='both', expand=True)
        scroll.configure(command=lst.yview)
        return lst

    def textbox(self, parent, height, readonly=False):
        box = ttk.Frame(parent)
        box.pack(fill='both', expand=True)
        scroll = ttk.Scrollbar(box)
        scroll.pack(side='right', fill='y')
        text = tk.Text(box, height=height, width=30, wrap='word', background=PANEL, foreground=TEXT,
                       insertbackground=TEXT, padx=8, pady=7, bd=0, highlightthickness=1,
                       highlightbackground='#334960', highlightcolor=ACCENT,
                       font=('Consolas', 10), yscrollcommand=scroll.set)
        text.pack(side='left', fill='both', expand=True)
        scroll.configure(command=text.yview)
        if readonly:
            text.configure(state='disabled')
        return text

    def setup_guide(self, tab):
        left = ttk.Frame(tab, width=265)
        left.pack(side='left', fill='y', padx=(0, 14))
        left.pack_propagate(False)
        ttk.Label(left, text='Choisir une opération', style='Heading.TLabel').pack(anchor='w', pady=(0, 6))
        self.workflow_list = self.listbox(left, 11)
        for item in WORKFLOWS:
            self.workflow_list.insert('end', f'  {item.category}  ·  {item.title}')
        if WORKFLOWS:
            self.workflow_list.selection_set(0)
        self.workflow_list.bind('<<ListboxSelect>>', lambda _: self.select_workflow())

        form = ttk.Frame(tab)
        form.pack(side='left', fill='both', expand=True)
        self.workflow_title = ttk.Label(form, style='Heading.TLabel')
        self.workflow_title.pack(anchor='w')
        self.workflow_desc = ttk.Label(form, style='Muted.TLabel', wraplength=620, justify='left')
        self.workflow_desc.pack(anchor='w', pady=(0, 6))
        ttk.Label(form, text='01   Fichiers source', style='Brand.TLabel').pack(anchor='w')
        self.file_list = self.listbox(form, 3, selectmode='extended')
        row = ttk.Frame(form)
        row.pack(fill='x', pady=(5, 5))
        ttk.Button(row, text='+ Ajouter des fichiers', command=self.add_files).pack(side='left')
        ttk.Button(row, text='Retirer la sélection', command=self.remove_files).pack(side='left', padx=7)
        ttk.Button(row, text='Vider', command=self.reset_files).pack(side='left')
        self.output_row = ttk.Frame(form)
        ttk.Label(self.output_row, text='02   Destination', style='Brand.TLabel').pack(side='left')
        ttk.Entry(self.output_row, textvariable=self.out).pack(side='left', fill='x', expand=True, padx=8)
        ttk.Button(self.output_row, text='Parcourir', command=self.output_dialog).pack(side='left')
        self.choice_row = ttk.Frame(form)
        ttk.Label(self.choice_row, text='Option', style='Brand.TLabel').pack(side='left')
        self.choice_widget = ttk.Combobox(self.choice_row, state='readonly', textvariable=self.choice)
        self.choice_widget.pack(side='left', padx=8)
        self.run_row = ttk.Frame(form)
        self.run_row.pack(fill='x', pady=(4, 0))
        self.run_button = ttk.Button(self.run_row, text='Lancer l’opération', style='Accent.TButton', command=self.run_guided)
        self.run_button.pack(side='right')

    def setup_expert(self, tab):
        left = ttk.Frame(tab, width=300)
        left.pack(side='left', fill='y', padx=(0, 14))
        left.pack_propagate(False)
        ttk.Label(left, text=f'{len(self.options)} arguments disponibles', style='Heading.TLabel').pack(anchor='w')
        entry = ttk.Entry(left, textvariable=self.filter)
        entry.pack(fill='x', pady=7)
        ttk.Label(left, text='Filtrer par argument ou description', style='Muted.TLabel').pack(anchor='w')
        self.option_list = self.listbox(left, 10)
        self.option_list.bind('<<ListboxSelect>>', lambda _: self.select_option())
        self.filter.trace_add('write', lambda *_: self.filter_options())

        right = ttk.Frame(tab)
        right.pack(side='left', fill='both', expand=True)
        self.option_title = ttk.Label(right, style='Heading.TLabel')
        self.option_title.pack(anchor='w')
        self.option_desc = ttk.Label(right, wraplength=570, justify='left', style='Muted.TLabel')
        self.option_desc.pack(anchor='w')
        ttk.Label(right, text='Saisis une valeur par ligne. Les espaces sont conservés.').pack(anchor='w', pady=(5, 0))
        self.values = self.textbox(right, 2)
        row = ttk.Frame(right)
        row.pack(fill='x', pady=5)
        ttk.Button(row, text='Insérer des fichiers', command=self.expert_files).pack(side='left')
        ttk.Button(row, text='Définir cet argument', command=self.put_option).pack(side='right')
        ttk.Label(right, text='Arguments prêts à exécuter', style='Brand.TLabel').pack(anchor='w')
        self.custom_list = self.listbox(right, 3)
        self.custom_list.bind('<Double-Button-1>', lambda _: self.edit_option())
        row = ttk.Frame(right)
        row.pack(fill='x', pady=(5, 0))
        ttk.Button(row, text='Retirer', command=self.remove_option).pack(side='left')
        ttk.Button(row, text='Tout effacer', command=self.clear_options).pack(side='left', padx=7)
        self.expert_run = ttk.Button(row, text='Exécuter ces arguments', style='Accent.TButton', command=self.run_expert)
        self.expert_run.pack(side='right')
        self.filter_options()

    def setup_compat(self, tab):
        ttk.Label(tab, text='Fichier de clés local', style='Heading.TLabel').pack(anchor='w')
        ttk.Label(tab, text='Son contenu n’est ni copié dans le projet ni affiché. La sélection vaut pour cette session.', style='Muted.TLabel', wraplength=820).pack(anchor='w')
        row = ttk.Frame(tab)
        row.pack(fill='x', pady=(8, 14))
        ttk.Button(row, text='Choisir le fichier…', command=self.choose_keys).pack(side='left')
        ttk.Button(row, text='Oublier', command=self.forget_keys).pack(side='left', padx=6)
        ttk.Label(row, textvariable=self.keys_label, style='Muted.TLabel').pack(side='left', padx=6)
        ttk.Separator(tab).pack(fill='x', pady=(0, 12))
        ttk.Label(tab, text='Compatibilité avec les modes d’origine', style='Heading.TLabel').pack(anchor='w')
        ttk.Label(tab, text='Les fonctions dépendant du matériel, du cloud et des menus Batch restent dans leurs interfaces d’origine.', style='Muted.TLabel', wraplength=820).pack(anchor='w', pady=(0, 8))
        for title, script, detail in [
            ('Menu NSCB', 'NSCB.bat', 'Configuration, tâches différées, mode historique, Google Drive et DBI/MTP.'),
            ('Interface File Info', 'Interface.bat', 'Interface navigateur d’origine : illustrations, métadonnées et bibliothèques.'),
            ('Serveur', 'Server.bat', 'Lanceur serveur d’origine. Vérifie la configuration réseau avant le lancement.'),
        ]:
            row = ttk.Frame(tab)
            row.pack(fill='x', pady=3)
            ttk.Button(row, text=title, width=19, command=lambda name=script: self.legacy(name)).pack(side='left')
            ttk.Label(row, text=detail, style='Muted.TLabel', wraplength=650).pack(side='left', padx=10)
        ttk.Button(tab, text='Ouvrir la documentation Studio', command=lambda: os.startfile(ROOT / 'studio' / 'README.md')).pack(anchor='w', pady=(11, 0))

    def select_workflow(self):
        sel = self.workflow_list.curselection()
        if not sel:
            return
        workflow = WORKFLOWS[sel[0]]
        self.workflow = workflow
        self.workflow_title.configure(text=workflow.title)
        suffix = f' Formats : {", ".join(workflow.extensions)}.' if workflow.extensions else ''
        self.workflow_desc.configure(text=workflow.description + suffix)
        self.output_row.pack_forget()
        self.choice_row.pack_forget()
        if workflow.output:
            self.output_row.pack(fill='x', before=self.run_row, pady=(1, 4))
        if workflow.choices:
            self.choice_widget.configure(values=workflow.choices)
            self.choice.set(workflow.choices[0])
            self.choice_row.pack(fill='x', before=self.run_row)
        else:
            self.choice.set('')

    def add_files(self):
        ext = self.workflow.extensions
        formats = [('Formats de l’opération', ' '.join('*' + e for e in ext)), ('Tous les fichiers', '*')] if ext else [('Tous les fichiers', '*')]
        for value in filedialog.askopenfilenames(parent=self.root, filetypes=formats):
            path = Path(value)
            if path not in self.files:
                self.files.append(path)
                self.file_list.insert('end', str(path))

    def remove_files(self):
        for i in reversed(self.file_list.curselection()):
            del self.files[i]
            self.file_list.delete(i)

    def reset_files(self):
        self.files.clear()
        self.file_list.delete(0, 'end')

    def output_dialog(self):
        current = Path(self.out.get()).expanduser()
        selected = filedialog.askdirectory(parent=self.root, initialdir=current if current.is_dir() else Path.home())
        if selected:
            self.out.set(selected)

    def choose_keys(self):
        selected = filedialog.askopenfilename(parent=self.root, initialdir=Path.home() / 'Desktop', filetypes=[('Fichiers de clés', '*.txt *.keys'), ('Tous les fichiers', '*')])
        if selected:
            self.keys = Path(selected)
            self.keys_label.set(f'Sélectionné : {self.keys.name}')

    def forget_keys(self):
        self.keys = None
        self.keys_label.set('Aucun fichier externe sélectionné')

    def filter_options(self):
        query = self.filter.get().casefold()
        self.matches = [o for o in self.options if query in (' '.join((o.flag, *o.aliases)) + ' ' + o.help).casefold()]
        self.option_list.delete(0, 'end')
        for opt in self.matches:
            self.option_list.insert('end', '  ' + opt.flag)
        if self.matches:
            self.option_list.selection_set(0)
        self.select_option()

    def select_option(self):
        selected = self.option_list.curselection()
        self.option = self.matches[selected[0]] if selected else None
        self.values.delete('1.0', 'end')
        if self.option:
            opt = self.option
            self.option_title.configure(text=opt.flag)
            self.option_desc.configure(text=opt.help or 'Argument interne : consulter la documentation du moteur.')
            self.values.insert('1.0', '\n'.join(self.custom.get(opt.flag, (None, []))[1]))
        else:
            self.option_title.configure(text='Aucun résultat')
            self.option_desc.configure(text='Essaie une autre recherche.')

    def expert_files(self):
        paths = filedialog.askopenfilenames(parent=self.root)
        if paths:
            existing = self.values.get('1.0', 'end-1c')
            self.values.insert('end-1c', ('\n' if existing else '') + '\n'.join(paths))

    def put_option(self):
        if not self.option:
            return
        values = [x for x in self.values.get('1.0', 'end-1c').split('\n') if x != '']
        item = self.option, values
        try:
            build_arguments([item])
        except ValueError as exc:
            self.alert(str(exc))
            return
        self.custom[self.option.flag] = item
        self.refresh_custom()

    def refresh_custom(self):
        self.custom_list.delete(0, 'end')
        for opt, vals in self.custom.values():
            self.custom_list.insert('end', f'  {opt.flag}    ·    {len(vals)} valeur(s)')

    def edit_option(self):
        sel = self.custom_list.curselection()
        if sel:
            opt, _ = list(self.custom.values())[sel[0]]
            self.filter.set(opt.flag)
            idx = self.matches.index(opt)
            self.option_list.selection_clear(0, 'end')
            self.option_list.selection_set(idx)
            self.option_list.see(idx)
            self.select_option()
            self.values.focus_set()

    def remove_option(self):
        sel = self.custom_list.curselection()
        if sel:
            del self.custom[list(self.custom)[sel[0]]]
            self.refresh_custom()
            self.select_option()

    def clear_options(self):
        self.custom.clear()
        self.refresh_custom()
        self.select_option()

    def alert(self, detail):
        messagebox.showerror('NSCB Studio', detail, parent=self.root)

    def run_guided(self):
        if self.stop is not None:
            return
        workflow = self.workflow
        if workflow.caution and not messagebox.askokcancel('Confirmer', workflow.caution, parent=self.root):
            return
        try:
            raw = self.out.get().strip()
            if workflow.output and not raw:
                raise ValueError('Choisis un dossier de destination.')
            output = Path(raw).expanduser().resolve() if workflow.output else None
            jobs = build_jobs(workflow, self.files, output, self.choice.get())
            if output:
                output.mkdir(parents=True, exist_ok=True)
            self.start(workflow.title, jobs)
        except (ValueError, OSError) as exc:
            self.alert(str(exc))

    def run_expert(self):
        if not self.custom:
            return self.alert('Définis au moins un argument dans le catalogue.')
        try:
            args = build_arguments(self.custom.values())
        except ValueError as exc:
            return self.alert(str(exc))
        if messagebox.askokcancel('Vérifier les arguments', 'Le moteur applique les arguments sélectionnés directement. Certaines commandes peuvent modifier ou supprimer des fichiers. Continuer ?', parent=self.root):
            self.start('Commande Squirrel', [args])

    def legacy(self, script):
        if os.name != 'nt':
            return self.alert('Les lanceurs historiques nécessitent Windows.')
        if script == 'Server.bat' and not messagebox.askokcancel('Démarrer le serveur ?', 'Le serveur d’origine peut écouter sur le réseau selon sa configuration.', parent=self.root):
            return
        try:
            env = engine_environment(self.keys)
            env['NSCB_STUDIO_PYTHON'] = str(Path(sys.executable).with_name('python.exe'))
            env['NSCB_STUDIO_PYTHONW'] = str(Path(sys.executable).with_name('pythonw.exe'))
            subprocess.Popen([os.environ.get('COMSPEC', 'cmd.exe'), '/d', '/c', script], cwd=ROOT / 'py', env=env, creationflags=subprocess.CREATE_NEW_CONSOLE)
        except OSError as exc:
            self.alert(str(exc))

    def start(self, name, jobs):
        if self.stop is not None:
            return
        if self.keys is not None and not self.keys.is_file():
            return self.alert('Le fichier de clés sélectionné est introuvable.')
        self.stop = stop = Event()
        self.cancel_button.configure(state='normal')
        self.run_button.configure(state='disabled')
        self.expert_run.configure(state='disabled')
        self.status.set('En cours : ' + name)
        self.progress.start(12)
        self.append_log('\n' + name + '\n')
        env = engine_environment(self.keys)

        def worker():
            def emit(line):
                self.events.put(('line', line))
            try:
                binary = Path(sys.executable)
                console = binary.with_name('python.exe')
                if binary.name.lower() == 'pythonw.exe' and console.is_file():
                    binary = console
                code = execute([str(binary), '-u', str(ENGINE)], jobs, ENGINE.parent, env, stop, emit)
                result = ('Arrêt demandé — vérifie les fichiers partiels.' if code is None else
                          'Moteur terminé — consulte le journal.' if code == 0 else f'Erreur moteur (code {code})')
            except (OSError, ValueError) as exc:
                emit(f'Impossible de lancer Squirrel : {exc}\n')
                result = 'Échec du lancement'
            self.events.put(('done', result))
        Thread(target=worker, daemon=True).start()

    def cancel(self):
        if self.stop is not None:
            self.stop.set()
            self.cancel_button.configure(state='disabled')
            self.status.set('Arrêt en cours…')

    def poll(self):
        lines = []
        for _ in range(120):
            try:
                kind, value = self.events.get_nowait()
            except Empty:
                break
            if kind == 'line':
                lines.append(value)
            else:
                lines.append('\n' + value + '\n')
                self.stop = None
                self.progress.stop()
                self.status.set(value)
                self.run_button.configure(state='normal')
                self.expert_run.configure(state='normal')
                self.cancel_button.configure(state='disabled')
        if lines:
            self.append_log(''.join(lines))
        self.root.after(60, self.poll)

    def append_log(self, text):
        self.log.configure(state='normal')
        follow = self.log.yview()[1] >= 0.995
        self.log.insert('end', text)
        lines = int(self.log.index('end-1c').split('.')[0])
        if lines > 4000:
            self.log.delete('1.0', f'{lines - 3999}.0')
        if follow:
            self.log.see('end')
        self.log.configure(state='disabled')

    def copy_log(self):
        self.root.clipboard_clear()
        self.root.clipboard_append(self.log.get('1.0', 'end-1c'))

    def clear_log(self):
        self.log.configure(state='normal')
        self.log.delete('1.0', 'end')
        self.log.configure(state='disabled')

    def close(self):
        if self.stop is not None:
            if messagebox.askokcancel('Tâche en cours', 'Arrêter le traitement ? Les fichiers partiels ne seront pas supprimés.', parent=self.root):
                self.cancel()
            return
        self.root.destroy()


def main():
    root = tk.Tk()
    Studio(root)
    root.mainloop()


if __name__ == '__main__':
    main()

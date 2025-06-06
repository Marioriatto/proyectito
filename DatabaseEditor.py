import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import sqlite3
import os

class DatabaseEditor:
    def __init__(self, root):
        self.root = root
        self.root.title("Database Editor")
        self.root.geometry("900x600")

        self.db_path = None
        self.conn = None
        self.cursor = None

        self.init_ui()

    def init_ui(self):
        self.toolbar = ttk.Frame(self.root)
        self.toolbar.pack(side=tk.TOP, fill=tk.X)

        ttk.Button(self.toolbar, text="New Database", command=self.create_database).pack(side=tk.LEFT, padx=5, pady=5)
        ttk.Button(self.toolbar, text="Open Database", command=self.open_database).pack(side=tk.LEFT, padx=5, pady=5)
        ttk.Button(self.toolbar, text="Update View", command=self.populate_tabs).pack(side=tk.LEFT, padx=5, pady=5)

        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        self.tabs = {}
        for name in ["Rooms", "Teachers", "Subjects", "Groups", "Timeslots"]:
            frame = ttk.Frame(self.notebook)
            self.tabs[name] = frame
            self.notebook.add(frame, text=name)

    def create_database(self):
        path = filedialog.asksaveasfilename(defaultextension=".db", filetypes=[("SQLite DB", "*.db")])
        if not path:
            return

        self.db_path = path
        self.conn = sqlite3.connect(self.db_path)
        self.cursor = self.conn.cursor()

        self.cursor.executescript("""
        CREATE TABLE IF NOT EXISTS rooms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            type TEXT NOT NULL,
            capacity INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS teachers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS subjects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            requires_lab INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS groups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject_id INTEGER,
            teacher_id INTEGER,
            student_count INTEGER,
            FOREIGN KEY(subject_id) REFERENCES subjects(id),
            FOREIGN KEY(teacher_id) REFERENCES teachers(id)
        );
        CREATE TABLE IF NOT EXISTS timeslots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            day INTEGER NOT NULL,
            slot INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS group_schedule (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id INTEGER,
            room_id INTEGER,
            timeslot_id INTEGER,
            FOREIGN KEY(group_id) REFERENCES groups(id),
            FOREIGN KEY(room_id) REFERENCES rooms(id),
            FOREIGN KEY(timeslot_id) REFERENCES timeslots(id)
        );
        CREATE INDEX IF NOT EXISTS idx_group_schedule_group ON group_schedule(group_id);
        CREATE INDEX IF NOT EXISTS idx_group_schedule_room ON group_schedule(room_id);
        CREATE INDEX IF NOT EXISTS idx_group_schedule_timeslot ON group_schedule(timeslot_id);
        CREATE TRIGGER IF NOT EXISTS Validate 
            BEFORE INSERT ON groups FOR EACH ROW 
            WHEN (SELECT COUNT(*) FROM groups WHERE subject_id = new.subject_id and teacher_id = new.teacher_id) > 0
                BEGIN
                    SELECT RAISE(ABORT, 'You are trying to insert a duplicate!');
                END
        """)
        self.conn.commit()
        messagebox.showinfo("Success", "Database created successfully.")
        self.populate_tabs()

    def open_database(self):
        path = filedialog.askopenfilename(filetypes=[("SQLite DB", "*.db")])
        if not path or not os.path.exists(path):
            return
        self.db_path = path
        self.conn = sqlite3.connect(self.db_path)
        self.cursor = self.conn.cursor()
        self.populate_tabs()

    def populate_tabs(self):
        for name in self.tabs:
            for widget in self.tabs[name].winfo_children():
                widget.destroy()

        self.init_rooms_tab()
        self.init_teachers_tab()
        self.init_subjects_tab()
        self.init_groups_tab()
        self.init_timeslots_tab()

    def init_rooms_tab(self):
        self.init_table_editor(
            "Rooms",
            ["Name", "Type", "Capacity"],
            lambda values: self.cursor.execute("INSERT INTO rooms (name, type, capacity) VALUES (?, ?, ?)", values),
            lambda: self.cursor.execute("SELECT id, name, type, capacity FROM rooms"),
            lambda rid: self.cursor.execute("DELETE FROM rooms WHERE id=?", (rid,)),
            custom_widgets={1: ttk.Combobox, 'choices': ["standard", "lab", "auditorium"]}
        )

    def init_teachers_tab(self):
        self.init_table_editor(
            "Teachers",
            ["Name"],
            lambda values: self.cursor.execute("INSERT INTO teachers (name) VALUES (?)", values),
            lambda: self.cursor.execute("SELECT id, name FROM teachers"),
            lambda rid: self.cursor.execute("DELETE FROM teachers WHERE id=?", (rid,))
        )

    def init_subjects_tab(self):
        self.init_table_editor(
            "Subjects",
            ["Name", "Requires Lab (0/1)"],
            lambda values: self.cursor.execute("INSERT INTO subjects (name, requires_lab) VALUES (?, ?)", values),
            lambda: self.cursor.execute("SELECT id, name, requires_lab FROM subjects"),
            lambda rid: self.cursor.execute("DELETE FROM subjects WHERE id=?", (rid,))
        )

    def init_groups_tab(self):
        frame = self.tabs["Groups"]

        ttk.Label(frame, text="Subject").grid(row=0, column=0)
        ttk.Label(frame, text="Teacher").grid(row=0, column=1)
        ttk.Label(frame, text="Student Count").grid(row=0, column=2)

        subject_var = tk.StringVar()
        teacher_var = tk.StringVar()
        count_var = tk.StringVar()

        self.cursor.execute("SELECT id, name FROM subjects")
        subjects = self.cursor.fetchall()
        subject_map = {f"{name} (ID: {sid})": sid for sid, name in subjects}
        subject_cb = ttk.Combobox(frame, textvariable=subject_var, values=list(subject_map.keys()))
        subject_cb.grid(row=1, column=0)

        self.cursor.execute("SELECT id, name FROM teachers")
        teachers = self.cursor.fetchall()
        teacher_map = {f"{name} (ID: {tid})": tid for tid, name in teachers}
        teacher_cb = ttk.Combobox(frame, textvariable=teacher_var, values=list(teacher_map.keys()))
        teacher_cb.grid(row=1, column=1)

        count_entry = ttk.Entry(frame, textvariable=count_var)
        count_entry.grid(row=1, column=2)

        def add_group():
            try:
                subject_id = subject_map[subject_var.get()]
                teacher_id = teacher_map[teacher_var.get()]
                try:
                    count = int(count_var.get())
                except Exception:
                    count = 0
                self.cursor.execute("INSERT INTO groups (subject_id, teacher_id, student_count) VALUES (?, ?, ?)",
                                    (subject_id, teacher_id, count))
                self.conn.commit()
                refresh_table()
            except Exception as e:
                messagebox.showerror("Insert Error", str(e))

        def delete_selected():
            selected = table.selection()
            if not selected:
                return
            try:
                for sel in selected:
                    rid = table.item(sel)["values"][0]
                    self.cursor.execute("DELETE FROM groups WHERE id=?", (rid,))
                self.conn.commit()
                refresh_table()
            except Exception as e:
                messagebox.showerror("Delete Error", str(e))

        ttk.Button(frame, text="Add", command=add_group).grid(row=2, column=0, pady=5)
        ttk.Button(frame, text="Delete", command=delete_selected).grid(row=2, column=1, pady=5)

        table = ttk.Treeview(frame, columns=(0, 1, 2, 3), show="headings", height=15)
        table.grid(row=3, column=0, columnspan=3)

        for i, col in enumerate(["ID", "Subject ID", "Teacher ID", "Student Count"]):
            table.heading(i, text=col)
            table.column(i, width=120)

        def refresh_table():
            for row in table.get_children():
                table.delete(row)
            self.cursor.execute("SELECT id, subject_id, teacher_id, student_count FROM groups")
            for row in self.cursor.fetchall():
                table.insert("", "end", values=row)

        refresh_table()

    def init_timeslots_tab(self):
        frame = self.tabs["Timeslots"]

        ttk.Label(frame, text="Timeslots (Day 0–4, Slot 0–5)").pack(pady=5)

        ttk.Button(frame, text="Generate Default Timeslots", command=self.generate_default_timeslots).pack(pady=5)

        table = ttk.Treeview(frame, columns=(0, 1, 2), show="headings", height=15)
        table.pack(fill=tk.BOTH, expand=True)

        table.heading(0, text="ID")
        table.heading(1, text="Day")
        table.heading(2, text="Slot")

        def refresh_table():
            for row in table.get_children():
                table.delete(row)
            self.cursor.execute("SELECT id, day, slot FROM timeslots ORDER BY day, slot")
            for row in self.cursor.fetchall():
                table.insert("", "end", values=row)

        self.timeslot_table_refresh = refresh_table  # Save for use after button press
        refresh_table()
    
    def generate_default_timeslots(self):
        try:
            self.cursor.execute("DELETE FROM timeslots")
            for day in range(5):
                for slot in range(6):
                    self.cursor.execute("INSERT INTO timeslots (day, slot) VALUES (?, ?)", (day, slot))
            self.conn.commit()
            self.timeslot_table_refresh()
            messagebox.showinfo("Success", "Timeslots reset to Monday–Friday with 6 slots per day.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate timeslots: {e}")


    def init_table_editor(self, tab_name, fields, insert_callback, select_callback, delete_callback, custom_widgets=None):
        frame = self.tabs[tab_name]

        entry_vars = []
        entries = []
        for idx, field in enumerate(fields):
            ttk.Label(frame, text=field).grid(row=0, column=idx)
            var = tk.StringVar()
            widget_class = ttk.Entry
            if custom_widgets and idx in custom_widgets:
                widget_class = custom_widgets[idx]
                widget = widget_class(frame, textvariable=var, values=custom_widgets['choices'][idx] if isinstance(custom_widgets['choices'], dict) else custom_widgets['choices'])
            else:
                widget = widget_class(frame, textvariable=var)
            widget.grid(row=1, column=idx)
            entry_vars.append(var)
            entries.append(widget)

        def add_entry():
            try:
                values = tuple(var.get() for var in entry_vars)
                insert_callback(values)
                self.conn.commit()
                refresh_table()
            except Exception as e:
                messagebox.showerror("Insert Error", str(e))

        def delete_selected():
            selected = table.selection()
            if not selected:
                return
            try:
                for sel in selected:
                    rid = table.item(sel)["values"][0]
                    delete_callback(rid)
                self.conn.commit()
                refresh_table()
            except Exception as e:
                messagebox.showerror("Delete Error", str(e))

        ttk.Button(frame, text="Add", command=add_entry).grid(row=2, column=0, pady=5)
        ttk.Button(frame, text="Delete", command=delete_selected).grid(row=2, column=1, pady=5)

        table = ttk.Treeview(frame, columns=list(range(len(fields)+1)), show="headings", height=15)
        table.grid(row=3, column=0, columnspan=len(fields))

        headers = ["ID"] + fields
        for i, header in enumerate(headers):
            table.heading(i, text=header)
            table.column(i, width=120)

        def refresh_table():
            for row in table.get_children():
                table.delete(row)
            for row in select_callback():
                table.insert("", "end", values=row)

        refresh_table()


if __name__ == "__main__":
    root = tk.Tk()
    app = DatabaseEditor(root)
    root.mainloop()

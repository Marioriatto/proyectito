import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import sqlite3
import os

VALID_ROOM_TYPES = {"standard", "lab", "auditorium"}

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
        ttk.Button(self.toolbar, text="Refresh", command=self.populate_tabs).pack(side=tk.LEFT, padx=5, pady=5)

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

        self.cursor.executescript(""" ... """)  # Keep your full SQL schema here as-is.
        self.conn.commit()
        messagebox.showinfo("Success", "Database created with triggers.")
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
            self.insert_room,
            lambda: self.cursor.execute("SELECT id, name, type, capacity FROM rooms"),
            lambda rid: self.cursor.execute("DELETE FROM rooms WHERE id=?", (rid,)),
            custom_widgets={1: ttk.Combobox, 'choices': ["standard", "lab", "auditorium"]}
        )

    def insert_room(self, values):
        name, type_, capacity = values
        if not name.strip() or not type_.strip() or not capacity.strip():
            raise ValueError("All fields must be filled.")
        if type_.lower() not in VALID_ROOM_TYPES:
            raise ValueError("Invalid room type.")
        self.cursor.execute("INSERT INTO rooms (name, type, capacity) VALUES (?, ?, ?)", (name, type_, int(capacity)))

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

        # Input labels and fields
        ttk.Label(frame, text="Group Name").grid(row=0, column=0)
        ttk.Label(frame, text="Subject").grid(row=0, column=1)
        ttk.Label(frame, text="Teacher").grid(row=0, column=2)
        ttk.Label(frame, text="Student Count").grid(row=0, column=3)
        ttk.Label(frame, text="Frecuency").grid(row=0, column=4)

        name_var = tk.StringVar()
        subject_var = tk.StringVar()
        teacher_var = tk.StringVar()
        count_var = tk.StringVar()
        frecuency_var = tk.StringVar()

        ttk.Entry(frame, textvariable=name_var).grid(row=1, column=0)

        self.cursor.execute("SELECT id, name FROM subjects")
        subjects = self.cursor.fetchall()
        subject_map = {f"{name} (ID: {sid})": sid for sid, name in subjects}
        ttk.Combobox(frame, textvariable=subject_var, values=list(subject_map.keys())).grid(row=1, column=1)

        self.cursor.execute("SELECT id, name FROM teachers")
        teachers = self.cursor.fetchall()
        teacher_map = {f"{name} (ID: {tid})": tid for tid, name in teachers}
        ttk.Combobox(frame, textvariable=teacher_var, values=list(teacher_map.keys())).grid(row=1, column=2)

        ttk.Entry(frame, textvariable=count_var).grid(row=1, column=3)
        ttk.Entry(frame, textvariable=frecuency_var).grid(row=1, column=4)

        def add_group():
            try:
                name = name_var.get().strip()
                if not name:
                    raise ValueError("Group name cannot be empty.")
                subject_id = subject_map[subject_var.get()]
                teacher_id = teacher_map[teacher_var.get()]
                count = int(count_var.get())
                frecuency = int(frecuency_var.get())
                if count <= 0 or frecuency <= 0:
                    raise ValueError("Counts must be positive.")
                self.cursor.execute(
                    "INSERT INTO groups (name, subject_id, teacher_id, student_count, frecuency_count) VALUES (?, ?, ?, ?, ?)",
                    (name, subject_id, teacher_id, count, frecuency))
                self.conn.commit()
                refresh_table()
            except Exception as e:
                messagebox.showerror("Insert Error", str(e))

        def delete_selected():
            for sel in table.selection():
                rid = table.item(sel)["values"][0]
                self.cursor.execute("DELETE FROM groups WHERE id=?", (rid,))
            self.conn.commit()
            refresh_table()

        ttk.Button(frame, text="Add", command=add_group).grid(row=2, column=0, pady=5)
        ttk.Button(frame, text="Delete", command=delete_selected).grid(row=2, column=1, pady=5)

        table = ttk.Treeview(frame, columns=(0, 1, 2, 3, 4, 5), show="headings", height=15)
        table.grid(row=3, column=0, columnspan=6)

        for i, col in enumerate(["ID", "Group Name", "Subject ID", "Teacher ID", "Student Count", "Weekly Frecuency"]):
            table.heading(i, text=col)
            table.column(i, width=120)

        def refresh_table():
            for row in table.get_children():
                table.delete(row)
            self.cursor.execute("SELECT id, name, subject_id, teacher_id, student_count, frecuency_count FROM groups")
            for row in self.cursor.fetchall():
                table.insert("", "end", values=row)

        refresh_table()

    def init_timeslots_tab(self):
        frame = self.tabs["Timeslots"]

        ttk.Label(frame, text="Timeslots (5 Days, 6 Slots)").pack(pady=5)
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

        self.timeslot_table_refresh = refresh_table
        refresh_table()

    def generate_default_timeslots(self):
        try:
            self.cursor.execute("DELETE FROM timeslots")
            for day in range(5):
                for slot in range(6):
                    self.cursor.execute("INSERT INTO timeslots (day, slot) VALUES (?, ?)", (day, slot))
            self.conn.commit()
            self.timeslot_table_refresh()
            messagebox.showinfo("Success", "Timeslots reset.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate timeslots: {e}")

    def init_table_editor(self, tab_name, fields, insert_callback, select_callback, delete_callback, custom_widgets=None):
        frame = self.tabs[tab_name]
        entry_vars = []
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

        def add_entry():
            try:
                values = tuple(var.get().strip() for var in entry_vars)
                if any(val == "" for val in values):
                    raise ValueError("No field can be empty.")
                insert_callback(values)
                self.conn.commit()
                refresh_table()
            except Exception as e:
                messagebox.showerror("Insert Error", str(e))

        def delete_selected():
            for sel in table.selection():
                rid = table.item(sel)["values"][0]
                delete_callback(rid)
            self.conn.commit()
            refresh_table()

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

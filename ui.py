import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import sqlite3
import importlib.util
import os
from collections import defaultdict
import threading
import subprocess
import sys

class ScheduleApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Schedule Viewer")
        self.root.geometry("1200x600")
        self.root.rowconfigure(0, weight=1)
        self.root.columnconfigure(0, weight=1)

        self.db_path = None

        # TreeView Main frame
        self.main_frame = ttk.Frame(root)
        self.main_frame.grid(row=0, column=0, sticky="nsew")
        self.main_frame.rowconfigure(0, weight=1)
        self.main_frame.columnconfigure(0, weight=1)

        self.tree = ttk.Treeview(self.main_frame, show="headings", height=6)

        style = ttk.Style()
        style.configure("Treeview", rowheight=80, font=("Arial", 10))
        style.configure("Treeview.Heading", font=("Arial", 10, "bold"))

        self.tree.grid(row=0, column=0, sticky="nsew")
        
        # Scrollbars
        vsb = ttk.Scrollbar(self.main_frame, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(self.main_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")

        # Bottom fixed navbar
        self.control_frame = ttk.Frame(root)
        self.control_frame.grid(row=1, column=0, sticky="ew")
        self.control_frame.columnconfigure((0, 1, 2), weight=1)

        self.select_button = ttk.Button(self.control_frame, text="Select Database", command=self.select_database)
        self.select_button.grid(row=0, column=0, padx=10, pady=10)

        self.solve_button = ttk.Button(self.control_frame, text="Solve Schedule", command=self.solve_schedule, state="disabled")
        self.solve_button.grid(row=0, column=1, padx=10, pady=10)

        self.edit_db_button = ttk.Button(self.control_frame, text="Edit Database", command=self.launch_editor)
        self.edit_db_button.grid(row=0, column=2, padx=10, pady=10)

        self.refresh_button = ttk.Button(self.control_frame, text="Refresh View", command=self.load_schedule, state="disabled")
        self.refresh_button.grid(row=0, column=3, padx=10, pady=10)

        # selector dropdowns viewer
        self.view_type_var = tk.StringVar(value="Full Schedule")
        self.view_selector = ttk.Combobox(self.control_frame, textvariable=self.view_type_var, values=["Full Schedule", "Group", "Teacher", "Room"], state="readonly")
        self.view_selector.grid(row=0, column=4, padx=10)
        self.view_selector.bind("<<ComboboxSelected>>", self.update_filter_options)

        self.view_value_var = tk.StringVar()
        self.value_selector = ttk.Combobox(self.control_frame, textvariable=self.view_value_var, state="readonly")
        self.value_selector.grid(row=0, column=5, padx=10)

        self.apply_button = ttk.Button(self.control_frame, text="Apply View", command=self.load_schedule)
        self.apply_button.grid(row=0, column=6, padx=10)

        self.init_empty_grid()
        
    def init_empty_grid(self):
        self.drag_source = None
        self.tree.bind("<ButtonPress-1>", self.on_drag_start)
        self.tree.bind("<ButtonRelease-1>", self.on_drag_release)
        self.tree["columns"] = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
        for col in self.tree["columns"]:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=240, anchor="center")
        for slot_index in range(6):
            self.tree.insert("", "end", iid=slot_index, values=["" for _ in range(5)])
        
        

    def select_database(self):
        path = filedialog.askopenfilename(title="Select database", filetypes=[("SQLite DB", "*.db")])
        if not path or not os.path.exists(path):
            messagebox.showerror("Database Error", "Valid database file not selected.")
            return
        self.db_path = path
        self.solve_button.config(state="normal")
        self.refresh_button.config(state="normal")
        self.update_filter_options()
        self.load_schedule()

    def connect(self):
        return sqlite3.connect(self.db_path)

    def load_schedule(self):
        if not self.db_path:
            return

        try:
            for row in self.tree.get_children():
                self.tree.delete(row)

            conn = self.connect()
            cursor = conn.cursor()

            base_query = '''
            SELECT g.id, r.name, s.name, t.name, ts.day, ts.slot
            FROM group_schedule gs
            JOIN groups g ON gs.group_id = g.id
            JOIN rooms r ON gs.room_id = r.id
            JOIN timeslots ts ON gs.timeslot_id = ts.id
            JOIN subjects s ON g.subject_id = s.id
            JOIN teachers t ON g.teacher_id = t.id
            '''

            filter_type = self.view_type_var.get()
            filter_value = self.view_value_var.get()

            params = ()
            if filter_type == "Group" and filter_value:
                base_query += " WHERE g.id = ?"
                params = (int(filter_value),)
            elif filter_type == "Teacher" and filter_value:
                base_query += " WHERE t.name = ?"
                params = (filter_value,)
            elif filter_type == "Room" and filter_value:
                base_query += " WHERE r.name = ?"
                params = (filter_value,)

            schedule_grid = defaultdict(lambda: defaultdict(list))

            for group_id, room, subject, teacher, day, slot in cursor.execute(base_query, params):
                text = f"Group {group_id} ({subject})\n{teacher} @ {room}"
                schedule_grid[day][slot].append(text)

            conn.close()

            for slot_index in range(6):
                values = []
                for day in range(5):
                    entries = schedule_grid[day][slot_index]
                    values.append("\n\n".join(entries) if entries else "")
                self.tree.insert("", "end", iid=slot_index, values=values)

        except Exception as e:
            messagebox.showerror("Error loading schedule", str(e))

    def update_filter_options(self, event=None):
        if not self.db_path:
            return

        conn = self.connect()
        cursor = conn.cursor()
        option_type = self.view_type_var.get()

        if option_type == "Group":
            cursor.execute("SELECT id FROM groups")
            options = [str(row[0]) for row in cursor.fetchall()]
        elif option_type == "Teacher":
            cursor.execute("SELECT name FROM teachers")
            options = [row[0] for row in cursor.fetchall()]
        elif option_type == "Room":
            cursor.execute("SELECT name FROM rooms")
            options = [row[0] for row in cursor.fetchall()]
        else:
            options = []

        self.value_selector["values"] = options
        if options:
            self.value_selector.current(0)
        else:
            self.view_value_var.set("")

        conn.close()

    def solve_schedule(self):
        if not self.db_path:
            return

        def run_solver_with_popup():
            loading = tk.Toplevel(self.root)
            loading.title("Solving...")
            tk.Label(loading, text="Solving schedule, please wait...").pack(padx=20, pady=20)
            loading.geometry("300x100")
            loading.transient(self.root)
            loading.grab_set()
            loading.update()

            try:
                base_dir = os.path.dirname(os.path.abspath(__file__))
                solver_path = os.path.join(base_dir, "solver.py")

                if not os.path.isfile(solver_path):
                    raise FileNotFoundError(f"solver.py not found at {solver_path}")

                spec = importlib.util.spec_from_file_location("solver", solver_path)
                solver = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(solver)

                result = solver.run_solver(self.db_path)
                messagebox.showinfo("Solver", result)
                self.load_schedule()

            except Exception as e:
                messagebox.showerror("Solver Error", str(e))
            finally:
                loading.destroy()

        threading.Thread(target=run_solver_with_popup).start()

    def launch_editor(self):
        try:
            editor_path = os.path.join(os.path.dirname(__file__), "DatabaseEditor.py")
            if not os.path.exists(editor_path):
                messagebox.showerror("Missing File", "DatabaseEditor.py not found.")
                return
            subprocess.Popen([sys.executable, editor_path])
        except Exception as e:
            messagebox.showerror("Launch Error", str(e))

    def on_drag_start(self, event):
        if self.view_type_var.get() == "Full Schedule":
            return  # Disable drag in Full Schedule

        region = self.tree.identify("region", event.x, event.y)
        if region != "cell":
            return

        row_id = self.tree.identify_row(event.y)
        col_id = self.tree.identify_column(event.x)
        if row_id and col_id:
            self.drag_source = (int(row_id), int(col_id[1:]) - 1)

    def on_drag_release(self, event):
        if not self.drag_source or self.view_type_var.get() == "Full Schedule":
            return

        region = self.tree.identify("region", event.x, event.y)
        if region != "cell":
            return

        target_row = self.tree.identify_row(event.y)
        target_col = self.tree.identify_column(event.x)
        if not target_row or not target_col:
            return

        source_slot, source_day = self.drag_source
        target_slot = int(target_row)
        target_day = int(target_col[1:]) - 1

        if (source_slot, source_day) == (target_slot, target_day):
            return  # No movement

        self.swap_slots(source_day, source_slot, target_day, target_slot)
        self.drag_source = None
    
    def swap_slots(self, day1, slot1, day2, slot2):
        try:
            conn = self.connect()
            cur = conn.cursor()

            # Get timeslot IDs
            cur.execute("SELECT id FROM timeslots WHERE day = ? AND slot = ?", (day1, slot1))
            ts1 = cur.fetchone()
            cur.execute("SELECT id FROM timeslots WHERE day = ? AND slot = ?", (day2, slot2))
            ts2 = cur.fetchone()
            if not ts1 or not ts2:
                messagebox.showerror("Error", "Time slot not found.")
                return

            ts1_id, ts2_id = ts1[0], ts2[0]

            filter_type = self.view_type_var.get()
            filter_value = self.view_value_var.get()

            base_query = '''
            SELECT gs.id, gs.group_id, gs.timeslot_id
            FROM group_schedule gs
            JOIN groups g ON gs.group_id = g.id
            JOIN rooms r ON gs.room_id = r.id
            JOIN timeslots ts ON gs.timeslot_id = ts.id
            JOIN subjects s ON g.subject_id = s.id
            JOIN teachers t ON g.teacher_id = t.id
            '''

            params = ()
            if filter_type == "Group":
                base_query += " WHERE g.id = ?"
                params = (int(filter_value),)
            elif filter_type == "Teacher":
                base_query += " WHERE t.name = ?"
                params = (filter_value,)
            elif filter_type == "Room":
                base_query += " WHERE r.name = ?"
                params = (filter_value,)

            cur.execute(base_query, params)
            entries = cur.fetchall()

            group_by_timeslot = {ts: (gs_id, group_id) for gs_id, group_id, ts in entries}

            gs1 = group_by_timeslot.get(ts1_id)
            gs2 = group_by_timeslot.get(ts2_id)

            if gs1:
                cur.execute("UPDATE group_schedule SET timeslot_id = ? WHERE id = ?", (ts2_id, gs1[0]))
            if gs2:
                cur.execute("UPDATE group_schedule SET timeslot_id = ? WHERE id = ?", (ts1_id, gs2[0]))

            conn.commit()
            conn.close()
            self.load_schedule()
        except Exception as e:
            messagebox.showerror("Swap Error", str(e))

if __name__ == "__main__":
    root = tk.Tk()
    app = ScheduleApp(root)
    root.mainloop()

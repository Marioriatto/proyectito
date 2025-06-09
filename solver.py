import sqlite3
from collections import defaultdict
import copy

def run_solver(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Load data
    cursor.execute("SELECT id, subject_id, teacher_id, student_count FROM groups")
    groups = cursor.fetchall()

    cursor.execute("SELECT id, name, type, capacity FROM rooms")
    rooms = cursor.fetchall()

    cursor.execute("SELECT id, day, slot FROM timeslots")
    timeslots = cursor.fetchall()

    cursor.execute("SELECT id, requires_lab FROM subjects")
    subject_lab_map = {row[0]: row[1] for row in cursor.fetchall()}
    conn.close()

    group_data = {
        g[0]: {
            "subject_id": g[1],
            "teacher_id": g[2],
            "student_count": g[3],
            "requires_lab": subject_lab_map.get(g[1], 0)
        }
        for g in groups
    }

    room_data = {
        r[0]: {
            "name": r[1],
            "type": r[2].strip().lower(),
            "capacity": r[3]
        }
        for r in rooms
    }

    # Sort time slots by (day, slot) for chronological priority
    timeslot_ordered = sorted(timeslots, key=lambda x: (x[1], x[2]))
    timeslot_ids = [t[0] for t in timeslot_ordered]

    teacher_to_groups = defaultdict(set)
    for gid, g in group_data.items():
        teacher_to_groups[g["teacher_id"]].add(gid)

    # Build domains
    domains = {}
    empty_domain_report = []
    for group_id, g in group_data.items():
        domain = []
        for room_id, room in room_data.items():
            if g["student_count"] > room["capacity"]:
                continue
            if g["requires_lab"] and room["type"] != "lab":
                continue
            for ts in timeslot_ordered:
                timeslot_id = ts[0]
                domain.append((room_id, timeslot_id))
        if not domain:
            reasons = []
            for room_id, room in room_data.items():
                if g["student_count"] > room["capacity"]:
                    reasons.append(f"Room {room['name']} too small")
                elif g["requires_lab"] and room["type"] != "lab":
                    reasons.append(f"Room {room['name']} not lab")
            empty_domain_report.append(f"Group {group_id} has no valid domain:\n  " + "\n  ".join(set(reasons)))
        domains[group_id] = domain

    if empty_domain_report:
        return "No feasible schedule found. Domain too narrow:\n\n" + "\n\n".join(empty_domain_report)

    assignment = {}
    conflict_log = []

    def is_valid(group_id, room_id, timeslot_id, partial_assignment):
        teacher_id = group_data[group_id]["teacher_id"]
        for other_gid, (r_id, t_id) in partial_assignment.items():
            if t_id == timeslot_id:
                if r_id == room_id:
                    return False
                if group_data[other_gid]["teacher_id"] == teacher_id:
                    return False
        return True

    def forward_check(domains, group_id, value, assignment):
        room_id, timeslot_id = value
        pruned = {}

        for other_gid in domains:
            if other_gid in assignment or other_gid == group_id:
                continue
            new_domain = []
            for v in domains[other_gid]:
                if v[1] == timeslot_id:
                    same_teacher = group_data[other_gid]["teacher_id"] == group_data[group_id]["teacher_id"]
                    same_room = v[0] == room_id
                    if same_teacher or same_room:
                        continue
                new_domain.append(v)
            if not new_domain:
                return None  # Dead end
            pruned[other_gid] = domains[other_gid]
            domains[other_gid] = new_domain
        return pruned

    def restore_domains(domains, pruned):
        for gid in pruned:
            domains[gid] = pruned[gid]

    def select_unassigned_group(domains, assignment):
        # MRV + Degree Heuristic
        unassigned = [g for g in domains if g not in assignment]
        mrv = sorted(unassigned, key=lambda g: (len(domains[g]), -len(teacher_to_groups[group_data[g]["teacher_id"]])))
        return mrv[0] if mrv else None

    def order_domain_values(group_id, domains, assignment):
        # LCV + Early time slot priority
        value_counts = []
        for value in domains[group_id]:
            room_id, timeslot_id = value
            conflicts = 0
            for other_gid in domains:
                if other_gid == group_id or other_gid in assignment:
                    continue
                for v in domains[other_gid]:
                    if v[1] == timeslot_id:
                        if v[0] == room_id or group_data[other_gid]["teacher_id"] == group_data[group_id]["teacher_id"]:
                            conflicts += 1
            value_counts.append((conflicts, value))

        # Sort first by least conflicts, then by timeslot order (earlier first)
        return [v for _, v in sorted(value_counts, key=lambda x: (x[0], timeslot_ids.index(x[1][1])))]

    def backtrack():
        if len(assignment) == len(domains):
            return True
        group_id = select_unassigned_group(domains, assignment)
        if group_id is None:
            return False
        for value in order_domain_values(group_id, domains, assignment):
            if is_valid(group_id, *value, assignment):
                assignment[group_id] = value
                pruned = forward_check(domains, group_id, value, assignment)
                if pruned is not None:
                    if backtrack():
                        return True
                    restore_domains(domains, pruned)
                del assignment[group_id]
        return False

    success = backtrack()

    if success:
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM group_schedule")
            for group_id, (room_id, timeslot_id) in assignment.items():
                cursor.execute(
                    "INSERT INTO group_schedule (group_id, room_id, timeslot_id) VALUES (?, ?, ?)",
                    (group_id, room_id, timeslot_id)
                )
            conn.commit()
            conn.close()
            return "Schedule successfully generated using backtracking + heuristics (earliest times prioritized)."
        except Exception as e:
            return f"Failed to save schedule: {e}"
    else:
        return "No feasible schedule found. Conflicts encountered during search:\n" + "\n".join(conflict_log[:10])

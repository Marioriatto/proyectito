import sqlite3

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

    # Prepare structures
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

    timeslot_ids = [t[0] for t in timeslots]

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
            for timeslot_id in timeslot_ids:
                domain.append((room_id, timeslot_id))

        if not domain:
            reasons = []
            for room_id, room in room_data.items():
                if g["student_count"] > room["capacity"]:
                    reasons.append(f"Room {room['name']} too small ({room['capacity']} < {g['student_count']})")
                elif g["requires_lab"] and room["type"] != "lab":
                    reasons.append(f"Room {room['name']} not lab")
            empty_domain_report.append(f"Group {group_id} has no valid assignment:\n  " + "\n  ".join(set(reasons)))
        domains[group_id] = domain

    if empty_domain_report:
        return "No feasible schedule found. Domain too narrow for some groups:\n\n" + "\n\n".join(empty_domain_report)

    assignment = {}
    conflict_log = []

    def is_valid(group_id, room_id, timeslot_id):
        teacher_id = group_data[group_id]["teacher_id"]
        for other_gid, (r_id, t_id) in assignment.items():
            if t_id == timeslot_id:
                if r_id == room_id:
                    conflict_log.append(
                        f"Room conflict at timeslot {t_id}: Room {room_id} is assigned to both group {group_id} and group {other_gid}"
                    )
                    return False
                if group_data[other_gid]["teacher_id"] == teacher_id:
                    conflict_log.append(
                        f"Teacher conflict at timeslot {t_id}: Teacher {teacher_id} is assigned to both group {group_id} and group {other_gid}"
                    )
                    return False
        return True

    def backtrack(index=0):
        if index == len(groups):
            return True
        group_id = groups[index][0]
        for room_id, timeslot_id in domains[group_id]:
            if is_valid(group_id, room_id, timeslot_id):
                assignment[group_id] = (room_id, timeslot_id)
                if backtrack(index + 1):
                    return True
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
            return "Schedule successfully generated using backtracking."
        except Exception as e:
            return f"Failed to save schedule: {e}"
    else:
        return "No feasible schedule found. Conflicts encountered during search:\n" + "\n".join(conflict_log[:10])

import sqlite3
from collections import defaultdict
import copy

def run_solver(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("SELECT id, subject_id, teacher_id, student_count, frecuency_count FROM groups")
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
            "frecuency_count": g[4],
            "requires_lab": subject_lab_map.get(g[1], 0)
        } for g in groups
    }

    room_data = {
        r[0]: {
            "name": r[1],
            "type": r[2].strip().lower(),
            "capacity": r[3]
        } for r in rooms
    }

    timeslot_ordered = sorted(timeslots, key=lambda x: (x[2], x[1]))
    timeslot_ids = [t[0] for t in timeslot_ordered]

    teacher_to_groups = defaultdict(set)
    for gid, g in group_data.items():
        teacher_to_groups[g["teacher_id"]].add(gid)

    original_frecuencies = {gid: data["frecuency_count"] for gid, data in group_data.items()}
    current_frecuencies = copy.deepcopy(original_frecuencies)
    best_solution_found = None

    while True:
        print(f"\nAttempting to solve with target frequencies: {current_frecuencies}")
        csp_variables = [(group_id, i) for group_id, freq in current_frecuencies.items() for i in range(freq)]
        if not csp_variables:
            if best_solution_found:
                print("All frequencies reduced to zero, but a solution was found at a higher frequency. Proceeding to save it.")
                break
            else:
                return "No feasible schedule can be found, even after reducing all group frequencies to zero."

        domains = {}
        empty_domain_report_this_iter = []
        for var_tuple in csp_variables:
            original_group_id, _ = var_tuple
            g = group_data[original_group_id]
            domain = []
            for room_id, room in room_data.items():
                if g["student_count"] > room["capacity"]:
                    continue
                if g["requires_lab"] and room["type"] != "lab":
                    continue
                for ts in timeslot_ordered:
                    domain.append((room_id, ts[0]))
            if not domain:
                empty_domain_report_this_iter.append(f"Variable {var_tuple} has an empty initial domain.")
            domains[var_tuple] = domain

        if empty_domain_report_this_iter:
            print("WARNING: Some variables have empty initial domains based on room/lab constraints.")

        assignment = {}

        def is_valid(group_var, room_id, timeslot_id, partial_assignment):
            original_group_id, _ = group_var
            teacher_id = group_data[original_group_id]["teacher_id"]
            assigned_ts = {
                t_id for (g_id, _), (_, t_id) in partial_assignment.items()
                if g_id == original_group_id
            }
            for (other_gid, _), (r_id, t_id) in partial_assignment.items():
                if t_id == timeslot_id and r_id == room_id:
                    return False
                if group_data[other_gid]["teacher_id"] == teacher_id and t_id == timeslot_id:
                    return False
                if other_gid == original_group_id and t_id == timeslot_id:
                    return False
            return timeslot_id not in assigned_ts

        def forward_check(domains, var, value, assignment):
            room_id, timeslot_id = value
            pruned = {}
            temp_domains = copy.deepcopy(domains)
            for other_var in temp_domains:
                if other_var in assignment or other_var == var:
                    continue
                other_gid, _ = other_var
                new_domain = []
                for val in temp_domains[other_var]:
                    if val[0] == room_id and val[1] == timeslot_id:
                        continue
                    if group_data[other_gid]["teacher_id"] == group_data[var[0]]["teacher_id"] and val[1] == timeslot_id:
                        continue
                    if other_gid == var[0] and val[1] == timeslot_id:
                        continue
                    new_domain.append(val)
                if not new_domain:
                    return None
                if new_domain != temp_domains[other_var]:
                    pruned[other_var] = temp_domains[other_var]
                    temp_domains[other_var] = new_domain
            for k in pruned:
                domains[k] = temp_domains[k]
            return pruned

        def restore_domains(domains, pruned):
            for k in pruned:
                domains[k] = pruned[k]

        def select_unassigned_group(domains, assignment):
            unassigned = [v for v in csp_variables if v not in assignment]
            if not unassigned:
                return None
            return sorted(unassigned, key=lambda var: (len(domains[var]), -len(teacher_to_groups[group_data[var[0]]["teacher_id"]]))) [0]

        def order_domain_values(var, domains, assignment):
            gid, _ = var
            teacher_id = group_data[gid]["teacher_id"]
            value_conflicts = []
            for val in domains[var]:
                room_id, timeslot_id = val
                conflicts = sum(
                    1 for other_var in domains
                    if other_var != var and other_var not in assignment and any(
                        (v[0] == room_id and v[1] == timeslot_id) or
                        (group_data[other_var[0]]["teacher_id"] == teacher_id and v[1] == timeslot_id) or
                        (other_var[0] == gid and v[1] == timeslot_id)
                        for v in domains[other_var]
                    )
                )
                value_conflicts.append((conflicts, val))
            return [v for _, v in sorted(value_conflicts, key=lambda x: (x[0], timeslot_ids.index(x[1][1])))]

        def backtrack():
            if len(assignment) == len(csp_variables):
                return True
            var = select_unassigned_group(domains, assignment)
            if var is None:
                return False
            for value in order_domain_values(var, domains, assignment):
                if is_valid(var, *value, assignment):
                    assignment[var] = value
                    pruned = forward_check(domains, var, value, assignment)
                    if pruned is not None:
                        if backtrack():
                            return True
                        restore_domains(domains, pruned)
                    del assignment[var]
            return False

        if backtrack():
            best_solution_found = copy.deepcopy(assignment)
            print(f"Successfully found a schedule with target frequencies: {current_frecuencies}")
            break
        else:
            print(f"No solution found. Reducing a group's frequency.")
            reducible = [(groupId, frequency) for groupId, frequency in current_frecuencies.items() if frequency > 0]
            if not reducible:
                break
            group_to_reduce = max(reducible, key=lambda x: x[1])[0]
            current_frecuencies[group_to_reduce] -= 1
            print(f"Reduced frequency for Group {group_to_reduce} to {current_frecuencies[group_to_reduce]}.")

    if best_solution_found:
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM group_schedule")
            for (gid, _), (room_id, timeslot_id) in best_solution_found.items():
                cursor.execute("INSERT INTO group_schedule (group_id, room_id, timeslot_id) VALUES (?, ?, ?)", (gid, room_id, timeslot_id))
            conn.commit()
            conn.close()

            final_report = defaultdict(int)
            for (gid, _), _ in best_solution_found.items():
                final_report[gid] += 1

            report_lines = []
            for gid in sorted(original_frecuencies):
                original = original_frecuencies[gid]
                assigned = final_report[gid]
                if assigned == original:
                    report_lines.append(f"  Group {gid}: Assigned {assigned} (Target: {original}) - ✓")
                elif assigned > 0:
                    report_lines.append(f"  Group {gid}: Assigned {assigned} (Reduced from {original})")
                else:
                    report_lines.append(f"  Group {gid}: Assigned 0 (Target: {original}) - ✗")

            return "Schedule generated successfully:\n" + "\n".join(report_lines)

        except Exception as e:
            return f"Failed to save schedule: {e}"

    return "No feasible schedule found after all attempts."

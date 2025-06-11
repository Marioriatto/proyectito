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

    # x[0] : id, x[1] : day, x[2] : slot
    # order by slot and then by day to fill up row by row
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



        csp_variables = []
        for group_id, freq in current_frecuencies.items():
            for i in range(freq):
                csp_variables.append((group_id, i))



        if not csp_variables:
            if best_solution_found:
                print("INFO: All frequencies reduced to zero, but a solution was found at a higher frequency. Proceeding to save it.")
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
                    timeslot_id = ts[0]
                    domain.append((room_id, timeslot_id))
            
            if not domain:


                empty_domain_report_this_iter.append(f"Variable {var_tuple} has an empty initial domain. This instance cannot be assigned.")
            domains[var_tuple] = domain




        if empty_domain_report_this_iter:
            print("WARNING: Some variables have empty initial domains based on room/lab constraints. This attempt will likely fail.")




        assignment = {}



        def is_valid(group_var, room_id, timeslot_id, partial_assignment):
            original_group_id, instance_num = group_var
            teacher_id = group_data[original_group_id]["teacher_id"]


            assigned_timeslots_for_this_original_group = set()

            for other_group_var, (other_r_id, other_t_id) in partial_assignment.items():
                other_original_group_id, other_instance_num = other_group_var


                if other_t_id == timeslot_id and other_r_id == room_id:
                    return False



                if group_data[other_original_group_id]["teacher_id"] == teacher_id and other_t_id == timeslot_id:
                    return False



                if other_original_group_id == original_group_id:
                    assigned_timeslots_for_this_original_group.add(other_t_id)


            if timeslot_id in assigned_timeslots_for_this_original_group:
                return False

            return True

        def forward_check(current_domains, current_group_var, value, current_assignment):
            room_id, timeslot_id = value
            pruned = {}
            original_current_group_id, _ = current_group_var



            temp_domains = copy.deepcopy(current_domains) 

            for other_var in temp_domains:
                if other_var in current_assignment or other_var == current_group_var:
                    continue
                
                original_other_group_id, _ = other_var

                new_domain_for_other_var = []
                for v in temp_domains[other_var]:

                    

                    if v[0] == room_id and v[1] == timeslot_id:
                        continue 


                    if group_data[original_other_group_id]["teacher_id"] == group_data[original_current_group_id]["teacher_id"] and v[1] == timeslot_id:
                        continue 
                    

                    if original_other_group_id == original_current_group_id and v[1] == timeslot_id:
                        continue
                    
                    new_domain_for_other_var.append(v)
                
                if not new_domain_for_other_var:
                    return None 
                
                if new_domain_for_other_var != temp_domains[other_var]:
                    pruned[other_var] = temp_domains[other_var]
                    temp_domains[other_var] = new_domain_for_other_var
            


            for var_to_prune, new_dom in temp_domains.items():
                 if var_to_prune in pruned: 
                     current_domains[var_to_prune] = new_dom
            return pruned

        def restore_domains(current_domains, pruned):
            for var in pruned:
                current_domains[var] = pruned[var]

        def select_unassigned_group(current_domains, current_assignment):

            unassigned_vars = [v for v in csp_variables if v not in current_assignment]
            if not unassigned_vars:
                return None
            



            mrv_degree_sorted = sorted(unassigned_vars, 
                                     key=lambda var: (len(current_domains[var]), 
                                                      -len(teacher_to_groups[group_data[var[0]]["teacher_id"]])))
            return mrv_degree_sorted[0]

        def order_domain_values(group_var, current_domains, current_assignment):
            original_group_id, instance_num = group_var
            teacher_id = group_data[original_group_id]["teacher_id"]
            
            value_counts = []
            for value in current_domains[group_var]:
                room_id, timeslot_id = value
                conflicts = 0


                for other_var_in_domains in current_domains:
                    if other_var_in_domains == group_var or other_var_in_domains in current_assignment:
                        continue 
                    
                    original_other_group_id, _ = other_var_in_domains

                    for other_val_in_domain in current_domains[other_var_in_domains]:

                        

                        if other_val_in_domain[0] == room_id and other_val_in_domain[1] == timeslot_id:
                            conflicts += 1
                            continue 


                        if group_data[original_other_group_id]["teacher_id"] == teacher_id and other_val_in_domain[1] == timeslot_id:
                            conflicts += 1
                            continue
                        

                        if original_other_group_id == original_group_id and other_val_in_domain[1] == timeslot_id:
                            conflicts += 1
                            continue

                value_counts.append((conflicts, value))



            return [v for _, v in sorted(value_counts, key=lambda x: (x[0], timeslot_ids.index(x[1][1])))]


        def backtrack():

            if len(assignment) == len(csp_variables):
                return True
            

            var_to_assign = select_unassigned_group(domains, assignment)
            if var_to_assign is None:
                return False 


            for value in order_domain_values(var_to_assign, domains, assignment):

                if is_valid(var_to_assign, *value, assignment):

                    assignment[var_to_assign] = value
                    

                    pruned = forward_check(domains, var_to_assign, value, assignment)
                    
                    if pruned is not None: 
                        if backtrack(): 
                            return True 
                        

                        restore_domains(domains, pruned)
                    

                    del assignment[var_to_assign]
            
            return False 



        success = backtrack()

        if success:

            best_solution_found = copy.deepcopy(assignment)
            print(f"INFO: Successfully found a schedule with target frequencies: {current_frecuencies}")
            break

        else:

            print(f"INFO: No solution found with current frequencies. Attempting to reduce a group's frequency.")

            group_to_reduce = None
            max_freq_to_reduce = -1 




            for gid, freq in current_frecuencies.items():
                if freq > 0 and freq > max_freq_to_reduce:
                    group_to_reduce = gid
                    max_freq_to_reduce = freq
            
            if group_to_reduce is None:



                break # Exit the outer loop, no solution possible.


            current_frecuencies[group_to_reduce] = max(0, current_frecuencies[group_to_reduce] - 1)
            print(f"INFO: Reduced target frequency for Group {group_to_reduce} to {current_frecuencies[group_to_reduce]}. Retrying...")


    if best_solution_found:
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM group_schedule") # Clear any previous schedule




            for (original_group_id, instance_num), (room_id, timeslot_id) in best_solution_found.items():
                cursor.execute(
                    "INSERT INTO group_schedule (group_id, room_id, timeslot_id) VALUES (?, ?, ?)",
                    (original_group_id, room_id, timeslot_id)
                )
            conn.commit()
            conn.close()


            final_frequency_report = defaultdict(int)
            for (group_id, _), _ in best_solution_found.items():
                final_frequency_report[group_id] += 1
            
            report_lines = []

            for gid in sorted(original_frecuencies.keys()):
                original_freq = original_frecuencies[gid]
                assigned_freq = final_frequency_report[gid] # Gets 0 if group not assigned at all

                if assigned_freq == original_freq:
                    report_lines.append(f"  Group {gid}: Assigned {assigned_freq} times (Original Target: {original_freq}) - Achieved!")
                elif assigned_freq > 0:
                    report_lines.append(f"  Group {gid}: Assigned {assigned_freq} times (Reduced from Original Target: {original_freq})")
                else: # assigned_freq is 0
                     report_lines.append(f"  Group {gid}: Assigned 0 times (Original Target: {original_freq}) - Could not be scheduled.")

            return "Schedule successfully generated with the following group frequencies:\n" + "\n".join(report_lines)

        except Exception as e:
            return f"Failed to save schedule: {e}"
    else:

        return "No feasible schedule found after exhausting all frequency reduction attempts. Consider reviewing initial constraints (rooms, timeslots, capacities)."
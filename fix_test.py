import re

with open("test_system.py", "r") as f:
    content = f.read()

# Remove the broken old_eval logic in test_complete_proof_temporal_negative_controls
content = re.sub(
    r"    old_eval = engine\.evaluation_time\n    engine\.evaluation_time = datetime\(2026, 8, 15, 0, 0, 0\)\n",
    "",
    content
)
content = re.sub(
    r"    engine\.evaluation_time = old_eval\n",
    "",
    content
)

# Fix g_a.get_subgraph_for_order("nc1", as_of_time=datetime(2026, 8, 15, 12, 0, 0)) -> g_a.get_subgraph_for_order("nc1")
content = re.sub(
    r"\.get_subgraph_for_order\(([^,]+), as_of_time=datetime\(2026, 8, 15, 12, 0, 0\)\)",
    r".get_subgraph_for_order(\1)",
    content
)

# Ensure every engine.reconcile_order without as_of_time gets one
# But we already did a greedy replacement that put it in get_subgraph_for_order!
# Since we just fixed get_subgraph_for_order, let's now add it to reconcile_order correctly.
def replacer(match):
    full = match.group(0)
    if "as_of_time=" in full: return full
    # Add as_of_time to the end of reconcile_order args
    return full[:-1] + ", as_of_time=datetime(2026, 8, 15, 12, 0, 0))"

content = re.sub(
    r"engine\.reconcile_order\([^)]+\)",
    replacer,
    content
)

with open("test_system.py", "w") as f:
    f.write(content)

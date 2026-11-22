# Check imports demo version
import sys
import os

mods = [
    "hdfs_utils",
    "tools_utils",
    "vm1_mcp_logger_client",
    "vm1_local_worker",
    "mcp_registry",
    "multi_tool_handler",
    "utils",
    "gc_call_oaitsh",
    "tools.math_tools",
    "tools.time_tool",
]

print("=" * 60)
print("Checking module imports in AI-skillhub")
print("=" * 60)
print()

ok = True
for m in mods:
    try:
        __import__(m)
        print(f"  OK: {m}")
    except Exception as e:
        print(f"  FAIL: {m} - {e}")
        ok = False

print()
if ok:
    print("All modules imported successfully!")
else:
    print("Some modules failed to import.")
    sys.exit(1)
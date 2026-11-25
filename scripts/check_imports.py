# Check imports demo version
import sys


mods = [
    "audit_helper.cli_skillhub_v02",
    "audit_helper.hdfs_utils",
    "audit_helper.tools_utils",
    "audit_helper.vm1_mcp_logger_client",
    "audit_helper.vm1_local_worker",
    "audit_helper.mcp_registry",
    "audit_helper.multi_tool_handler",
    "audit_helper.utils",
    "audit_helper.gc_call_oaitsh",
    "audit_helper.tools.math_tools",
    "audit_helper.tools.time_tool",
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
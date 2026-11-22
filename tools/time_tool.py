"""time_tool"""
import datetime
from mcp_registry import mcp


@mcp.tool(name="cur_datetime", host="vm1", type="python_fn", description="Показывает текущую дату и время")
def cur_datetime() -> str:
    """Показывает текущее время по мск"""

    offset = datetime.timezone(datetime.timedelta(hours=3))
    r = str(datetime.datetime.now(offset)).split('.')[0]
    return r
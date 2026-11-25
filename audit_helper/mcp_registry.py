"""mcp_registry"""
import json
import socket
from functools import wraps
from audit_helper.hdfs_utils import hdfs_read, hdfs_write, hdfs_exists
import os

HDFS_FOLDER = f"hdfs://arnsdpsbx/user/{os.environ.get('NB_USER', 'demo_user')}/notebooks/skillhub_proxy_folder"
TOOLS_PATH = f"{HDFS_FOLDER}/tools_config.json"


class MCPRegistry:
    """MCPRegistry"""
    def __init__(self, tools_path=TOOLS_PATH):
        self.tools_path = tools_path

    def _load(self):
        if hdfs_exists(self.tools_path):
            try:
                return json.loads(hdfs_read(self.tools_path))
            except Exception:
                return {"tools": {}}
        else:
            return {"tools": {}}

    def _save(self, data):
        hdfs_write(self.tools_path, json.dumps(data, ensure_ascii=False, indent=2))

    def register(self, metadata: dict):
        data = self._load()
        tools = data.get("tools", {})
        tools[metadata["name"]] = metadata
        data["tools"] = tools
        self._save(data)
        return metadata

    def tool(self, name=None, host=None, type="python_fn", command=None, args=None, entrypoint=None, description=""):
        """
        декоратор для регистрации функции в качестве тула
        Usage:
          @mcp.tool(name='add', host='vm1', type='python_fn')
          def add(a,b): ...
        """
        def decorator(fn):
            tool_name = name or fn.__name__
            meta = {
                "name": tool_name,
                "host": host or socket.gethostname(),
                "type": type,
                "command": command,
                "args": args or [],
                "entrypoint": entrypoint or f"{fn.__module__}:{fn.__name__}",
                "description": description or (fn.__doc__ or ""),
            }
            self.register(meta)

            @wraps(fn)
            def wrapper(*a, **kw):
                return fn(*a, **kw)
            return wrapper
        return decorator


# singleton
mcp = MCPRegistry()
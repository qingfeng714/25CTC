"""
简化的审计日志服务
"""
import json
from datetime import datetime
from typing import Dict, Any

class AuditLogger:
    """简化的审计日志记录器"""
    
    def __init__(self):
        self.logs = []
    
    def log(self, session_id: str, action: str, user: str, details: Dict[str, Any] = None):
        """记录审计日志"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "session_id": session_id,
            "action": action,
            "user": user,
            "details": details or {}
        }
        self.logs.append(log_entry)
        print(f"[AUDIT] {session_id} - {action} by {user}")
    
    def get_logs(self, session_id: str = None) -> list:
        """获取审计日志"""
        if session_id:
            return [log for log in self.logs if log["session_id"] == session_id]
        return self.logs
import traceback
import sys
from pathlib import Path
# ensure repo root is on sys.path
repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root))
from services.crossmodal_service import CrossModalAttentionService

svc = CrossModalAttentionService(device='cpu')
try:
    res = svc.process_files_folder(
        csv_path=r'd:\\QF\\25密码技术竞赛\\2025-Cryptography-Knowledge-Contest-Repository\\database\\cxr-record-list.csv',
        files_root=r'd:\\QF\\25密码技术竞赛\\2025-Cryptography-Knowledge-Contest-Repository\\database\\files',
        output_path=r'd:\\QF\\25密码技术竞赛\\2025-Cryptography-Knowledge-Contest-Repository\\output\\pipeline\\files_run_local'
    )
    import json
    print(json.dumps(res, ensure_ascii=False, indent=2))
except Exception:
    traceback.print_exc()

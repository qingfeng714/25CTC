import requests
import json

url = 'http://127.0.0.1:5000/api/process_files'
body = {
    'csv_path': r'd:\\QF\\25密码技术竞赛\\2025-Cryptography-Knowledge-Contest-Repository\\database\\cxr-record-list.csv',
    'files_root': r'd:\\QF\\25密码技术竞赛\\2025-Cryptography-Knowledge-Contest-Repository\\database\\files',
    'output_prefix': r'd:\\QF\\25密码技术竞赛\\2025-Cryptography-Knowledge-Contest-Repository\\output\\pipeline\\files_run_1'
}

print('POST', url)
try:
    r = requests.post(url, json=body, timeout=60)
    print('STATUS', r.status_code)
    try:
        print(json.dumps(r.json(), ensure_ascii=False, indent=2))
    except Exception:
        print(r.text)
except Exception as e:
    print('ERROR', e)

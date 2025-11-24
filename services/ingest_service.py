import os
import uuid
from datetime import datetime

def parseDICOM(dicom_file):
    """模拟DICOM文件解析"""
    if not dicom_file:
        return None
    
    # 在实际应用中，这里应该解析DICOM文件
    # 这里我们只是模拟返回一个ID
    ingest_id = f"dicom_{uuid.uuid4().hex[:8]}"
    
    # 模拟保存文件
    upload_dir = os.path.join(os.path.dirname(__file__), '../uploads')
    os.makedirs(upload_dir, exist_ok=True)
    
    if dicom_file:
        filename = f"{ingest_id}.dcm"
        filepath = os.path.join(upload_dir, filename)
        dicom_file.save(filepath)
    
    return ingest_id
"""
调试脚本：检查存储数据库状态
"""
import sqlite3
from pathlib import Path

# 数据库路径
db_path = Path("storage_repo/db/index.sqlite")

if not db_path.exists():
    print(f"❌ 数据库不存在: {db_path}")
    exit(1)

print(f"✅ 数据库路径: {db_path}")
print("=" * 60)

# 连接数据库
conn = sqlite3.connect(str(db_path))
cur = conn.cursor()

# 检查objects表
print("\n【objects表】")
print("-" * 60)
cur.execute("SELECT COUNT(*) FROM objects")
count = cur.fetchone()[0]
print(f"总记录数: {count}")

if count > 0:
    print("\n最近5条记录:")
    cur.execute("""
        SELECT id, patient_id, batch_id, dicom_sha256, text_sha256, ts_ms
        FROM objects
        ORDER BY id DESC
        LIMIT 5
    """)
    for row in cur.fetchall():
        print(f"  ID: {row[0]}")
        print(f"  Patient ID: {row[1]}")
        print(f"  Batch ID: {row[2]}")
        print(f"  DICOM SHA256: {row[3][:16]}...")
        print(f"  Text SHA256: {row[4][:16]}...")
        print(f"  Timestamp: {row[5]}")
        print("-" * 40)

# 检查batches表
print("\n【batches表】")
print("-" * 60)
cur.execute("SELECT COUNT(*) FROM batches")
count = cur.fetchone()[0]
print(f"总记录数: {count}")

if count > 0:
    print("\n最近5条记录:")
    cur.execute("""
        SELECT id, count, audit_sha256, ts_ms
        FROM batches
        ORDER BY ts_ms DESC
        LIMIT 5
    """)
    for row in cur.fetchall():
        print(f"  Batch ID: {row[0]}")
        print(f"  Count: {row[1]}")
        print(f"  Audit SHA256: {row[2][:16] if row[2] else 'N/A'}...")
        print(f"  Timestamp: {row[3]}")
        print("-" * 40)

# 检查CAS存储
print("\n【CAS存储】")
print("-" * 60)
cas_dir = Path("storage_repo/cas")
if cas_dir.exists():
    dcm_files = list(cas_dir.rglob("*"))
    dcm_files = [f for f in dcm_files if f.is_file()]
    print(f"CAS文件总数: {len(dcm_files)}")
    if len(dcm_files) > 0:
        print(f"\n示例文件路径:")
        for f in dcm_files[:3]:
            print(f"  {f.relative_to(cas_dir.parent)}")
else:
    print("❌ CAS目录不存在")

# 检查batches目录
print("\n【批次目录】")
print("-" * 60)
batches_dir = Path("storage_repo/batches")
if batches_dir.exists():
    batch_dirs = [d for d in batches_dir.iterdir() if d.is_dir()]
    print(f"批次目录数量: {len(batch_dirs)}")
    if len(batch_dirs) > 0:
        print(f"\n最近的批次:")
        for d in sorted(batch_dirs, key=lambda x: x.stat().st_mtime, reverse=True)[:3]:
            print(f"  {d.name}")
            files = list(d.glob("*"))
            for f in files:
                print(f"    - {f.name}")
else:
    print("❌ 批次目录不存在")

# 检查protected文件
print("\n【保护文件】")
print("-" * 60)
output_dir = Path("output")
if output_dir.exists():
    batch_dirs = [d for d in output_dir.iterdir() if d.is_dir() and d.name.startswith("batch_")]
    print(f"输出批次数量: {len(batch_dirs)}")
    if len(batch_dirs) > 0:
        print(f"\n最近的批次:")
        for d in sorted(batch_dirs, key=lambda x: x.stat().st_mtime, reverse=True)[:3]:
            print(f"  {d.name}")
            
            # 检查protected_dicom
            protected_dicom = d / "protected_dicom"
            if protected_dicom.exists():
                dcm_files = list(protected_dicom.glob("*.dcm"))
                print(f"    protected_dicom: {len(dcm_files)} 个文件")
                for f in dcm_files[:3]:
                    print(f"      - {f.name}")
                    
                # 检查命名格式
                if len(dcm_files) > 0:
                    first_file = dcm_files[0].stem
                    if first_file.startswith("patient"):
                        print(f"      ✅ 使用patient_id命名（新格式）")
                    elif len(first_file) == 24:
                        print(f"      ❌ 使用哈希命名（旧格式）")
            
            # 检查protected_text
            protected_text = d / "protected_text"
            if protected_text.exists():
                json_files = [f for f in protected_text.glob("*.json") if f.name != "audit_manifest.json"]
                print(f"    protected_text: {len(json_files)} 个文件")
                for f in json_files[:3]:
                    print(f"      - {f.name}")
else:
    print("❌ 输出目录不存在")

conn.close()

print("\n" + "=" * 60)
print("检查完成")
print("\n提示：")
print("  - 如果objects表为0，说明文件名不匹配或入库失败")
print("  - 如果DICOM使用哈希命名，说明服务运行旧代码")
print("  - 应该重启服务：完全重启服务.bat")


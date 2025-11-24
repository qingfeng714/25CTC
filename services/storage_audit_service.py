"""
存储与审计服务
实现内容寻址存储(CAS)、SQLite索引、审计清单管理
"""
import sqlite3, json, time, hashlib, shutil, zipfile
from pathlib import Path
from typing import Optional, List, Dict
import pydicom

class StorageAuditService:
    """存储与审计服务"""
    
    def __init__(self, repo_path: str):
        """
        初始化存储服务
        :param repo_path: 仓库根目录
        """
        self.repo = Path(repo_path)
        self.repo.mkdir(parents=True, exist_ok=True)
        self.conn = self._init_db()
    
    def _init_db(self) -> sqlite3.Connection:
        """初始化SQLite数据库"""
        dbp = self.repo / "db" / "index.sqlite"
        dbp.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(dbp), check_same_thread=False)
        
        # 对象表
        conn.execute("""
        CREATE TABLE IF NOT EXISTS objects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sop_uid TEXT,
            patient_id TEXT,
            dicom_sha256 TEXT,
            text_sha256 TEXT,
            masked_pixels INTEGER,
            batch_id TEXT,
            ts_ms INTEGER,
            dicom_cas TEXT,
            text_cas TEXT
        )""")
        
        # 批次表
        conn.execute("""
        CREATE TABLE IF NOT EXISTS batches (
            id TEXT PRIMARY KEY,
            audit_sha256 TEXT,
            sig_sha256 TEXT,
            pk_sha256 TEXT,
            count INTEGER,
            ts_ms INTEGER
        )""")
        
        # 创建索引
        conn.execute("CREATE INDEX IF NOT EXISTS idx_sop ON objects(sop_uid)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_patient ON objects(patient_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_batch ON objects(batch_id)")
        
        conn.commit()
        return conn
    
    def _sha256_file(self, p: Path) -> str:
        """计算文件SHA256"""
        h = hashlib.sha256()
        with p.open("rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        return h.hexdigest()
    
    def _cas_path(self, digest: str) -> Path:
        """获取CAS路径"""
        return self.repo / "cas" / digest[:2] / digest[2:]
    
    def _cas_put(self, src: Path) -> str:
        """存入CAS"""
        digest = self._sha256_file(src)
        dst = self._cas_path(digest)
        dst.parent.mkdir(parents=True, exist_ok=True)
        if not dst.exists():
            shutil.copy2(src, dst)
        return digest
    
    def ingest_batch(self, protected_dicom: Path, protected_text: Path, batch_id: str) -> Dict:
        """
        批量入库
        :param protected_dicom: 保护后的DICOM目录
        :param protected_text: 保护后的文本目录
        :param batch_id: 批次ID
        :return: 入库结果
        """
        # 保存审计材料
        batch_dir = self.repo / "batches" / batch_id
        batch_dir.mkdir(parents=True, exist_ok=True)
        
        for name in ["audit_manifest.json", "audit_manifest.sig", "audit_manifest.pk"]:
            src = protected_text / name
            if src.exists():
                shutil.copy2(src, batch_dir / name)
        
        # 计算审计文件哈希
        audit_sha = sig_sha = pk_sha = None
        if (batch_dir / "audit_manifest.json").exists():
            audit_sha = self._sha256_file(batch_dir / "audit_manifest.json")
        if (batch_dir / "audit_manifest.sig").exists():
            sig_sha = self._sha256_file(batch_dir / "audit_manifest.sig")
        if (batch_dir / "audit_manifest.pk").exists():
            pk_sha = self._sha256_file(batch_dir / "audit_manifest.pk")
        
        # 读取审计清单获取count
        count = 0
        if (batch_dir / "audit_manifest.json").exists():
            try:
                audit_data = json.loads((batch_dir / "audit_manifest.json").read_text(encoding='utf-8'))
                count = audit_data.get("count", 0)
            except:
                pass
        
        # 插入批次记录
        self.conn.execute(
            "INSERT OR REPLACE INTO batches(id, audit_sha256, sig_sha256, pk_sha256, count, ts_ms) VALUES(?,?,?,?,?,?)",
            (batch_id, audit_sha, sig_sha, pk_sha, count, int(time.time() * 1000))
        )
        self.conn.commit()
        
        # 入库DICOM-文本对
        dicoms = {p.stem: p for p in protected_dicom.glob("*.dcm")}
        texts = {p.stem: p for p in protected_text.glob("*.json") if p.name != "audit_manifest.json"}
        stems = sorted(set(dicoms.keys()) & set(texts.keys()))
        
        ingested = 0
        for stem in stems:
            dcm = dicoms[stem]
            txt = texts[stem]
            
            # 提取SOP和Patient ID
            try:
                ds = pydicom.dcmread(str(dcm), stop_before_pixels=True, force=True)
                sop = str(getattr(ds, "SOPInstanceUID", "")) or ""
                patient_id = str(getattr(ds, "PatientID", "")) or stem
            except Exception:
                sop = ""
                patient_id = stem
            
            d_sha = self._sha256_file(dcm)
            t_sha = self._sha256_file(txt)
            d_cas = self._cas_put(dcm)
            t_cas = self._cas_put(txt)
            
            self.conn.execute("""
                INSERT INTO objects
                (sop_uid, patient_id, dicom_sha256, text_sha256, masked_pixels, batch_id, ts_ms, dicom_cas, text_cas)
                VALUES(?,?,?,?,?,?,?,?,?)
            """, (sop, patient_id, d_sha, t_sha, 0, batch_id, int(time.time() * 1000), d_cas, t_cas))
            ingested += 1
        
        self.conn.commit()
        
        return {
            "batch_id": batch_id,
            "ingested": ingested,
            "audit_sha256": audit_sha,
            "has_signature": sig_sha is not None
        }
    
    def list_objects(self, limit: int = 20, offset: int = 0) -> List[Dict]:
        """列出对象"""
        cur = self.conn.execute("""
            SELECT id, sop_uid, patient_id, dicom_sha256, text_sha256, batch_id, ts_ms 
            FROM objects 
            ORDER BY id DESC 
            LIMIT ? OFFSET ?
        """, (limit, offset))
        
        results = []
        for row in cur.fetchall():
            results.append({
                "id": row[0],
                "sop_uid": row[1],
                "patient_id": row[2],
                "dicom_sha256": row[3],
                "text_sha256": row[4],
                "batch_id": row[5],
                "timestamp": row[6]
            })
        return results
    
    def list_batches(self, limit: int = 20) -> List[Dict]:
        """列出批次"""
        cur = self.conn.execute("""
            SELECT id, audit_sha256, sig_sha256, count, ts_ms 
            FROM batches 
            ORDER BY ts_ms DESC 
            LIMIT ?
        """, (limit,))
        
        results = []
        for row in cur.fetchall():
            results.append({
                "batch_id": row[0],
                "audit_sha256": row[1],
                "has_signature": row[2] is not None,
                "count": row[3],
                "timestamp": row[4]
            })
        return results
    
    def get_object_by_patient_id(self, patient_id: str) -> Optional[Dict]:
        """根据Patient ID查找对象"""
        cur = self.conn.execute("""
            SELECT sop_uid, dicom_cas, text_cas, batch_id 
            FROM objects 
            WHERE patient_id = ? 
            ORDER BY id DESC 
            LIMIT 1
        """, (patient_id,))
        
        row = cur.fetchone()
        if not row:
            return None
        
        return {
            "sop_uid": row[0],
            "dicom_cas": row[1],
            "text_cas": row[2],
            "batch_id": row[3]
        }
    
    def build_bundle(self, patient_id: str, out_zip: Path) -> bool:
        """
        构建可验证的bundle
        :param patient_id: 患者ID
        :param out_zip: 输出ZIP路径
        :return: 是否成功
        """
        obj = self.get_object_by_patient_id(patient_id)
        if not obj:
            return False
        
        dcas = obj["dicom_cas"]
        tcas = obj["text_cas"]
        bid = obj["batch_id"]
        sop = obj["sop_uid"]
        
        batch_dir = self.repo / "batches" / bid
        
        out_zip.parent.mkdir(parents=True, exist_ok=True)
        
        with zipfile.ZipFile(out_zip, "w", compression=zipfile.ZIP_DEFLATED) as z:
            # DICOM
            dcm_path = self._cas_path(dcas)
            if dcm_path.exists():
                z.write(dcm_path, arcname=f"{patient_id}.dcm")
            
            # 文本bundle
            txt_path = self._cas_path(tcas)
            if txt_path.exists():
                z.write(txt_path, arcname=f"{patient_id}.json")
            
            # 审计材料
            if (batch_dir / "audit_manifest.json").exists():
                z.write(batch_dir / "audit_manifest.json", arcname="audit_manifest.json")
            if (batch_dir / "audit_manifest.sig").exists():
                z.write(batch_dir / "audit_manifest.sig", arcname="audit_manifest.sig")
            if (batch_dir / "audit_manifest.pk").exists():
                z.write(batch_dir / "audit_manifest.pk", arcname="audit_manifest.pk")
        
        return True
    
    def get_stats(self) -> Dict:
        """获取统计信息"""
        cur = self.conn.execute("SELECT COUNT(*) FROM objects")
        total_objects = cur.fetchone()[0]
        
        cur = self.conn.execute("SELECT COUNT(*) FROM batches")
        total_batches = cur.fetchone()[0]
        
        return {
            "total_objects": total_objects,
            "total_batches": total_batches,
            "repo_path": str(self.repo)
        }

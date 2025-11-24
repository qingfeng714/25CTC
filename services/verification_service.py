"""
验证服务
验证SPHINCS+签名、DICOM私有标签、密文完整性
"""
import json, zipfile
from pathlib import Path
from typing import Dict, List
import pydicom

try:
    import pyspx.shake256_128f as sphincs
    HAS_SPX = True
except Exception:
    HAS_SPX = False

class VerificationService:
    """验证服务"""
    
    @staticmethod
    def verify_signature(audit_bytes: bytes, sig: bytes, pk: bytes) -> bool:
        """验证SPHINCS+签名"""
        if not HAS_SPX:
            return False
        try:
            sphincs.verify(pk, audit_bytes, sig)
            return True
        except Exception:
            return False
    
    @staticmethod
    def load_private_payload(ds) -> Dict:
        """从DICOM加载私有保护载荷"""
        try:
            if ds.get((0x0011, 0x0010)) and ds.get((0x0011, 0x0010)).value == "PROTECT-META":
                if ds.get((0x0011, 0x1010)):
                    return json.loads(ds.get((0x0011, 0x1010)).value)
        except Exception:
            pass
        return {}
    
    @staticmethod
    def token_shape_ok(field: str, token: str) -> bool:
        """检查token格式是否合法"""
        if field in ("PatientID", "AccessionNumber", "InstitutionName"):
            return token and token.upper() == token and token.isalnum()
        if field == "StudyDate":
            return token and token.isdigit() and len(token) >= 6
        return True
    
    def verify_pair(self, dcm_path: Path, json_path: Path) -> Dict:
        """
        验证DICOM-JSON对
        :param dcm_path: DICOM文件路径
        :param json_path: JSON文件路径
        :return: 验证结果
        """
        issues = []
        
        # 验证DICOM
        try:
            ds = pydicom.dcmread(str(dcm_path), force=True)
        except Exception as e:
            return {"error": f"Cannot read DICOM: {e}"}
        
        priv = self.load_private_payload(ds)
        fields = priv.get("fields", [])
        if not fields:
            issues.append("missing private protection payload")
        
        # 检查header token
        hdr = {}
        for tag, name in [
            ((0x0010, 0x0020), "PatientID"),
            ((0x0008, 0x0050), "AccessionNumber"),
            ((0x0008, 0x0020), "StudyDate"),
            ((0x0008, 0x0080), "InstitutionName")
        ]:
            try:
                v = ds.get(tag).value if ds.get(tag) is not None else ""
            except Exception:
                v = ""
            hdr[name] = v
            if not self.token_shape_ok(name, v):
                issues.append(f"header token shape suspicious: {name}={v}")
        
        # 验证文本bundle
        try:
            tb = json.loads(json_path.read_text(encoding="utf-8"))
            cols = tb.get("columns_cipher", {})
            for col, rec in cols.items():
                for k in ("cipher_b64", "nonce", "ad"):
                    if k not in rec:
                        issues.append(f"column {col} missing {k}")
        except Exception as e:
            issues.append(f"text bundle parse error: {e}")
        
        return {
            "dicom": str(dcm_path),
            "text": str(json_path),
            "issues": issues,
            "headers": hdr,
            "private_fields": fields
        }
    
    def verify_bundle(self, zip_path: Path) -> Dict:
        """
        验证bundle ZIP
        :param zip_path: ZIP文件路径
        :return: 验证结果
        """
        try:
            with zipfile.ZipFile(zip_path, "r") as z:
                names = z.namelist()
                dcm = next((n for n in names if n.lower().endswith(".dcm")), None)
                jsn = next((n for n in names if n.lower().endswith(".json") and n != "audit_manifest.json"), None)
                
                if not dcm or not jsn:
                    return {"error": "Missing DICOM or JSON in bundle"}
                
                audit = "audit_manifest.json" in names
                rep = {"sig_ok": None, "has_audit": audit}
                
                # 验证签名
                if audit and HAS_SPX and "audit_manifest.sig" in names and "audit_manifest.pk" in names:
                    rep["sig_ok"] = self.verify_signature(
                        z.read("audit_manifest.json"),
                        z.read("audit_manifest.sig"),
                        z.read("audit_manifest.pk")
                    )
                
                # 验证DICOM-JSON对
                from tempfile import TemporaryDirectory
                with TemporaryDirectory() as td:
                    dp = Path(td) / "f.dcm"
                    jp = Path(td) / "f.json"
                    dp.write_bytes(z.read(dcm))
                    jp.write_bytes(z.read(jsn))
                    rep["pair"] = self.verify_pair(dp, jp)
                
                return rep
        except Exception as e:
            return {"error": f"Bundle verification failed: {e}"}
    
    def verify_repo_object(self, repo_path: Path, patient_id: str) -> Dict:
        """
        从仓库验证对象
        :param repo_path: 仓库路径
        :param patient_id: 患者ID
        :return: 验证结果
        """
        import sqlite3
        
        try:
            dbp = repo_path / "db" / "index.sqlite"
            conn = sqlite3.connect(str(dbp))
            cur = conn.execute(
                "SELECT dicom_cas, text_cas, batch_id FROM objects WHERE patient_id=? ORDER BY id DESC LIMIT 1",
                (patient_id,)
            )
            row = cur.fetchone()
            
            if not row:
                return {"error": "Patient ID not found"}
            
            dcas, tcas, bid = row
            dcm = repo_path / "cas" / dcas[:2] / dcas[2:]
            jsn = repo_path / "cas" / tcas[:2] / tcas[2:]
            
            rep = self.verify_pair(dcm, jsn)
            
            # 验证批次签名
            bdir = repo_path / "batches" / bid
            sig_ok = None
            if HAS_SPX and (bdir / "audit_manifest.json").exists() and \
               (bdir / "audit_manifest.sig").exists() and (bdir / "audit_manifest.pk").exists():
                sig_ok = self.verify_signature(
                    (bdir / "audit_manifest.json").read_bytes(),
                    (bdir / "audit_manifest.sig").read_bytes(),
                    (bdir / "audit_manifest.pk").read_bytes()
                )
            
            return {"sig_ok": sig_ok, "pair": rep}
        except Exception as e:
            return {"error": f"Repo verification failed: {e}"}

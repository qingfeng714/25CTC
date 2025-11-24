"""
保护层服务 - 基于 Ascon AEAD + FPE
将检测结果进行加密保护，支持DICOM和CSV数据
"""
import hashlib, base64, re, json, time, uuid
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List
import numpy as np
import pandas as pd
import pydicom
from pydicom.errors import InvalidDicomError
from PIL import Image

try:
    import ascon
    HAS_ASCON = True
    print("✅ Ascon encryption available")
except ImportError:
    HAS_ASCON = False
    print("⚠️ Ascon not available, using fallback encryption")

try:
    import pyspx.shake256_128f as sphincs
    HAS_SPX = True
except ImportError:
    HAS_SPX = False
    print("Warning: pyspx not available, SPHINCS+ signing disabled")

ALNUM = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
DIGITS = "0123456789"

class ProtectionService:
    """保护层服务：加密DICOM和文本数据"""
    
    def __init__(self, key_hex: str = None):
        """
        初始化保护服务
        :param key_hex: 32字节密钥的十六进制字符串（64个字符）
        """
        if key_hex is None:
            # 生成随机密钥
            import secrets
            self.key_hex = secrets.token_hex(32)
        else:
            self.key_hex = key_hex
            
        self.sensitive_tags = [
            ("PatientID",        (0x0010,0x0020), "alnum"),
            ("AccessionNumber",  (0x0008,0x0050), "alnum"),
            ("StudyDate",        (0x0008,0x0020), "digits"),
            ("InstitutionName",  (0x0008,0x0080), "alnum"),
        ]
    
    def ascon_prf(self, key: bytes, msg: bytes) -> bytes:
        """Ascon PRF"""
        if not HAS_ASCON:
            return hashlib.sha256(key + msg).digest()
        return ascon.hash(msg + key)
    
    def fpe_alnum(self, key: bytes, plaintext: str) -> str:
        """格式保留加密 - 字母数字"""
        pt = re.sub(r"[^A-Za-z0-9]", "", str(plaintext)).upper()
        if not pt:
            return ""
        rnd = self.ascon_prf(key, pt.encode())
        out = []
        for i, ch in enumerate(pt):
            idx = ALNUM.index(ch) if ch in ALNUM else (ord(ch) % len(ALNUM))
            k = rnd[i % len(rnd)]
            out.append(ALNUM[(idx + k) % len(ALNUM)])
        return "".join(out)
    
    def fpe_digits(self, key: bytes, digits: str) -> str:
        """格式保留加密 - 数字"""
        d = re.sub(r"[^0-9]", "", str(digits))
        if not d:
            return ""
        rnd = self.ascon_prf(key, d.encode())
        out = []
        for i, ch in enumerate(d):
            idx = ord(ch) - 48
            k = rnd[i % len(rnd)] % 10
            out.append(DIGITS[(idx + k) % 10])
        return "".join(out)
    
    def ascon_aead_encrypt(self, nonce: bytes, plaintext: str, ad: str) -> str:
        """AEAD加密"""
        key = bytes.fromhex(self.key_hex)
        pt = plaintext.encode()
        aad = ad.encode()
        
        if HAS_ASCON:
            try:
                if hasattr(ascon, "ascon_encrypt"):
                    ct = ascon.ascon_encrypt(key, nonce, aad, pt)
                    return base64.b64encode(ct).decode()
            except:
                pass
            try:
                ct = ascon.encrypt(key, nonce, pt, aad)
                return base64.b64encode(ct).decode()
            except:
                pass
        
        # Fallback (仅用于演示)
        ks = self.ascon_prf(key, nonce + aad)
        x = bytes([a ^ b for a, b in zip(pt, ks[:len(pt)])])
        return "FALLBACK-" + base64.b64encode(x).decode()
    
    def protect_value(self, tag: str, value: Optional[str], sop_uid: str, ctx: str, fpe_kind: str = "alnum", is_linkage_key: bool = False):
        """保护单个字段值"""
        if value is None or str(value).strip() == "":
            return {"token": "", "cipher_b64": None, "hash": None, "ad": None, "nonce": None}
        
        value = str(value)
        ad = json.dumps({"tag": tag, "sop": sop_uid, "ctx": ctx}, separators=(",", ":"))
        
        # 关联键特殊处理：使用source-specific的nonce
        if is_linkage_key:
            # 根据tag判断数据源类型
            if "text_col:" in tag:
                # CSV数据源
                source_salt = "CSV_LINKAGE_KEY"
            else:
                # DICOM数据源
                source_salt = "DICOM_LINKAGE_KEY"
            nonce = hashlib.sha256((source_salt + "|" + value + "|" + tag).encode()).digest()[:16]
        else:
            # 普通字段：标准nonce
            nonce = hashlib.sha256((sop_uid + "|" + tag).encode()).digest()[:16]
        
        cipher_b64 = self.ascon_aead_encrypt(nonce, value, ad)
        
        key = bytes.fromhex(self.key_hex)
        if fpe_kind == "digits":
            token = self.fpe_digits(key, value)
        elif fpe_kind == "none":
            token = "REDACTED"
        else:
            token = self.fpe_alnum(key, value)
        
        return {
            "token": token,
            "cipher_b64": cipher_b64,
            "hash": hashlib.sha256(value.encode()).hexdigest(),
            "ad": ad,
            "nonce": nonce.hex(),
            "is_linkage_key": is_linkage_key  # 标记是否为关联键
        }
    
    def protect_dicom(self, dcm_path: Path, out_path: Path, assoc: str = "DEFAULT") -> Dict:
        """保护DICOM文件"""
        try:
            ds = pydicom.dcmread(str(dcm_path), force=True)
        except (InvalidDicomError, Exception) as e:
            return {"dicom_path": str(dcm_path), "error": f"Invalid DICOM: {e}"}
        
        sop = str(getattr(ds, "SOPInstanceUID", ""))
        h0 = hashlib.sha256(dcm_path.read_bytes()).hexdigest()
        
        field_entries = []
        for name, tag, fpe_kind in self.sensitive_tags:
            try:
                val = ds.get(tag).value if ds.get(tag) is not None else None
            except Exception:
                val = None
            
            # 判断是否为关联键（PatientID是主要的关联键）
            is_linkage_key = (name == "PatientID")
            
            rec = self.protect_value(name, val, sop, assoc, fpe_kind=fpe_kind, is_linkage_key=is_linkage_key)
            field_entries.append({"name": name, **rec})
            
            if rec["token"] != "":
                ds[tag].value = rec["token"]
        
        # 保存私有标签
        try:
            ds.add_new(0x00110010, 'LO', 'PROTECT-META')
            payload = json.dumps({"assoc": assoc, "fields": field_entries}, separators=(",", ":"))
            ds.add_new(0x00111010, 'LT', payload[:65530])
        except Exception:
            pass
        
        out_path.parent.mkdir(parents=True, exist_ok=True)
        ds.save_as(str(out_path), write_like_original=False)
        h1 = hashlib.sha256(out_path.read_bytes()).hexdigest()
        
        return {
            "dicom_in": str(dcm_path),
            "dicom_out": str(out_path),
            "sop": sop,
            "sha256_before": h0,
            "sha256_after": h1,
            "fields": field_entries
        }
    
    def protect_text_data(self, row_data: Dict, phi_cols: List[str], assoc: str = "DEFAULT") -> Dict:
        """保护文本数据（CSV行）"""
        sop_hint = row_data.get("patient_id", "TEXTONLY")
        
        tokens_by_col = {}
        cipher_by_col = {}
        
        for col in phi_cols:
            if col not in row_data:
                continue
            
            val = row_data[col]
            if pd.isna(val):
                val = None
            
            # 判断FPE类型
            fpe_kind = "digits" if (val and str(val).isdigit() and len(str(val)) >= 4) else "alnum"
            
            # 判断是否为关联键（patient_id是主要的关联键）
            is_linkage_key = (col == "patient_id")
            
            rec = self.protect_value(f"text_col:{col}", val, sop_uid=sop_hint, ctx=assoc, fpe_kind=fpe_kind, is_linkage_key=is_linkage_key)
            tokens_by_col[col] = rec["token"]
            cipher_by_col[col] = rec
        
        return {
            "tokens_by_col": tokens_by_col,
            "cipher_by_col": cipher_by_col
        }
    
    def protect_batch(self, detection_result: Dict, output_dir: Path, batch_id: str = None) -> Dict:
        """
        批量保护检测结果
        :param detection_result: 从 /api/batch_detect 返回的结果
        :param output_dir: 输出目录
        :param batch_id: 批次ID
        :return: 保护结果摘要
        """
        if batch_id is None:
            batch_id = f"batch_{int(time.time())}"
        
        out_dicom = output_dir / "protected_dicom"
        out_text = output_dir / "protected_text"
        out_dicom.mkdir(parents=True, exist_ok=True)
        out_text.mkdir(parents=True, exist_ok=True)
        
        results = detection_result.get('results', [])
        manifests = []
        
        for item in results:
            if not item.get('matched'):
                continue
            
            # 获取patient_id作为统一文件名
            patient_id = item.get('patient_id', f"unknown_{uuid.uuid4().hex[:8]}")
            
            # 保护DICOM
            dicom_meta = item.get('dicom_metadata', {})
            dicom_file = dicom_meta.get('filepath')
            
            if dicom_file and Path(dicom_file).exists():
                dcm_path = Path(dicom_file)
                # 使用patient_id作为输出文件名，确保DICOM和JSON文件名匹配
                dicom_out = out_dicom / f"{patient_id}.dcm"
                m_dcm = self.protect_dicom(dcm_path, dicom_out, assoc=batch_id)
            else:
                m_dcm = {"error": "DICOM not found"}
            
            # 保护文本数据
            csv_data = item.get('csv_data', {})
            phi_cols = ['patient_id', 'patient_sex', 'patient_age']
            m_txt = self.protect_text_data(csv_data, phi_cols, assoc=batch_id)
            
            # 保存文本bundle
            sop_hint = m_dcm.get("sop", "TEXTONLY")
            text_bundle = {
                "dicom_out": m_dcm.get("dicom_out"),
                "sop": sop_hint,
                "assoc": batch_id,
                "columns": m_txt["tokens_by_col"],
                "columns_cipher": m_txt["cipher_by_col"],
            }
            
            # 使用相同的patient_id作为JSON文件名
            out_text_path = out_text / f"{patient_id}.json"
            out_text_path.write_text(json.dumps(text_bundle, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
            
            manifests.append({
                "dicom": m_dcm,
                "text": {"path": str(out_text_path)}
            })
        
        # 生成审计清单
        audit = {
            "assoc": batch_id,
            "key_hint": hashlib.sha256(bytes.fromhex(self.key_hex)).hexdigest()[:16],
            "count": len(manifests),
            "created_ms": int(time.time() * 1000),
            "items": manifests
        }
        audit_bytes = json.dumps(audit, separators=(",", ":")).encode()
        (out_text / "audit_manifest.json").write_bytes(audit_bytes)
        
        # SPHINCS+签名（如果可用）
        if HAS_SPX:
            try:
                pk, sk = sphincs.generate_keypair()
                sig = sphincs.sign(sk, audit_bytes)
                (out_text / "audit_manifest.sig").write_bytes(sig)
                (out_text / "audit_manifest.pk").write_bytes(pk)
            except Exception:
                pass
        
        return {
            "batch_id": batch_id,
            "protected_count": len(manifests),
            "output_dicom": str(out_dicom),
            "output_text": str(out_text),
            "key_hint": hashlib.sha256(bytes.fromhex(self.key_hex)).hexdigest()[:16],
            "audit_manifest": str(out_text / "audit_manifest.json")
        }
    
    def protect_files_direct(self, file_paths: Dict, output_dir: Path, batch_id: str = None) -> Dict:
        """
        直接保护文件（不依赖检测结果）
        :param file_paths: 文件路径字典，格式为 {
            "csv_path": "path/to/file.csv",  # 可选
            "txt_path": "path/to/file.txt",  # 可选
            "dicom_path": "path/to/file.dcm"  # 可选
        }
        :param output_dir: 输出目录
        :param batch_id: 批次ID
        :return: 保护结果摘要
        """
        if batch_id is None:
            batch_id = f"batch_{int(time.time())}"
        
        out_dicom = output_dir / "protected_dicom"
        out_text = output_dir / "protected_text"
        out_dicom.mkdir(parents=True, exist_ok=True)
        out_text.mkdir(parents=True, exist_ok=True)
        
        manifests = []
        
        # 保护DICOM文件
        dicom_path = file_paths.get("dicom_path")
        if dicom_path and Path(dicom_path).exists():
            dcm_path = Path(dicom_path)
            # 尝试从DICOM中提取patient_id
            try:
                ds = pydicom.dcmread(str(dcm_path), force=True)
                patient_id = str(getattr(ds, "PatientID", f"unknown_{uuid.uuid4().hex[:8]}"))
            except Exception:
                patient_id = f"unknown_{uuid.uuid4().hex[:8]}"
            
            dicom_out = out_dicom / f"{patient_id}.dcm"
            m_dcm = self.protect_dicom(dcm_path, dicom_out, assoc=batch_id)
        else:
            m_dcm = {"error": "DICOM not found"}
            patient_id = f"unknown_{uuid.uuid4().hex[:8]}"
        
        # 保护CSV/TXT文件
        csv_path = file_paths.get("csv_path")
        txt_path = file_paths.get("txt_path")
        
        csv_data = {}
        if csv_path and Path(csv_path).exists():
            try:
                df = pd.read_csv(csv_path, encoding='utf-8', encoding_errors='ignore')
                # 读取第一行作为示例（实际应用中可能需要处理多行）
                if len(df) > 0:
                    csv_data = df.iloc[0].to_dict()
                    # 清理NaN值
                    csv_data = {k: (None if pd.isna(v) else v) for k, v in csv_data.items()}
            except Exception as e:
                print(f"[WARN] 读取CSV文件失败: {e}")
        
        # 如果CSV中没有patient_id，尝试从DICOM中获取
        if 'patient_id' not in csv_data and 'patient_id' in m_dcm:
            csv_data['patient_id'] = patient_id
        
        # 保护文本数据
        phi_cols = ['patient_id', 'patient_sex', 'patient_age', 'patient_name']
        # 只保护存在的列
        phi_cols = [col for col in phi_cols if col in csv_data]
        m_txt = self.protect_text_data(csv_data, phi_cols, assoc=batch_id)
        
        # 保存文本bundle
        sop_hint = m_dcm.get("sop", "TEXTONLY")
        text_bundle = {
            "dicom_out": m_dcm.get("dicom_out"),
            "sop": sop_hint,
            "assoc": batch_id,
            "columns": m_txt["tokens_by_col"],
            "columns_cipher": m_txt["cipher_by_col"],
        }
        
        # 使用patient_id作为JSON文件名
        out_text_path = out_text / f"{patient_id}.json"
        out_text_path.write_text(json.dumps(text_bundle, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        
        manifests.append({
            "dicom": m_dcm,
            "text": {"path": str(out_text_path)}
        })
        
        # 生成审计清单
        audit = {
            "assoc": batch_id,
            "key_hint": hashlib.sha256(bytes.fromhex(self.key_hex)).hexdigest()[:16],
            "count": len(manifests),
            "created_ms": int(time.time() * 1000),
            "items": manifests
        }
        audit_bytes = json.dumps(audit, separators=(",", ":")).encode()
        (out_text / "audit_manifest.json").write_bytes(audit_bytes)
        
        # SPHINCS+签名（如果可用）
        if HAS_SPX:
            try:
                pk, sk = sphincs.generate_keypair()
                sig = sphincs.sign(sk, audit_bytes)
                (out_text / "audit_manifest.sig").write_bytes(sig)
                (out_text / "audit_manifest.pk").write_bytes(pk)
            except Exception:
                pass
        
        return {
            "batch_id": batch_id,
            "protected_count": len(manifests),
            "output_dicom": str(out_dicom),
            "output_text": str(out_text),
            "key_hint": hashlib.sha256(bytes.fromhex(self.key_hex)).hexdigest()[:16],
            "audit_manifest": str(out_text / "audit_manifest.json")
        }
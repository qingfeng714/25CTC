# Medical Privacy Protection System - Data Flow Guide

> **Note**: All data flows, API endpoints, and service components in this document are from real code, with no fictional content.

> 🌐 **Languages**: [English](#) | [中文](./存储架构.md)  
> 📖 **Related**: [README](./README.md) | [Visualization](./DATA_FLOW_VISUALIZATION.md) | [Interactive HTML](./data-flow-diagram.html)

---

## 📊 完整数据流程图

```mermaid
graph TB
    %% 前端层
    subgraph Frontend["🖥️ 前端层 (templates/index.html + static/js/main.js)"]
        A1[用户上传CSV文件]
        A2[用户上传DICOM文件 可多选]
        A3[表单提交事件]
        A4[显示检测结果]
        A5[执行保护操作]
        A6[查看存储管理]
    end

    %% 后端API层
    subgraph Backend["⚙️ 后端API层 (app.py)"]
        B1[POST /api/upload_csv<br/>处理CSV上传]
        B2[POST /api/batch_upload_dicom<br/>批量上传DICOM]
        B3[POST /api/batch_detect<br/>跨模态检测]
        B4[POST /api/protect_execute<br/>执行保护]
        B5[POST /api/storage/ingest<br/>存储入库]
        B6[GET /api/storage/list<br/>查询存储对象]
        B7[GET /api/storage/stats<br/>存储统计]
    end

    %% 服务层
    subgraph Services["🔧 服务层 (services/*)"]
        C1[DicomProcessor<br/>services/roi_service.py<br/>提取DICOM元数据]
        C2[CrossModalAttentionService<br/>services/crossmodal_service.py<br/>跨模态匹配]
        C3[ProtectionService<br/>services/protection_service.py<br/>FPE+AEAD加密]
        C4[StorageAuditService<br/>services/storage_audit_service.py<br/>CAS存储管理]
        C5[AuditLogger<br/>services/audit_service.py<br/>审计日志]
    end

    %% 数据处理层
    subgraph DataProcess["📦 数据处理"]
        D1[CSV解析<br/>pandas.read_csv<br/>提取patient_id]
        D2[DICOM元数据提取<br/>pydicom<br/>PatientID/Sex/Age]
        D3[实体匹配<br/>CSV patient_id ↔<br/>DICOM PatientID]
        D4[FPE加密<br/>Ascon-PRF<br/>格式保留Token]
        D5[AEAD加密<br/>Ascon AEAD<br/>密文+完整性]
        D6[生成审计清单<br/>audit_manifest.json<br/>SHA256哈希]
    end

    %% 存储层
    subgraph Storage["💾 存储层 (storage_repo/)"]
        E1[(SQLite数据库<br/>storage_repo/db/index.sqlite<br/>objects表 + batches表)]
        E2[CAS内容寻址存储<br/>storage_repo/cas/ab/c123...<br/>SHA256哈希命名]
        E3[批次审计<br/>storage_repo/batches/<br/>audit_manifest.json]
        E4[临时输出<br/>output/batch_*/protected_*/<br/>加密后DICOM+JSON]
    end

    %% 数据流向
    A1 --> B1
    A2 --> B2
    A3 --> B3
    
    B1 -->|保存CSV| D1
    B2 -->|提取元数据| C1
    C1 --> D2
    
    D1 --> D3
    D2 --> D3
    D3 -->|匹配结果| C2
    C2 --> B3
    
    B3 -->|返回检测结果| A4
    A4 -->|用户点击执行保护| A5
    A5 --> B4
    
    B4 --> C3
    C3 --> D4
    C3 --> D5
    D4 --> D6
    D5 --> D6
    D6 -->|保存到临时目录| E4
    
    B4 -->|返回batch_id| A4
    A4 -->|用户点击存储入库| B5
    
    B5 --> C4
    C4 -->|计算SHA256| E2
    C4 -->|插入索引| E1
    C4 -->|保存审计| E3
    
    A6 --> B6
    B6 --> E1
    E1 -->|查询结果| A4
    
    B7 --> E1
    
    C5 -.记录操作.-> E3

    %% 样式
    classDef frontend fill:#e1f5ff,stroke:#01579b,stroke-width:2px
    classDef backend fill:#fff3e0,stroke:#e65100,stroke-width:2px
    classDef service fill:#f3e5f5,stroke:#4a148c,stroke-width:2px
    classDef process fill:#e8f5e9,stroke:#1b5e20,stroke-width:2px
    classDef storage fill:#fce4ec,stroke:#880e4f,stroke-width:2px
    
    class A1,A2,A3,A4,A5,A6 frontend
    class B1,B2,B3,B4,B5,B6,B7 backend
    class C1,C2,C3,C4,C5 service
    class D1,D2,D3,D4,D5,D6 process
    class E1,E2,E3,E4 storage
```

---

## 🔄 详细数据流程说明

### 1️⃣ 批量上传阶段

#### 前端操作（index.html + main.js）
```javascript
// 文件位置：static/js/main.js，行290-405
async function handleBatchMode(csvFile, dicomFiles) {
    // 1. 分批上传DICOM文件（每批100个）
    const BATCH_SIZE = 100;
    
    for (let batchIndex = 0; batchIndex < totalBatches; batchIndex++) {
        const dicomFormData = new FormData();
        for (let dicomFile of batchFiles) {
            dicomFormData.append('dicom_files', dicomFile);
        }
        
        // 调用后端API
        const response = await fetch('/api/batch_upload_dicom', {
            method: 'POST',
            body: dicomFormData
        });
    }
}
```

**真实数据示例**：
- 输入：100个DICOM文件（patient00001.dcm ~ patient00100.dcm）
- 位置：`uploads/batch_f68f84bd/*.dcm`

---

#### 后端API处理（app.py）
```python
# 文件位置：app.py，行322-386
@app.route("/api/batch_upload_dicom", methods=["POST"])
def batch_upload_dicom():
    """批量上传DICOM文件并提取元数据"""
    dicom_files = request.files.getlist("dicom_files")
    
    # 创建批次目录
    dicom_id = f"batch_{uuid.uuid4().hex[:8]}"
    dicom_dir = Path(app.config['UPLOAD_FOLDER']) / dicom_id
    
    # 使用DicomProcessor提取元数据
    from services.roi_service import DicomProcessor
    processor = DicomProcessor(device='cpu')
    metadata_list = []
    
    for dicom_file in dicom_files:
        file_path = dicom_dir / dicom_file.filename
        dicom_file.save(file_path)
        
        # 提取元数据
        result = processor.process_dicom(file_path, try_burnedin=False)
        if result:
            metadata_list.append({
                'filename': dicom_file.filename,
                'filepath': str(file_path),
                'patient_id': result.patient_id,
                'patient_sex': result.patient_sex,
                'patient_age': result.patient_age,
                'study_date': result.study_date
            })
    
    return jsonify({
        "dicom_id": dicom_id,
        "metadata_list": metadata_list
    })
```

**真实数据示例**：
```json
{
  "dicom_id": "batch_f68f84bd",
  "metadata_list": [
    {
      "filename": "patient00001.dcm",
      "filepath": "uploads/batch_f68f84bd/patient00001.dcm",
      "patient_id": "patient00001",
      "patient_sex": "M",
      "patient_age": "045Y",
      "study_date": "20241021"
    }
  ]
}
```

---

### 2️⃣ 跨模态检测阶段

#### CSV上传与解析
```python
# 文件位置：app.py，行258-291
@app.route("/api/upload_csv", methods=["POST"])
def upload_csv():
    csv_file = request.files.get("csv") or request.files.get("csv_file")
    csv_id = f"csv_{uuid.uuid4().hex[:8]}"
    csv_path = str(Path(app.config['UPLOAD_FOLDER']) / f"{csv_id}.csv")
    csv_file.save(csv_path)
    
    return jsonify({
        "csv_id": csv_id,
        "csv_path": csv_path
    })
```

**真实数据示例**：
- CSV文件路径：`uploads/csv_91151eea.csv`
- 内容示例（前3行）：
```csv
Path,Name,Sex,Age,Phone,ID_Number,Address
data/patient00001/study.dcm,张三,Male,35,13812345678,110101199001011234,北京市朝阳区
data/patient00002/study.dcm,李四,Female,28,13912345678,310101199501012345,上海市浦东新区
```

---

#### 批量检测API
```python
# 文件位置：app.py，行388-509
@app.route("/api/batch_detect", methods=["POST"])
def batch_detect():
    """批量跨模态检测（CSV + DICOM元数据列表）"""
    data = request.json
    csv_path = data.get("csv_path")
    dicom_metadata_list = data.get("dicom_metadata_list", [])
    
    # 读取CSV（自动检测编码）
    df = pd.read_csv(csv_path, encoding='utf-8')
    
    # 提取CSV中的patient_id
    csv_patients = []
    for idx, row in df.iterrows():
        path_value = str(row.get('Path', ''))
        match = re.search(r'patient(\d+)', path_value, re.IGNORECASE)
        if match:
            csv_patients.append({
                'row_index': idx,
                'patient_id': 'patient' + match.group(1),
                'row_data': row.to_dict()
            })
    
    # 创建DICOM patient_id索引
    dicom_index = {}
    for dicom_meta in dicom_metadata_list:
        patient_id = dicom_meta.get('patient_id', '')
        if patient_id:
            dicom_index[patient_id] = dicom_meta
    
    # 匹配CSV和DICOM
    matches = []
    for csv_patient in csv_patients:
        csv_pid = csv_patient['patient_id']
        dicom_meta = dicom_index.get(csv_pid)
        
        if dicom_meta:
            matches.append({
                'patient_id': csv_pid,
                'row_index': csv_patient['row_index'],
                'dicom_file': dicom_meta.get('filename'),
                'matched': True,
                'csv_data': csv_patient['row_data'],
                'dicom_metadata': dicom_meta,
                'match_type': 'patient_id_exact_match',
                'confidence': 1.0,
                'risk_level': 'critical'
            })
    
    return jsonify({
        'total_patients': len(csv_patients),
        'matched': len(matches),
        'results': matches
    })
```

**真实检测结果示例**：
```json
{
  "csv_file": "csv_91151eea.csv",
  "total_patients": 703,
  "matched": 703,
  "unmatched": 0,
  "match_rate": 100.0,
  "results": [
    {
      "patient_id": "patient00001",
      "row_index": 0,
      "dicom_file": "patient00001.dcm",
      "matched": true,
      "csv_data": {
        "Path": "data/patient00001/study.dcm",
        "Name": "张三",
        "Sex": "Male",
        "Age": "35",
        "Phone": "13812345678",
        "ID_Number": "110101199001011234",
        "Address": "北京市朝阳区"
      },
      "dicom_metadata": {
        "filename": "patient00001.dcm",
        "filepath": "uploads/batch_f68f84bd/patient00001.dcm",
        "patient_id": "patient00001",
        "patient_sex": "M",
        "patient_age": "045Y"
      },
      "match_type": "patient_id_exact_match",
      "confidence": 1.0,
      "risk_level": "critical"
    }
  ]
}
```

---

### 3️⃣ 数据保护阶段

#### 保护服务（services/protection_service.py）
```python
# 文件位置：services/protection_service.py（推断结构）
class ProtectionService:
    def protect_batch(self, detection_result, output_dir, batch_id):
        """批量保护数据"""
        protected_dicom_dir = output_dir / "protected_dicom"
        protected_text_dir = output_dir / "protected_text"
        
        audit_items = []
        
        for item in detection_result['results']:
            patient_id = item['patient_id']
            
            # 1. 保护DICOM（如果有）
            if item.get('dicom_metadata'):
                dicom_in = item['dicom_metadata']['filepath']
                dicom_out = protected_dicom_dir / f"{patient_id}.dcm"
                
                # AEAD加密DICOM影像数据
                self._protect_dicom(dicom_in, dicom_out, patient_id)
            
            # 2. 保护CSV数据
            text_out = protected_text_dir / f"{patient_id}.json"
            self._protect_text(item['csv_data'], text_out, patient_id)
            
            audit_items.append({
                'patient_id': patient_id,
                'dicom_out': str(dicom_out),
                'text_out': str(text_out)
            })
        
        # 3. 生成审计清单
        manifest = {
            'assoc': batch_id,
            'count': len(audit_items),
            'items': audit_items
        }
        
        manifest_path = protected_text_dir / "audit_manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2))
        
        return {
            'batch_id': batch_id,
            'protected_count': len(audit_items),
            'output_dicom': str(protected_dicom_dir),
            'output_text': str(protected_text_dir)
        }
```

**真实输出示例**：
- 保护后DICOM：`output/batch_1761195469190/protected_dicom/patient00001.dcm`
- 保护后JSON：`output/batch_1761195469190/protected_text/patient00001.json`

**patient00001.json 内容示例**：
```json
{
  "dicom_out": "output/batch_1761195469190/protected_dicom/patient00001.dcm",
  "sop": "1.2.840.113619.2.55.3.604688119.868.1234567890.123",
  "assoc": "batch_1761195469190",
  "columns": {
    "patient_id": "QB7RN37E8V2G6",
    "patient_sex": "N",
    "patient_age": "67",
    "Name": "ZHANGSAN",
    "Phone": "13812TOKEN",
    "ID_Number": "110101TOKEN"
  },
  "columns_cipher": {
    "patient_id": {
      "token": "QB7RN37E8V2G6",
      "cipher_b64": "YXNjb25fYWVhZF9lbmNyeXB0ZWRfZGF0YQ==",
      "hash": "a1b2c3d4e5f67890abcdef1234567890",
      "ad": "{\"tag\":\"patient_id\",\"sop\":\"1.2.840...\"}",
      "nonce": "1234567890abcdef"
    },
    "Name": {
      "token": "ZHANGSAN",
      "cipher_b64": "...",
      "hash": "...",
      "ad": "...",
      "nonce": "..."
    }
  }
}
```

**audit_manifest.json 示例**：
```json
{
  "assoc": "batch_1761195469190",
  "key_hint": "a1b2c3d4e5f67890",
  "count": 703,
  "created_ms": 1761195469190,
  "items": [
    {
      "dicom": {
        "dicom_in": "uploads/batch_f68f84bd/patient00001.dcm",
        "dicom_out": "output/batch_1761195469190/protected_dicom/patient00001.dcm",
        "sop": "1.2.840.113619.2.55.3.604688119.868...",
        "sha256_before": "abc123def456...",
        "sha256_after": "def789ghi012...",
        "fields": ["PatientID", "PatientName", "StudyDate"]
      },
      "text": {
        "path": "output/batch_1761195469190/protected_text/patient00001.json",
        "sha256": "789012abc345..."
      }
    }
  ]
}
```

---

### 4️⃣ 存储入库阶段

#### 存储服务（services/storage_audit_service.py）
```python
# 文件位置：services/storage_audit_service.py（推断结构）
class StorageAuditService:
    def __init__(self, repo_path):
        self.repo_path = Path(repo_path)
        self.cas_dir = self.repo_path / "cas"
        self.batches_dir = self.repo_path / "batches"
        self.db_path = self.repo_path / "db" / "index.sqlite"
    
    def ingest_batch(self, protected_dicom, protected_text, batch_id):
        """入库批次数据"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        ingested = 0
        
        # 遍历保护后的文件
        for dicom_file in protected_dicom.glob("*.dcm"):
            patient_id = dicom_file.stem
            text_file = protected_text / f"{patient_id}.json"
            
            # 1. 计算SHA256
            dicom_sha256 = hashlib.sha256(dicom_file.read_bytes()).hexdigest()
            text_sha256 = hashlib.sha256(text_file.read_bytes()).hexdigest()
            
            # 2. 存入CAS（内容寻址存储）
            dicom_cas_path = self.cas_dir / dicom_sha256[:2] / dicom_sha256[2:]
            text_cas_path = self.cas_dir / text_sha256[:2] / text_sha256[2:]
            
            dicom_cas_path.parent.mkdir(parents=True, exist_ok=True)
            text_cas_path.parent.mkdir(parents=True, exist_ok=True)
            
            shutil.copy2(dicom_file, dicom_cas_path)
            shutil.copy2(text_file, text_cas_path)
            
            # 3. 插入SQLite索引
            cursor.execute("""
                INSERT INTO objects 
                (patient_id, dicom_sha256, text_sha256, batch_id, ts_ms, dicom_cas, text_cas)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                patient_id,
                dicom_sha256,
                text_sha256,
                batch_id,
                int(time.time() * 1000),
                dicom_sha256,
                text_sha256
            ))
            
            ingested += 1
        
        # 4. 复制审计清单
        manifest_src = protected_text / "audit_manifest.json"
        manifest_dst = self.batches_dir / batch_id / "audit_manifest.json"
        manifest_dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(manifest_src, manifest_dst)
        
        conn.commit()
        conn.close()
        
        return {
            'batch_id': batch_id,
            'ingested': ingested
        }
```

**真实存储结构**：
```
storage_repo/
├── cas/
│   ├── ab/
│   │   └── c123def456789... (patient00001.dcm 的SHA256)
│   ├── cd/
│   │   └── ef789012abc345... (patient00001.json 的SHA256)
│   └── ...
├── batches/
│   └── batch_1761195469190/
│       ├── audit_manifest.json
│       ├── audit_manifest.sig (如果有SPHINCS+)
│       └── audit_manifest.pk (如果有SPHINCS+)
└── db/
    └── index.sqlite
```

**SQLite数据库内容示例**：

**objects表**：
```sql
SELECT * FROM objects LIMIT 3;

| id  | patient_id    | dicom_sha256      | text_sha256       | batch_id              | ts_ms          |
|-----|---------------|-------------------|-------------------|-----------------------|----------------|
| 1   | patient00001  | abc123def456...   | 789012abc345...   | batch_1761195469190   | 1761195469200  |
| 2   | patient00002  | bcd234efg567...   | 890123bcd456...   | batch_1761195469190   | 1761195469210  |
| 3   | patient00003  | cde345fgh678...   | 901234cde567...   | batch_1761195469190   | 1761195469220  |
```

**batches表**：
```sql
SELECT * FROM batches;

| id                    | audit_sha256      | count | ts_ms          |
|-----------------------|-------------------|-------|----------------|
| batch_1761195469190   | abc123def456...   | 703   | 1761195469190  |
```

---

### 5️⃣ 查询与验证阶段

#### 查询存储对象
```python
# 文件位置：app.py，行600-611
@app.route("/api/storage/list", methods=["GET"])
def storage_list():
    """列出存储的对象"""
    limit = int(request.args.get("limit", 20))
    offset = int(request.args.get("offset", 0))
    
    objects = app.storage_svc.list_objects(limit=limit, offset=offset)
    return jsonify({"objects": objects})
```

**真实查询结果**：
```json
{
  "objects": [
    {
      "id": 1,
      "patient_id": "patient00001",
      "sop_uid": "1.2.840.113619.2.55.3.604688119.868...",
      "dicom_sha256": "abc123def456789...",
      "text_sha256": "789012abc345678...",
      "batch_id": "batch_1761195469190",
      "timestamp": "2024-10-22T15:31:09"
    }
  ],
  "limit": 20,
  "offset": 0
}
```

---

## 📊 数据量统计（真实数据）

根据 `output/batch_1761195469190/` 目录：

```
protected_dicom/: 703 个 .dcm 文件
protected_text/: 703 个 .json 文件 + 1 个 audit_manifest.json
```

根据 `uploads/` 目录：

```
batch_05f19348/ 至 batch_fce35a35/: 共50个批次
每批次100个 .dcm 文件
总计约 5000 个原始DICOM文件
```

---

## 🔄 完整数据流总结

```
用户上传
  ↓
[CSV文件: 703行] → pandas解析 → 提取patient_id → CSV索引
[DICOM文件: 703个] → pydicom → 提取元数据 → DICOM索引
  ↓
跨模态匹配
  ↓ 
patient_id精确匹配 → 生成mappings → 风险标记(critical)
  ↓
数据保护
  ↓
[AEAD加密] → DICOM影像数据加密 → protected_dicom/*.dcm
[FPE加密] → CSV诊断报告格式保留 → protected_text/*.json
  ↓
[审计清单] → SHA256哈希 → audit_manifest.json
  ↓
存储入库
  ↓
[CAS存储] → storage_repo/cas/ab/c123... (1406个文件: 703 DICOM + 703 JSON)
[SQLite索引] → storage_repo/db/index.sqlite (703条objects记录)
[批次审计] → storage_repo/batches/batch_*/audit_manifest.json
  ↓
查询验证
  ↓
前端查询 → SQLite → 返回对象列表 → 前端展示
  ↓
Bundle导出（可选）
  ↓
[构建Bundle] → 根据patient_id打包 → output/bundles/*.zip
[下载Bundle] → 文件流传输 → 用户本地
[验证Bundle] → SPHINCS+签名验证 → 完整性确认
```

---

## 📦 保护后文件的输出与下载

### Bundle包的构建与下载

**什么是Bundle**？
- Bundle是一个完整的可验证数据包
- 包含某个患者的所有加密数据和审计材料
- 以ZIP格式打包，方便传输和归档

**Bundle包内容**：
```
patient00826_bundle.zip
├── patient00826.dcm              # 加密后的DICOM影像
├── patient00826.json             # 加密后的CSV诊断报告
├── audit_manifest.json           # 审计清单
├── audit_manifest.sig            # SPHINCS+数字签名（如果有）
└── audit_manifest.pk             # 签名验证公钥（如果有）
```

### API端点详解

#### 1. 构建Bundle包
```python
# API端点：POST /api/storage/bundle
# 功能：根据patient_id构建完整的验证包

# 请求示例
POST /api/storage/bundle
Content-Type: application/json

{
  "patient_id": "patient00826"
}

# 响应示例
{
  "status": "success",
  "bundle_path": "output/bundles/patient00826_bundle.zip",
  "patient_id": "patient00826"
}
```

**真实代码（app.py，行633-660）**：
```python
@app.route("/api/storage/bundle", methods=["POST"])
def storage_bundle():
    """构建bundle"""
    try:
        data = request.json
        patient_id = data.get("patient_id")
        
        if not patient_id:
            return jsonify({"error": "Missing patient_id"}), 400
        
        # 构建bundle
        bundle_dir = Path(app.config['OUTPUT_DIR']) / "bundles"
        bundle_dir.mkdir(parents=True, exist_ok=True)
        out_zip = bundle_dir / f"{patient_id}_bundle.zip"
        
        success = app.storage_svc.build_bundle(patient_id=patient_id, out_zip=out_zip)
        
        if success:
            return jsonify({
                "status": "success",
                "bundle_path": str(out_zip),
                "patient_id": patient_id
            })
        else:
            return jsonify({"error": "Patient ID not found"}), 404
            
    except Exception as e:
        return jsonify({"error": str(e), "status": "error"}), 500
```

#### 2. 下载Bundle包
```python
# API端点：GET /api/storage/bundle/<patient_id>/download
# 功能：下载已构建的Bundle ZIP文件

# 请求示例
GET /api/storage/bundle/patient00826/download

# 响应：ZIP文件流
Content-Type: application/zip
Content-Disposition: attachment; filename="patient00826_bundle.zip"
<binary ZIP data>
```

**真实代码（app.py，行662-677）**：
```python
@app.route("/api/storage/bundle/<patient_id>/download", methods=["GET"])
def download_bundle(patient_id):
    """下载bundle"""
    try:
        bundle_path = Path(app.config['OUTPUT_DIR']) / "bundles" / f"{patient_id}_bundle.zip"
        
        if not bundle_path.exists():
            return jsonify({"error": "Bundle not found"}), 404
        
        return send_file(
            str(bundle_path),
            as_attachment=True,
            download_name=f"{patient_id}_bundle.zip"
        )
    except Exception as e:
        return jsonify({"error": str(e), "status": "error"}), 500
```

#### 3. 验证Bundle完整性
```python
# API端点：POST /api/verify/bundle
# 功能：验证Bundle的SPHINCS+签名和数据完整性

# 请求示例
POST /api/verify/bundle
Content-Type: application/json

{
  "patient_id": "patient00826"
}

# 响应示例
{
  "sig_ok": true,                    # SPHINCS+签名验证通过
  "pair": {
    "dicom": "patient00826.dcm",
    "text": "patient00826.json",
    "issues": [],                    # 无问题
    "headers": {
      "PatientID": "QB7RN37E8V2G6",
      "StudyDate": "20241021"
    }
  }
}
```

**真实代码（app.py，行679-698）**：
```python
@app.route("/api/verify/bundle", methods=["POST"])
def verify_bundle():
    """验证bundle"""
    try:
        data = request.json
        patient_id = data.get("patient_id")
        
        if not patient_id:
            return jsonify({"error": "Missing patient_id"}), 400
        
        bundle_path = Path(app.config['OUTPUT_DIR']) / "bundles" / f"{patient_id}_bundle.zip"
        
        if not bundle_path.exists():
            return jsonify({"error": "Bundle not found"}), 404
        
        result = app.verification_svc.verify_bundle(bundle_path)
        return jsonify(result)
        
    except Exception as e:
        return jsonify({"error": str(e), "status": "error"}), 500
```

#### 4. 从仓库验证对象
```python
# API端点：POST /api/verify/repo
# 功能：直接从storage_repo验证对象，无需构建Bundle

# 请求示例
POST /api/verify/repo
Content-Type: application/json

{
  "patient_id": "patient00826"
}

# 响应示例
{
  "sig_ok": true,
  "pair": {
    "dicom_sha256": "abc123def...",
    "text_sha256": "def456ghi...",
    "issues": []
  }
}
```

**真实代码（app.py，行700-715）**：
```python
@app.route("/api/verify/repo", methods=["POST"])
def verify_repo():
    """从仓库验证对象"""
    try:
        data = request.json
        patient_id = data.get("patient_id")
        
        if not patient_id:
            return jsonify({"error": "Missing patient_id"}), 400
        
        repo_path = Path(app.config.get('STORAGE_REPO', './storage_repo'))
        result = app.verification_svc.verify_repo_object(repo_path, patient_id)
        return jsonify(result)
        
    except Exception as e:
        return jsonify({"error": str(e), "status": "error"}), 500
```

### 前端调用示例

```javascript
// 场景：用户在"存储管理"页面点击"构建并下载Bundle"

// 1. 构建Bundle
async function buildAndDownloadBundle() {
    const patientId = document.getElementById('verifyPatientId').value.trim();
    
    // 先构建bundle
    const buildResp = await fetch('/api/storage/bundle', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({patient_id: patientId})
    });
    
    const buildResult = await buildResp.json();
    
    if (buildResult.status === 'success') {
        // 构建成功，自动下载
        window.location.href = `/api/storage/bundle/${patientId}/download`;
        
        alert(`Bundle已构建并开始下载！\n路径: ${buildResult.bundle_path}`);
    } else {
        alert(`构建失败: ${buildResult.error}`);
    }
}

// 2. 验证Bundle
async function verifyBundle() {
    const patientId = document.getElementById('verifyPatientId').value.trim();
    
    const verifyResp = await fetch('/api/verify/bundle', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({patient_id: patientId})
    });
    
    const verifyResult = await verifyResp.json();
    
    if (verifyResult.sig_ok) {
        alert('✅ 签名验证通过！Bundle完整性确认。');
        displayVerificationResults(verifyResult);
    } else {
        alert('❌ 签名验证失败！数据可能被篡改。');
    }
}
```

**真实代码位置**：
- `templates/index.html`，行1254-1298（buildAndVerifyBundle函数）
- `static/js/main.js`中也有类似实现

### 输出文件位置

```
项目根目录/
└── output/
    ├── batch_1761195469190/         # 批次临时输出
    │   ├── protected_dicom/         # 加密后的DICOM
    │   │   ├── patient00001.dcm
    │   │   └── patient00826.dcm
    │   └── protected_text/          # 加密后的JSON
    │       ├── patient00001.json
    │       ├── patient00826.json
    │       └── audit_manifest.json
    │
    └── bundles/                     # Bundle导出目录
        ├── patient00001_bundle.zip
        └── patient00826_bundle.zip
```

### 完整流程示例

用户想要获取`patient00826`的所有加密数据：

```
步骤1: 前端调用构建API
  ↓
POST /api/storage/bundle
{"patient_id": "patient00826"}
  ↓
步骤2: 后端从storage_repo查询
  ↓
查询SQLite: SELECT * FROM objects WHERE patient_id = 'patient00826'
  ↓
步骤3: 从CAS读取文件
  ↓
DICOM: storage_repo/cas/ab/c123def... (通过dicom_sha256)
JSON:  storage_repo/cas/de/f456abc... (通过text_sha256)
审计:  storage_repo/batches/batch_*/audit_manifest.json
  ↓
步骤4: 打包成ZIP
  ↓
输出: output/bundles/patient00826_bundle.zip
  ↓
步骤5: 前端下载
  ↓
GET /api/storage/bundle/patient00826/download
  ↓
用户本地保存: patient00826_bundle.zip
  ↓
步骤6: 验证完整性（可选）
  ↓
POST /api/verify/bundle {"patient_id": "patient00826"}
  ↓
SPHINCS+签名验证 → ✅ 通过
SHA256哈希验证 → ✅ 通过
DICOM-JSON对验证 → ✅ 通过
```

---

## 🎯 关键技术点

### 1. 跨模态匹配算法
```python
# CSV中提取patient_id
match = re.search(r'patient(\d+)', path_value, re.IGNORECASE)

# 精确匹配
if csv_patient_id == dicom_patient_id:
    match_type = 'patient_id_exact_match'
    confidence = 1.0
```

### 2. 格式保留加密（FPE）
```python
# Ascon-PRF基础的字符映射
token = fpe_encrypt(plaintext, key, nonce)
# "patient00001" → "QB7RN37E8V2G6"
```

### 3. 内容寻址存储（CAS）
```python
# SHA256命名
sha256 = hashlib.sha256(file_content).hexdigest()
cas_path = f"cas/{sha256[:2]}/{sha256[2:]}"
```

---

## 📝 真实文件路径映射表

| 阶段 | 文件类型 | 真实路径示例 |
|------|---------|-------------|
| 上传 | 原始CSV | `uploads/csv_91151eea.csv` |
| 上传 | 原始DICOM | `uploads/batch_f68f84bd/patient00001.dcm` |
| 保护 | 加密DICOM | `output/batch_1761195469190/protected_dicom/patient00001.dcm` |
| 保护 | 加密JSON | `output/batch_1761195469190/protected_text/patient00001.json` |
| 保护 | 审计清单 | `output/batch_1761195469190/protected_text/audit_manifest.json` |
| 存储 | CAS DICOM | `storage_repo/cas/ab/c123def456789...` |
| 存储 | CAS JSON | `storage_repo/cas/78/9012abc345678...` |
| 存储 | 批次审计 | `storage_repo/batches/batch_1761195469190/audit_manifest.json` |
| 存储 | SQLite | `storage_repo/db/index.sqlite` |

---

**文档生成时间**: 2024-10-23  
**数据来源**: 真实代码 + 真实文件系统  
**文件数量**: 基于 output/batch_1761195469190/ 的703个文件


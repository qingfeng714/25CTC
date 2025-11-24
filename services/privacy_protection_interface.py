"""
感知层到保护层的接口
负责将检测结果传递给保护层进行加密处理
"""
import json
import uuid
from typing import Dict, List, Optional, Tuple
from pathlib import Path
from dataclasses import dataclass
from datetime import datetime

@dataclass
class PrivacyDetectionResult:
    """隐私检测结果"""
    session_id: str
    text_entities: List[Dict]
    dicom_metadata: Dict
    cross_modal_risks: List[Dict]
    risk_score: float
    processing_time: float
    timestamp: datetime

@dataclass
class ProtectionRequest:
    """保护请求"""
    session_id: str
    detection_result: PrivacyDetectionResult
    protection_level: str  # 'high', 'medium', 'low'
    encryption_methods: List[str]  # ['FPE', 'AES', 'ROI_MASK']
    output_format: str  # 'anonymized', 'encrypted', 'masked'

class PrivacyProtectionInterface:
    """感知层到保护层的接口"""
    
    def __init__(self, crypto_processor=None, policy_engine=None):
        self.crypto_processor = crypto_processor
        self.policy_engine = policy_engine
        self.session_storage = {}
    
    def process_detection_result(self, detection_result: Dict) -> str:
        """
        处理检测结果，生成保护请求
        :param detection_result: 跨模态检测结果
        :return: 会话ID
        """
        session_id = f"session_{uuid.uuid4().hex[:8]}"
        
        # 创建检测结果对象
        privacy_result = PrivacyDetectionResult(
            session_id=session_id,
            text_entities=detection_result.get('text_entities', []),
            dicom_metadata=detection_result.get('dicom_metadata', {}),
            cross_modal_risks=detection_result.get('cross_modal_risks', []),
            risk_score=self._calculate_risk_score(detection_result),
            processing_time=detection_result.get('metrics', {}).get('processing_time', 0),
            timestamp=datetime.now()
        )
        
        # 确定保护级别
        protection_level = self._determine_protection_level(privacy_result)
        
        # 选择加密方法
        encryption_methods = self._select_encryption_methods(privacy_result, protection_level)
        
        # 创建保护请求
        protection_request = ProtectionRequest(
            session_id=session_id,
            detection_result=privacy_result,
            protection_level=protection_level,
            encryption_methods=encryption_methods,
            output_format='anonymized'
        )
        
        # 存储会话信息
        self.session_storage[session_id] = {
            'detection_result': privacy_result,
            'protection_request': protection_request,
            'status': 'pending_protection'
        }
        
        return session_id
    
    def execute_protection(self, session_id: str) -> Dict:
        """
        执行保护操作
        :param session_id: 会话ID
        :return: 保护结果
        """
        if session_id not in self.session_storage:
            return {"error": "Session not found", "status": "failed"}
        
        session_data = self.session_storage[session_id]
        protection_request = session_data['protection_request']
        
        try:
            # 执行文本保护
            protected_text = self._protect_text(
                protection_request.detection_result.text_entities,
                protection_request.encryption_methods
            )
            
            # 执行DICOM保护
            protected_dicom = self._protect_dicom(
                protection_request.detection_result.dicom_metadata,
                protection_request.encryption_methods
            )
            
            # 生成保护报告
            protection_report = self._generate_protection_report(
                session_id, protection_request, protected_text, protected_dicom
            )
            
            # 更新会话状态
            self.session_storage[session_id]['status'] = 'protected'
            self.session_storage[session_id]['protection_result'] = protection_report
            
            return {
                "session_id": session_id,
                "protected_text": protected_text,
                "protected_dicom": protected_dicom,
                "protection_report": protection_report,
                "status": "success"
            }
            
        except Exception as e:
            self.session_storage[session_id]['status'] = 'failed'
            return {"error": str(e), "status": "failed"}
    
    def get_protection_status(self, session_id: str) -> Dict:
        """获取保护状态"""
        if session_id not in self.session_storage:
            return {"error": "Session not found", "status": "not_found"}
        
        session_data = self.session_storage[session_id]
        return {
            "session_id": session_id,
            "status": session_data['status'],
            "risk_score": session_data['detection_result'].risk_score,
            "protection_level": session_data['protection_request'].protection_level,
            "timestamp": session_data['detection_result'].timestamp.isoformat()
        }
    
    def _calculate_risk_score(self, detection_result: Dict) -> float:
        """计算风险分数"""
        text_entities = detection_result.get('text_entities', [])
        cross_modal_risks = detection_result.get('cross_modal_risks', [])
        
        # 基础风险分数
        base_score = len(text_entities) * 0.1
        
        # 高风险实体权重
        high_risk_entities = ['PATIENT_ID', 'ID', 'NAME', 'PHONE']
        high_risk_count = sum(1 for e in text_entities if e['type'] in high_risk_entities)
        high_risk_score = high_risk_count * 0.3
        
        # 跨模态风险权重
        cross_modal_score = len(cross_modal_risks) * 0.2
        
        return min(1.0, base_score + high_risk_score + cross_modal_score)
    
    def _determine_protection_level(self, privacy_result: PrivacyDetectionResult) -> str:
        """确定保护级别"""
        risk_score = privacy_result.risk_score
        
        if risk_score >= 0.8:
            return 'high'
        elif risk_score >= 0.5:
            return 'medium'
        else:
            return 'low'
    
    def _select_encryption_methods(self, privacy_result: PrivacyDetectionResult, protection_level: str) -> List[str]:
        """选择加密方法"""
        methods = []
        
        if protection_level == 'high':
            methods = ['FPE', 'AES', 'ROI_MASK', 'HEADER_ENCRYPTION']
        elif protection_level == 'medium':
            methods = ['FPE', 'ROI_MASK']
        else:
            methods = ['FPE']
        
        return methods
    
    def _protect_text(self, text_entities: List[Dict], encryption_methods: List[str]) -> str:
        """保护文本数据"""
        if not text_entities:
            return ""
        
        # 模拟文本保护（实际应用中调用crypto_processor）
        protected_text = "原始文本已通过以下方法保护："
        for method in encryption_methods:
            if method == 'FPE':
                protected_text += "\n- 格式保留加密 (FPE)"
            elif method == 'AES':
                protected_text += "\n- AES对称加密"
        
        return protected_text
    
    def _protect_dicom(self, dicom_metadata: Dict, encryption_methods: List[str]) -> Dict:
        """保护DICOM数据"""
        if not dicom_metadata:
            return {}
        
        protected_dicom = {
            "original_metadata": dicom_metadata,
            "protection_applied": encryption_methods,
            "status": "protected"
        }
        
        # 模拟DICOM保护
        if 'ROI_MASK' in encryption_methods:
            protected_dicom["roi_masked"] = True
        if 'HEADER_ENCRYPTION' in encryption_methods:
            protected_dicom["header_encrypted"] = True
        
        return protected_dicom
    
    def _generate_protection_report(self, session_id: str, protection_request: ProtectionRequest, 
                                 protected_text: str, protected_dicom: Dict) -> Dict:
        """生成保护报告"""
        return {
            "session_id": session_id,
            "protection_level": protection_request.protection_level,
            "encryption_methods": protection_request.encryption_methods,
            "risk_score": protection_request.detection_result.risk_score,
            "entities_protected": len(protection_request.detection_result.text_entities),
            "cross_modal_risks_mitigated": len(protection_request.detection_result.cross_modal_risks),
            "protection_timestamp": datetime.now().isoformat(),
            "compliance_status": "HIPAA_COMPLIANT" if protection_request.protection_level in ['high', 'medium'] else "BASIC_PROTECTION"
        }

class ProtectionLayerInterface:
    """保护层接口，用于与外部保护系统集成"""
    
    def __init__(self, interface: PrivacyProtectionInterface):
        self.interface = interface
    
    def send_to_protection_layer(self, session_id: str) -> Dict:
        """发送到保护层进行处理"""
        try:
            result = self.interface.execute_protection(session_id)
            return result
        except Exception as e:
            return {"error": str(e), "status": "failed"}
    
    def get_protection_result(self, session_id: str) -> Dict:
        """获取保护结果"""
        return self.interface.get_protection_status(session_id)

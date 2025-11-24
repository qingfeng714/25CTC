import re
import csv
import pandas as pd
from typing import Dict, List, Optional, Tuple
from pathlib import Path

class NERService:
    def __init__(self):
        """初始化正则表达式规则（匹配中文医疗文本中的敏感实体）"""
        self.patterns = {
            "NAME": r"([\u4e00-\u9fa5]{2,4})",  # 中文姓名（2-4个汉字）
            "ID": r"(\d{17}[\dXx]|\d{15})",  # 身份证号（15或18位）
            "PHONE": r"(1[3-9]\d{9})",  # 手机号（11位，以1开头）
            # AGE模式：只匹配明确的年龄表达，避免误匹配其他数字
            "AGE": r"(?:年龄|age|Age|AGE)[:：\s]*(\d{1,3})[岁年]?|\b(\d{1,2})[岁年]\b",  # 年龄（只匹配"年龄:XX"或"XX岁"格式）
            "DATE": r"(\d{4}[年\-/]\d{1,2}[月\-/]\d{1,2}日?)",  # 日期
            "ADDRESS": r"([\u4e00-\u9fa5]+(省|市|区|县|街道|路|号|村|镇))",  # 地址
            # 移除过于宽泛的PATIENT_ID和ACCESSION模式，改为在CSV处理时根据列名判断
            "INSTITUTION": r"([\u4e00-\u9fa5]+(医院|中心|诊所|卫生院))",  # 机构名称
            "SEX": r"\b(Male|Female|M|F|男|女|男性|女性)\b",  # 性别
        }
        
        # 英文模式（用于处理英文医疗文本）
        self.english_patterns = {
            "NAME": r"[A-Z][a-z]+ [A-Z][a-z]+",  # 英文姓名
            "PHONE": r"\d{11}",  # 11位电话号码
            "ID_NUMBER": r"\d{17}[\dXx]",  # 18位身份证号
            "ADDRESS": r".+?(路|街|座|县|市|区|省)",  # 地址
        }

    def detect_from_text(self, text: str, use_english: bool = False) -> List[Dict]:
        """
        从单条文本中提取敏感实体
        :param text: 输入文本（如 "患者张三，电话13800138000"）
        :param use_english: 是否使用英文模式
        :return: [{"type": "NAME", "text": "张三", "start": 2, "end": 4, "confidence": 0.95}, ...]
        """
        entities = []
        patterns = self.english_patterns if use_english else self.patterns
        
        for entity_type, pattern in patterns.items():
            for match in re.finditer(pattern, text):
                if use_english:
                    # 英文模式直接匹配整个文本
                    start, end = match.start(), match.end()
                    text_content = match.group()
                else:
                    # 中文模式使用第一个分组
                    start, end = match.start(1), match.end(1)
                    text_content = match.group(1)
                
                # 特殊处理AGE类型：验证年龄值是否合理（0-150岁）
                if entity_type == "AGE":
                    # 从匹配中提取数字（可能是第1或第2个分组）
                    age_value = None
                    for i in range(1, min(3, len(match.groups()) + 1)):
                        if match.group(i):
                            try:
                                age_value = int(match.group(i))
                                break
                            except (ValueError, IndexError):
                                continue
                    
                    # 如果没有从分组中提取到数字，尝试从text_content中提取
                    if age_value is None:
                        # 尝试从text_content中提取数字
                        num_match = re.search(r'\d+', text_content)
                        if num_match:
                            try:
                                age_value = int(num_match.group())
                            except ValueError:
                                pass
                    
                    # 验证年龄值是否合理（0-150岁）
                    if age_value is None or age_value < 0 or age_value > 150:
                        continue  # 跳过不合理的年龄值
                    
                    # 使用合理的年龄值作为text
                    text_content = str(age_value)
                    # 更新start和end位置
                    if age_value is not None:
                        num_match = re.search(r'\b' + str(age_value) + r'\b', text[start:end] if start < len(text) else text)
                        if num_match:
                            start = start + num_match.start()
                            end = start + len(str(age_value))
                
                entities.append({
                    "type": entity_type,
                    "text": text_content,
                    "start": start,
                    "end": end,
                    "confidence": self._calc_confidence(entity_type, text_content)
                })
        
        return entities

    def detect_from_dataframe(self, df: pd.DataFrame, text_column: str = "text") -> pd.DataFrame:
        """
        从DataFrame中批量检测敏感实体
        :param df: 输入DataFrame（必须包含文本列）
        :param text_column: 文本列的列名（默认"text"）
        :return: 新增了"entities"列的DataFrame（每行存储该文本的实体列表）
        """
        df["entities"] = df[text_column].apply(self.detect_from_text)
        return df

    def anonymize_text(self, text: str, entities: List[Dict]) -> str:
        """
        匿名化文本（用占位符替换敏感实体）
        :param text: 原始文本
        :param entities: detect_from_text()返回的实体列表
        :return: 匿名化后的文本（如 "患者[NAME]，电话[PHONE]"）
        """
        # 按起始位置逆序处理，避免影响后续位置
        for entity in sorted(entities, key=lambda x: -x["start"]):
            text = text[:entity["start"]] + f"[{entity['type']}]" + text[entity["end"]:]
        return text

    def _calc_confidence(self, entity_type: str, text: str) -> float:
        """计算实体识别置信度（可自定义规则）"""
        base_conf = {
            "NAME": 0.95,
            "ID": 0.99,
            "PHONE": 0.97,
            "AGE": 0.90,
            "DATE": 0.93,
            "ADDRESS": 0.85,
            "PATIENT_ID": 0.98,
            "ACCESSION": 0.96,
            "INSTITUTION": 0.88,
        }
        return base_conf.get(entity_type, 0.8) * min(1.0, 0.9 + 0.1 * len(text) / 10)  # 长度越长置信度越高
    
    def process_csv(self, input_path: str, output_path: str, columns: Optional[List[str]] = None) -> bool:
        """
        处理CSV文件，检测并标记敏感实体
        :param input_path: 输入CSV文件路径
        :param output_path: 输出CSV文件路径
        :param columns: 指定需要处理的列名（默认自动检测）
        :return: 处理是否成功
        """
        try:
            # 读取CSV文件
            df = pd.read_csv(input_path, encoding='utf-8', encoding_errors='ignore')
            
            # 如果没有指定列，自动检测文本列
            if columns is None:
                text_columns = []
                for col in df.columns:
                    if df[col].dtype == 'object':  # 文本列
                        # 检查是否包含中文或英文文本
                        sample_text = str(df[col].iloc[0]) if len(df) > 0 else ""
                        if any('\u4e00' <= char <= '\u9fff' for char in sample_text) or \
                           any(char.isalpha() for char in sample_text):
                            text_columns.append(col)
                columns = text_columns
            
            print(f"处理列: {columns}")
            
            # 为每行添加实体检测结果
            df['detected_entities'] = ""
            df['anonymized_text'] = ""
            
            for idx, row in df.iterrows():
                all_entities = []
                anonymized_row = row.copy()
                
                for col in columns:
                    if col in df.columns:
                        text = str(row[col])
                        entities = self.detect_from_text(text)
                        all_entities.extend(entities)
                        
                        # 匿名化文本
                        anonymized_text = self.anonymize_text(text, entities)
                        anonymized_row[col] = anonymized_text
                
                # 保存结果
                df.at[idx, 'detected_entities'] = str(all_entities)
                for col in columns:
                    if col in df.columns:
                        df.at[idx, col] = anonymized_row[col]
            
            # 保存处理后的CSV
            df.to_csv(output_path, index=False, encoding='utf-8')
            print(f"处理完成！已保存到 {output_path}")
            return True
            
        except Exception as e:
            print(f"处理CSV时出错: {e}")
            return False
    
    def detect_pii(self, text: str) -> Dict[str, List[str]]:
        """检测文本中的 PII（个人身份信息）"""
        detected_pii = {}
        for pii_type, pattern in self.patterns.items():
            matches = re.findall(pattern, text)
            if matches:
                detected_pii[pii_type] = matches
        return detected_pii

class ClinicalNER:
    """临床NER服务，专门用于医疗文本"""
    def __init__(self):
        self.ner_service = NERService()
    
    def detect(self, text: str) -> List[Dict]:
        """检测临床文本中的敏感实体"""
        return self.ner_service.detect_from_text(text)

# 示例用法
if __name__ == "__main__":
    ner_service = NERService()
    ner_service.process_csv(
        input_csv="train_with_sensitive_info.csv",
        output_csv="anonymized_train.csv"
    )
from enum import Enum
import json

class ProtectionLevel(Enum):
    MASK = 1
    FPE = 2
    ENCRYPT = 3
    ERASE = 4

class PolicyEngine:
    def __init__(self, config_path: str):
        with open(config_path) as f:
            self.rules = json.load(f)
        
    def decide_protection(self, phi_entities: list) -> dict:
        """根据敏感级别生成保护策略"""
        decisions = {}
        for entity in phi_entities:
            ent_type = entity['entity']
            level = self.rules.get(ent_type, 'ENCRYPT')
            
            if level == 'MASK':
                decisions[entity['id']] = {'action': 'MASK', 'params': {}}
            elif level == 'FPE':
                decisions[entity['id']] = {
                    'action': 'FPE',
                    'params': {'type': ent_type}
                }
            # 其他规则...
        
        return decisions
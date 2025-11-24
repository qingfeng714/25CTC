#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试新的工作流
"""
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_imports():
    """测试导入"""
    print("=" * 50)
    print("Testing Module Imports...")
    print("=" * 50)
    
    try:
        from services.crossmodal_service import CrossModalAttentionService
        print("[OK] CrossModalAttentionService imported successfully")
    except Exception as e:
        print(f"[ERROR] CrossModalAttentionService import failed: {e}")
        return False
    
    try:
        from services.ner_service import NERService
        print("[OK] NERService imported successfully")
    except Exception as e:
        print(f"[ERROR] NERService import failed: {e}")
        return False
    
    try:
        from services.roi_service import DicomProcessor
        print("[OK] DicomProcessor imported successfully")
    except Exception as e:
        print(f"[ERROR] DicomProcessor import failed: {e}")
        return False
    
    return True

def test_ner_service():
    """测试NER服务"""
    print("\n" + "=" * 50)
    print("测试NER服务（PHI提取）...")
    print("=" * 50)
    
    try:
        from services.ner_service import NERService
        ner = NERService()
        
        # 测试文本
        test_text = "患者张三，身份证号110101199001011234，电话13800138000，年龄35岁，男性"
        entities = ner.detect_from_text(test_text)
        
        print(f"测试文本: {test_text}")
        print(f"提取到的实体数量: {len(entities)}")
        for entity in entities:
            print(f"  - {entity['type']}: {entity['text']} (置信度: {entity['confidence']:.2f})")
        
        return len(entities) > 0
    except Exception as e:
        print(f"[ERROR] NER service test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_process_files_folder_structure():
    """测试process_files_folder方法的结构"""
    print("\n" + "=" * 50)
    print("测试process_files_folder方法...")
    print("=" * 50)
    
    try:
        from services.crossmodal_service import CrossModalAttentionService
        import torch
        
        service = CrossModalAttentionService(device='cpu')
        
        # 检查方法是否存在
        if hasattr(service, 'process_files_folder'):
            print("[OK] process_files_folder method exists")
            
            # 检查方法签名
            import inspect
            sig = inspect.signature(service.process_files_folder)
            params = list(sig.parameters.keys())
            print(f"  Method parameters: {params}")
            
            if 'csv_path' in params and 'files_root' in params and 'output_path' in params:
                print("[OK] Method parameters are correct")
                return True
            else:
                print("[ERROR] Method parameters are incorrect")
                return False
        else:
            print("[ERROR] process_files_folder method does not exist")
            return False
    except Exception as e:
        print(f"[ERROR] Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """主测试函数"""
    print("\n" + "=" * 50)
    print("New Workflow Test")
    print("=" * 50 + "\n")
    
    results = []
    
    # Test 1: Imports
    results.append(("Module Imports", test_imports()))
    
    # Test 2: NER Service
    results.append(("NER Service", test_ner_service()))
    
    # Test 3: process_files_folder Method
    results.append(("process_files_folder Method", test_process_files_folder_structure()))
    
    # Summary
    print("\n" + "=" * 50)
    print("Test Results Summary")
    print("=" * 50)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "[PASS]" if result else "[FAIL]"
        print(f"{name}: {status}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n[SUCCESS] All tests passed! Code is ready to run.")
        return 0
    else:
        print("\n[ERROR] Some tests failed, please check the code.")
        return 1

if __name__ == "__main__":
    sys.exit(main())


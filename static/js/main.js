// 全局变量
let currentDetectionId = null;
let currentArtifactId = null;

// 初始化Cornerstone
function initializeCornerstone() {
    // 检查是否已加载Cornerstone库
    if (typeof cornerstone === 'undefined' || typeof cornerstoneWADOImageLoader === 'undefined') {
        console.warn('Cornerstone库未加载，DICOM预览功能将受限');
        return;
    }
    
    cornerstoneWADOImageLoader.external.cornerstone = cornerstone;
    cornerstoneWADOImageLoader.webWorkerManager.initialize({
        maxWebWorkers: 4,
        startWebWorkersOnDemand: true,
        webWorkerTaskPaths: []
    });
}

// 高亮显示PHI实体
function highlightPHIEntities(text, entities) {
    if (!text || !entities || entities.length === 0) return text;
    
    let highlightedText = text;
    // 按起始位置降序排序，避免替换影响后续位置
    const sortedEntities = [...entities].sort((a, b) => b.start_pos - a.start_pos);
    
    sortedEntities.forEach(entity => {
        const originalText = entity.text;
        const category = entity.category.toLowerCase();
        const confidence = (entity.confidence * 100).toFixed(1);
        
        const highlighted = `<span class="phi-highlight phi-${category}" 
            title="${entity.category} (置信度: ${confidence}%)"
            data-entity-id="${entity.entity_id}">
            ${originalText}
        </span>`;
        
        highlightedText = highlightedText.substring(0, entity.start_pos) + 
                         highlighted + 
                         highlightedText.substring(entity.end_pos);
    });
    
    return highlightedText;
}

// 显示ROI区域
function displayROIRegions(regions) {
    const overlay = document.getElementById('roiOverlay');
    if (!overlay) return;
    
    overlay.innerHTML = '';
    
    regions.forEach(region => {
        const roiElement = document.createElement('div');
        roiElement.className = 'roi-overlay';
        roiElement.style.left = `${region.coordinates.x}px`;
        roiElement.style.top = `${region.coordinates.y}px`;
        roiElement.style.width = `${region.coordinates.width}px`;
        roiElement.style.height = `${region.coordinates.height}px`;
        roiElement.title = region.description;
        roiElement.dataset.regionId = region.region_id;
        
        overlay.appendChild(roiElement);
    });
}

// 处理文件上传
document.getElementById('uploadForm')?.addEventListener('submit', async function(e) {
    e.preventDefault();
    
    const formData = new FormData();
    const dicomFile = document.getElementById('dicomFile').files[0];
    const diagnosisText = document.getElementById('diagnosisText').value;
    
    if (!dicomFile && !diagnosisText.trim()) {
        alert('请至少提供DICOM文件或诊断文本');
        return;
    }
    
    if (dicomFile) {
        formData.append('dicom', dicomFile);
    }
    formData.append('text', diagnosisText);
    
    const uploadBtn = document.getElementById('uploadBtn');
    const uploadText = document.getElementById('uploadText');
    const uploadSpinner = document.getElementById('uploadSpinner');
    
    // 显示加载状态
    uploadBtn.disabled = true;
    uploadText.textContent = '处理中...';
    uploadSpinner.style.display = 'inline-block';
    
    try {
        const response = await fetch('/api/ingest', {
            method: 'POST',
            body: formData
        });
        
        const result = await response.json();
        
        if (result.status === 'ok') {
            // 跳转到结果页面
            window.location.href = `/results/${result.ingest_id}`;
        } else {
            throw new Error(result.error || '上传处理失败');
        }
    } catch (error) {
        console.error('上传失败:', error);
        alert(`上传失败: ${error.message}`);
    } finally {
        // 恢复按钮状态
        if (uploadBtn) {
            uploadBtn.disabled = false;
            uploadText.textContent = '上传并检测敏感信息';
            uploadSpinner.style.display = 'none';
        }
    }
});

// 执行数据保护
document.getElementById('protectBtn')?.addEventListener('click', async function() {
    const protectBtn = document.getElementById('protectBtn');
    protectBtn.disabled = true;
    protectBtn.textContent = '保护处理中...';
    
    const ingestId = document.getElementById('ingestId')?.value;
    if (!ingestId) {
        alert('无法获取当前检测ID');
        return;
    }
    
    try {
        const response = await fetch('/api/protect', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                ingest_id: ingestId,
                policy: {
                    encryption_level: 'high',
                    preserve_roi: true,
                    fpe_enabled: true
                }
            })
        });
        
        const result = await response.json();
        
        if (result.artifact_id) {
            currentArtifactId = result.artifact_id;
            displayProtectionResults(result);
        } else {
            throw new Error(result.error || '数据保护失败');
        }
    } catch (error) {
        console.error('保护失败:', error);
        alert(`保护失败: ${error.message}`);
    } finally {
        if (protectBtn) {
            protectBtn.disabled = false;
            protectBtn.textContent = '执行数据保护';
        }
    }
});

// 显示保护结果
function displayProtectionResults(result) {
    const protectionSection = document.getElementById('protectionResults');
    if (!protectionSection) return;
    
    // 更新文本内容
    const protectedTextDisplay = document.getElementById('protectedTextDisplay');
    if (protectedTextDisplay) {
        protectedTextDisplay.innerHTML = result.protected_text || '无保护后文本';
    }
    
    // 更新审计信息
    document.getElementById('keyId').textContent = result.key_id || 'N/A';
    document.getElementById('signatureHash').textContent = result.signature_hash || 'N/A';
    
    // 显示保护后的影像（模拟）
    const protectedCanvas = document.getElementById('protectedCanvas');
    if (protectedCanvas) {
        const ctx = protectedCanvas.getContext('2d');
        ctx.fillStyle = '#2c3e50';
        ctx.fillRect(0, 0, protectedCanvas.width, protectedCanvas.height);
        
        // 模拟ROI保留区域
        ctx.fillStyle = '#34495e';
        ctx.fillRect(100, 100, 200, 150);
        
        ctx.fillStyle = '#e74c3c';
        ctx.font = '16px Arial';
        ctx.fillText('受保护影像 (ROI区域保留)', 20, 30);
    }
    
    // 显示保护结果区域
    protectionSection.style.display = 'block';
    protectionSection.scrollIntoView({ behavior: 'smooth' });
}

// 结果页面初始化
if (document.getElementById('ingestId')) {
    const ingestId = document.getElementById('ingestId').value;
    fetchInitialResults(ingestId);
}

// 获取初始结果
async function fetchInitialResults(ingestId) {
    try {
        // 在实际应用中，这里应该调用API获取真实数据
        // 这里我们使用模拟数据演示
        
        // 模拟PHI检测结果
        const mockEntities = [
            {
                entity_id: 'entity_' + Math.random().toString(36).substr(2, 8),
                text: '张明',
                category: '姓名',
                start_pos: 3,
                end_pos: 5,
                confidence: 0.95
            },
            {
                entity_id: 'entity_' + Math.random().toString(36).substr(2, 8),
                text: '35岁',
                category: '年龄',
                start_pos: 6,
                end_pos: 9,
                confidence: 0.89
            },
            {
                entity_id: 'entity_' + Math.random().toString(36).substr(2, 8),
                text: '2023-10-15',
                category: '日期',
                start_pos: 12,
                end_pos: 22,
                confidence: 0.92
            }
        ];
        
        // 模拟原始文本
        const mockText = "患者张明，35岁，就诊日期2023-10-15。CT检查显示肺部有阴影。";
        
        // 高亮显示PHI实体
        const phiTextDisplay = document.getElementById('phiTextDisplay');
        if (phiTextDisplay) {
            phiTextDisplay.innerHTML = highlightPHIEntities(mockText, mockEntities);
        }
        
        // 显示DICOM图像（模拟）
        const canvas = document.getElementById('cornerstoneCanvas');
        if (canvas) {
            const ctx = canvas.getContext('2d');
            ctx.fillStyle = '#2c3e50';
            ctx.fillRect(0, 0, canvas.width, canvas.height);
            
            // 创建模拟的医学影像效果
            ctx.fillStyle = '#34495e';
            for (let i = 0; i < 15; i++) {
                ctx.beginPath();
                ctx.arc(
                    Math.random() * canvas.width,
                    Math.random() * canvas.height,
                    Math.random() * 30 + 10,
                    0,
                    2 * Math.PI
                );
                ctx.fill();
            }
            
            // 添加文字标注
            ctx.fillStyle = '#e74c3c';
            ctx.font = '16px Arial';
            ctx.fillText('DICOM影像预览', 20, 30);
            ctx.fillText(`检测ID: ${ingestId}`, 20, 60);
            
            // 模拟ROI区域
            ctx.strokeStyle = '#e74c3c';
            ctx.lineWidth = 2;
            ctx.strokeRect(150, 120, 100, 80);
            ctx.fillStyle = 'rgba(231, 76, 60, 0.2)';
            ctx.fillRect(150, 120, 100, 80);
            ctx.fillStyle = '#e74c3c';
            ctx.font = '12px Arial';
            ctx.fillText('病灶区域', 160, 140);
        }
        
    } catch (error) {
        console.error('初始化结果失败:', error);
    }
}

// 下载保护文件
document.getElementById('downloadBtn')?.addEventListener('click', function() {
    if (!currentArtifactId) {
        alert('无可下载的保护文件');
        return;
    }
    alert(`模拟下载保护文件，ID: ${currentArtifactId}`);
});

// 初始化Cornerstone
document.addEventListener('DOMContentLoaded', function() {
    initializeCornerstone();
});
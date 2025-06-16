# utils.py - 유용한 도우미 함수들을 모아놓은 파일입니다
# Phase 2: 잉크량 계산과 이미지 분석을 위한 함수들이 추가되었습니다

"""
utils.py - 유틸리티 함수 모음
"""

import numpy as np
from datetime import datetime
from pathlib import Path

def points_to_mm(points):
    """
    포인트를 밀리미터로 변환하는 함수
    PDF는 포인트 단위를 사용하지만, 우리는 mm가 더 익숙합니다
    
    1 포인트 = 0.352778 밀리미터
    
    Args:
        points: 포인트 단위의 값
        
    Returns:
        float: 밀리미터 단위의 값
    """
    return points * 0.352778

def mm_to_points(mm):
    """밀리미터를 포인트로 변환"""
    return mm / 0.352778

def format_size_mm(width_pt, height_pt):
    """
    페이지 크기를 보기 좋은 mm 형식으로 변환
    예: "210.0 × 297.0 mm"
    """
    width_mm = points_to_mm(width_pt)
    height_mm = points_to_mm(height_pt)
    return f"{width_mm:.1f} × {height_mm:.1f} mm"

def safe_str(value):
    """
    어떤 값이든 안전하게 문자열로 변환
    None이나 오류가 발생해도 빈 문자열 반환
    """
    try:
        return str(value) if value is not None else ""
    except:
        return ""

def safe_integer(value):
    """
    값을 안전하게 정수로 변환
    Phase 2에서 추가된 타입 안전성 함수
    """
    try:
        if isinstance(value, (int, float)):
            return int(value)
        if isinstance(value, str) and value.strip():
            return int(float(value))
    except (ValueError, TypeError):
        pass
    return 0

def safe_float(value):
    """
    값을 안전하게 실수로 변환
    Phase 2에서 추가된 타입 안전성 함수
    """
    try:
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str) and value.strip():
            return float(value)
    except (ValueError, TypeError):
        pass
    return 0.0

def safe_div(dividend, divisor):
    """
    0으로 나누기 방지
    Phase 2에서 추가된 안전한 나눗셈 함수
    """
    divisor_num = safe_float(divisor)
    if divisor_num != 0:
        return safe_float(dividend) / divisor_num
    return 0.0

def create_report_filename(pdf_filename, report_type='text'):
    """
    PDF 파일명으로부터 보고서 파일명 생성
    
    Args:
        pdf_filename: 원본 PDF 파일명
        report_type: 'text' 또는 'html'
    
    예: "sample.pdf" → "sample_report.txt" 또는 "sample_report.html"
    """
    path = Path(pdf_filename)
    extension = '.txt' if report_type == 'text' else '.html'
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    return f"{path.stem}_report_{timestamp}{extension}"

def is_font_embedded(font_obj):
    """
    폰트가 임베딩되었는지 더 정확하게 확인하는 함수
    
    여러 가지 방법으로 폰트 임베딩을 확인합니다:
    1. BaseFont 이름에 + 기호 (서브셋)
    2. FontDescriptor의 FontFile 존재
    3. Type0 폰트의 특수 처리
    4. TrueType 폰트의 특수 처리
    """
    try:
        # 1. BaseFont 확인
        if hasattr(font_obj, 'BaseFont'):
            base_font = str(font_obj.BaseFont)
            if '+' in base_font:
                return True  # 서브셋 폰트는 거의 항상 임베딩됨
        
        # 2. FontDescriptor 확인
        if '/FontDescriptor' in font_obj:
            descriptor = font_obj.FontDescriptor
            
            # FontFile 시리즈 확인
            if any(key in descriptor for key in ['/FontFile', '/FontFile2', '/FontFile3']):
                return True
            
            # FontName과 BaseFont 비교
            if '/FontName' in descriptor and hasattr(font_obj, 'BaseFont'):
                # 이름이 일치하면 보통 임베딩됨
                return True
        
        # 3. Type0 (CID) 폰트 확인
        if hasattr(font_obj, 'Subtype') and str(font_obj.Subtype) == '/Type0':
            # CID 폰트는 대부분 임베딩됨
            return True
        
        # 4. 특정 폰트 타입 확인
        if hasattr(font_obj, 'Subtype'):
            subtype = str(font_obj.Subtype)
            if subtype in ['/TrueType', '/CIDFontType0', '/CIDFontType2']:
                # 이런 타입들은 보통 임베딩됨
                return True
                
    except Exception:
        pass
    
    return False

def format_file_size(size_bytes):
    """
    파일 크기를 읽기 쉬운 형식으로 변환
    Phase 2에서 추가된 함수
    
    예: 1234567 → "1.2 MB"
    """
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"

def calculate_coverage_percentage(cmyk_values):
    """
    CMYK 값에서 잉크 커버리지 퍼센트를 계산
    Phase 2 잉크량 계산을 위한 함수
    
    Args:
        cmyk_values: (C, M, Y, K) 튜플 (0-255 범위)
        
    Returns:
        float: 총 잉크량 퍼센트 (0-400%)
    """
    # 각 채널을 0-100% 범위로 변환하고 합산
    c, m, y, k = cmyk_values
    total = (c + m + y + k) / 255.0 * 100
    return min(total, 400.0)  # 최대 400%

def rgb_to_cmyk(r, g, b):
    """
    RGB를 CMYK로 변환
    Phase 2에서 색상 분석을 위해 추가
    
    Args:
        r, g, b: RGB 값 (0-255)
        
    Returns:
        tuple: (C, M, Y, K) 값 (0-255)
    """
    # RGB를 0-1 범위로 정규화
    r, g, b = r/255.0, g/255.0, b/255.0
    
    # K (검정) 계산
    k = 1 - max(r, g, b)
    
    # K가 1이면 순수 검정색
    if k == 1:
        return (0, 0, 0, 255)
    
    # CMY 계산
    c = (1 - r - k) / (1 - k)
    m = (1 - g - k) / (1 - k)
    y = (1 - b - k) / (1 - k)
    
    # 0-255 범위로 변환
    return (
        int(c * 255),
        int(m * 255),
        int(y * 255),
        int(k * 255)
    )

def get_severity_color(severity):
    """
    심각도에 따른 색상 코드 반환
    HTML 보고서에서 사용
    
    Args:
        severity: 'error', 'warning', 'info', 'success'
        
    Returns:
        str: 색상 코드
    """
    colors = {
        'error': '#e74c3c',
        'warning': '#f39c12',
        'info': '#3498db',
        'success': '#27ae60'
    }
    return colors.get(severity, '#95a5a6')

def format_datetime(dt=None):
    """
    날짜/시간을 보기 좋은 형식으로 변환
    
    Args:
        dt: datetime 객체 (None이면 현재 시간)
        
    Returns:
        str: "2024년 1월 15일 14:30:25" 형식
    """
    if dt is None:
        dt = datetime.now()
    return dt.strftime('%Y년 %m월 %d일 %H:%M:%S')

def truncate_text(text, max_length=50):
    """
    긴 텍스트를 적절히 자르고 ... 추가
    
    Args:
        text: 원본 텍스트
        max_length: 최대 길이
        
    Returns:
        str: 잘린 텍스트
    """
    text = str(text)
    if len(text) <= max_length:
        return text
    return text[:max_length-3] + '...'

def calculate_ink_coverage_stats(coverage_map):
    """
    잉크 커버리지 맵에서 통계 정보 계산
    
    Args:
        coverage_map: numpy array of coverage percentages
        
    Returns:
        dict: 통계 정보 (평균, 최대, 초과 영역 등)
    """
    return {
        'average': float(np.mean(coverage_map)),
        'max': float(np.max(coverage_map)),
        'over_280': float(np.sum(coverage_map > 280) / coverage_map.size * 100),
        'over_300': float(np.sum(coverage_map > 300) / coverage_map.size * 100),
        'over_320': float(np.sum(coverage_map > 320) / coverage_map.size * 100)
    }
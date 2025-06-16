# config.py - 프로그램 설정을 관리하는 파일입니다
# Phase 2.5: 고급 인쇄 검사 설정이 추가되었습니다
# 자동 수정 옵션 확장
# 2024.12 수정: 투명도 검사 기본값 OFF로 변경
# 2025.01 수정: 이미지 해상도 기준 완화 (72 DPI 기준)
# 2025.06 수정: 잉크량 검사 기본 OFF, 오버프린트 세부 설정 추가

"""
config.py - 프로그램 전체 설정 관리
"""

from pathlib import Path

class Config:
    """프로그램 설정을 한 곳에서 관리하는 클래스"""
    
    # === 폴더 이름 설정 (나중에 한국어로 변경 가능) ===
    INPUT_FOLDER = "input"      # TODO: 나중에 "입력"으로 변경
    OUTPUT_FOLDER = "output"    # TODO: 나중에 "완료"로 변경
    REPORTS_FOLDER = "reports"  # TODO: 나중에 "보고서"로 변경
    TEMPLATES_FOLDER = "templates"  # HTML 템플릿 폴더
    PROFILES_FOLDER = "profiles"    # 프리플라이트 프로파일 폴더
    
    # === 프로젝트 경로 설정 ===
    # 현재 파일이 있는 폴더를 기준으로 경로 설정
    BASE_DIR = Path(__file__).parent
    INPUT_PATH = BASE_DIR / INPUT_FOLDER
    OUTPUT_PATH = BASE_DIR / OUTPUT_FOLDER
    REPORTS_PATH = BASE_DIR / REPORTS_FOLDER
    TEMPLATES_PATH = BASE_DIR / TEMPLATES_FOLDER
    PROFILES_PATH = BASE_DIR / PROFILES_FOLDER
    
    # === PDF 검수 기준값 설정 ===
    # 잉크량 검사 기준 (단위: %)
    MAX_INK_COVERAGE = 300      # 최대 허용 잉크량 (인쇄 표준)
    WARNING_INK_COVERAGE = 280  # 경고 수준 잉크량
    CRITICAL_INK_COVERAGE = 320 # 심각한 수준 (인쇄 불가능)
    
    # 페이지 크기 허용 오차 (단위: mm)
    PAGE_SIZE_TOLERANCE = 2.0   # 2mm까지는 같은 크기로 간주
    
    # === 이미지 해상도 기준 (2025.01 수정: 기준 완화) ===
    # 이미지 해상도 기준값을 대폭 완화하여 오탐지 방지
    MIN_IMAGE_DPI = 72          # 인쇄용 최소 해상도 (웹용 수준)
    WARNING_IMAGE_DPI = 150     # 경고 수준 해상도 (일반 인쇄 최소)
    OPTIMAL_IMAGE_DPI = 300     # 권장 해상도 (고품질 인쇄)
    
    # 해상도별 설명 (보고서에 사용)
    DPI_DESCRIPTIONS = {
        'critical': '72 DPI 미만 - 인쇄 품질 심각',
        'warning': '72-150 DPI - 일반 문서용으로는 가능',
        'acceptable': '150-300 DPI - 대부분의 인쇄에 적합',
        'optimal': '300 DPI 이상 - 고품질 인쇄 가능'
    }
    
    # === Phase 2.5 추가 설정 ===
    # 재단선 여백 기준 (단위: mm)
    STANDARD_BLEED_SIZE = 3.0   # 표준 재단 여백
    LARGE_FORMAT_BLEED = 10.0   # 대형 인쇄용 재단 여백
    
    # 텍스트 크기 기준 (단위: pt)
    MIN_TEXT_SIZE = 4.0         # 최소 텍스트 크기
    WARNING_TEXT_SIZE = 5.0     # 경고 텍스트 크기
    
    # 투명도 처리
    FLATTEN_TRANSPARENCY = True  # 투명도 평탄화 권장
    
    # 프리플라이트 프로파일
    DEFAULT_PREFLIGHT_PROFILE = 'offset'  # 기본 프로파일
    AVAILABLE_PROFILES = [
        'offset',       # 옵셋 인쇄
        'digital',      # 디지털 인쇄
        'newspaper',    # 신문 인쇄
        'large_format', # 대형 인쇄
        'high_quality'  # 고품질 인쇄
    ]
    
    # === 보고서 설정 ===
    # 보고서 형식 ('text', 'html', 'both')
    DEFAULT_REPORT_FORMAT = 'both'  # 기본값: 텍스트와 HTML 둘 다 생성
    
    # HTML 보고서 스타일
    HTML_REPORT_STYLE = 'dashboard'  # 'business', 'dashboard', 'practical'
    
    # === 잉크량 계산 설정 (2025.06 수정: 기본 OFF) ===
    DEFAULT_INK_ANALYSIS = False  # 기본적으로 잉크량 분석 OFF (시간이 오래 걸리므로)
    INK_CALCULATION_DPI = 150    # 잉크량 계산시 사용할 해상도 (속도와 정확도 균형)
    
    # 잉크량 분석 상세 설정
    INK_ANALYSIS_OPTIONS = {
        'enabled': False,         # 기본값: OFF
        'dpi': 150,              # 계산 해상도
        'timeout': 60,           # 최대 처리 시간(초)
        'cache_results': True,   # 결과 캐싱
        'parallel': True         # 병렬 처리
    }
    
    # === 표준 용지 크기 정의 (단위: mm) ===
    STANDARD_PAPER_SIZES = {
        'A3': (297, 420),
        'A4': (210, 297),
        'A5': (148, 210),
        'B4': (257, 364),
        'B5': (182, 257),
        'Letter': (215.9, 279.4),
        'Legal': (215.9, 355.6),
        '4x6': (101.6, 152.4),
        '국배판': (636, 939),  # 한국 표준
        '46배판': (788, 1091), # 한국 표준
    }
    
    # === 인쇄 방식별 기본 설정 (2025.01 수정: 해상도 기준 조정) ===
    PRINT_METHOD_DEFAULTS = {
        'offset': {
            'max_ink': 300,
            'min_dpi': 150,  # 300에서 150으로 완화
            'bleed': 3,
            'color_mode': 'CMYK',
            'transparency': False
        },
        'digital': {
            'max_ink': 280,
            'min_dpi': 100,  # 200에서 100으로 완화
            'bleed': 2,
            'color_mode': 'RGB_OK',
            'transparency': True
        },
        'newspaper': {
            'max_ink': 240,
            'min_dpi': 72,   # 150에서 72로 완화
            'bleed': 0,
            'color_mode': 'CMYK',
            'transparency': False
        },
        'large_format': {
            'max_ink': 300,
            'min_dpi': 72,   # 100에서 72로 완화
            'bleed': 10,
            'color_mode': 'CMYK',
            'transparency': True
        }
    }
    
    # === 고급 검사 옵션 (2024.12 수정: 투명도 기본값 False) ===
    CHECK_OPTIONS = {
        'transparency': False,       # 투명도 검사 (기본값 OFF로 변경)
        'overprint': True,          # 중복인쇄 검사
        'bleed': True,              # 재단선 검사
        'spot_colors': True,        # 별색 상세 검사
        'image_compression': True,   # 이미지 압축 품질
        'minimum_text': True,       # 최소 텍스트 크기
        'ink_coverage': False       # 잉크량 검사 (2025.06 추가: 기본 OFF)
    }
    
    # === 오버프린트 세부 설정 (2025.06 추가) ===
    OVERPRINT_SETTINGS = {
        'check_white_overprint': True,      # 흰색 오버프린트 검사 (위험)
        'k_only_as_normal': True,           # K100%는 정상으로 처리
        'warn_light_colors': True,          # 라이트 컬러 경고
        'light_color_threshold': 20,        # CMYK 합계 20% 이하를 라이트로 정의
        'check_image_overprint': True,      # 이미지 오버프린트 검사
        'detailed_reporting': True          # 상세 보고 (타입별 분류)
    }
    
    # === 자동 수정 옵션 ===
    AUTO_FIX_OPTIONS = {
        # 색상 변환
        'convert_rgb_to_cmyk': False,  # RGB→CMYK 자동 변환
        'reduce_ink_coverage': False,   # 잉크량 자동 조정
        'convert_spot_to_cmyk': False,  # 별색→CMYK 변환
        
        # 폰트 처리
        'embed_fonts': False,          # 폰트 자동 임베딩
        'outline_fonts': False,        # 아웃라인 변환
        'warn_small_text': True,       # 작은 텍스트 경고
        
        # 이미지 최적화
        'upscale_low_res': False,      # 저해상도 이미지 보정
        'downscale_high_res': False,   # 고해상도 이미지 최적화
        
        # 인쇄 준비
        'flatten_transparency': False,  # 투명도 자동 평탄화
        'add_bleed_marks': False,      # 재단선 자동 추가
        
        # 백업 설정
        'always_backup': True,         # 항상 원본 백업
        'create_comparison_report': True  # 수정 전후 비교 리포트
    }
    
    # === 자동 수정 폴더 설정 ===
    BACKUP_FOLDER = "backup"          # 원본 백업 폴더
    FIXED_FOLDER = "fixed"            # 수정된 파일 폴더
    
    # === 사용자 메시지 설정 ===
    MESSAGES = {
        'welcome': "PDF 자동검수 시스템 Phase 2.5에 오신 것을 환영합니다!",
        'input_prompt': f"PDF 파일을 '{INPUT_FOLDER}' 폴더에 넣어주세요.",
        'processing': "PDF 파일을 분석하고 있습니다...",
        'ink_calculating': "잉크량을 계산하는 중입니다... (시간이 걸릴 수 있습니다)",
        'ink_analysis_skipped': "잉크량 분석을 건너뜁니다 (설정에서 활성화 가능)",
        'print_quality_checking': "고급 인쇄 품질을 검사하는 중입니다...",
        'preflight_checking': "프리플라이트 검사를 수행하는 중입니다...",
        'report_generating': "보고서를 생성하는 중입니다...",
        'complete': f"분석이 완료되었습니다. 결과는 '{REPORTS_FOLDER}' 폴더를 확인하세요.",
        'error': "오류가 발생했습니다: "
    }
    
    # === 파일 모니터링 설정 ===
    MONITOR_INTERVAL = 2  # 폴더 확인 간격 (초)
    PROCESS_DELAY = 1     # 파일 복사 완료 대기 시간 (초)
    
    @classmethod
    def create_folders(cls):
        """필요한 폴더들을 자동으로 생성하는 메서드"""
        folders = [
            cls.INPUT_PATH, 
            cls.OUTPUT_PATH, 
            cls.REPORTS_PATH,
            cls.TEMPLATES_PATH,
            cls.PROFILES_PATH,
            cls.OUTPUT_PATH / "정상",
            cls.OUTPUT_PATH / "경고", 
            cls.OUTPUT_PATH / "오류",
            cls.OUTPUT_PATH / cls.BACKUP_FOLDER,  # 백업 폴더
            cls.OUTPUT_PATH / cls.FIXED_FOLDER    # 수정된 파일 폴더
        ]
        
        for folder in folders:
            folder.mkdir(exist_ok=True, parents=True)
            print(f"✓ 폴더 확인/생성: {folder}")
    
    @classmethod
    def get_paper_size_name(cls, width_mm, height_mm, tolerance=5):
        """
        주어진 크기에 해당하는 표준 용지 이름을 찾는 메서드
        
        Args:
            width_mm: 폭 (mm)
            height_mm: 높이 (mm)
            tolerance: 허용 오차 (mm)
            
        Returns:
            str: 용지 이름 또는 'Custom'
        """
        for name, (std_width, std_height) in cls.STANDARD_PAPER_SIZES.items():
            # 가로/세로 모두 확인 (회전된 경우도 고려)
            if (abs(width_mm - std_width) <= tolerance and 
                abs(height_mm - std_height) <= tolerance):
                return name
            elif (abs(width_mm - std_height) <= tolerance and 
                  abs(height_mm - std_width) <= tolerance):
                return f"{name} (가로)"
                
        return "Custom"
    
    @classmethod
    def get_print_method_config(cls, method: str) -> dict:
        """
        인쇄 방식에 따른 기본 설정 반환
        
        Args:
            method: 인쇄 방식 ('offset', 'digital', 등)
            
        Returns:
            dict: 인쇄 방식별 설정
        """
        return cls.PRINT_METHOD_DEFAULTS.get(
            method, 
            cls.PRINT_METHOD_DEFAULTS['offset']
        )
    
    @classmethod
    def save_custom_profile(cls, profile_name: str, profile_data: dict):
        """
        커스텀 프로파일 저장
        
        Args:
            profile_name: 프로파일 이름
            profile_data: 프로파일 데이터
        """
        import json
        profile_path = cls.PROFILES_PATH / f"{profile_name}.json"
        
        with open(profile_path, 'w', encoding='utf-8') as f:
            json.dump(profile_data, f, ensure_ascii=False, indent=2)
        
        print(f"✓ 프로파일 저장: {profile_path}")
    
    @classmethod
    def load_custom_profile(cls, profile_name: str) -> dict:
        """
        커스텀 프로파일 로드
        
        Args:
            profile_name: 프로파일 이름
            
        Returns:
            dict: 프로파일 데이터
        """
        import json
        profile_path = cls.PROFILES_PATH / f"{profile_name}.json"
        
        if profile_path.exists():
            with open(profile_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        
        return None
    
    @classmethod
    def set_ink_analysis(cls, enabled: bool):
        """
        잉크량 분석 ON/OFF 설정
        
        Args:
            enabled: True=ON, False=OFF
        """
        cls.DEFAULT_INK_ANALYSIS = enabled
        cls.CHECK_OPTIONS['ink_coverage'] = enabled
        cls.INK_ANALYSIS_OPTIONS['enabled'] = enabled
        print(f"✓ 잉크량 분석: {'활성화' if enabled else '비활성화'}")
    
    @classmethod
    def is_ink_analysis_enabled(cls) -> bool:
        """
        잉크량 분석 활성화 여부 확인
        
        Returns:
            bool: 활성화 여부
        """
        return cls.CHECK_OPTIONS.get('ink_coverage', False) or cls.DEFAULT_INK_ANALYSIS
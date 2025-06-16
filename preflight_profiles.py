# preflight_profiles.py - 프리플라이트 프로파일 시스템
# Phase 2.5: 인쇄 방식별 맞춤 검사 규칙
# 2025.01 수정: 재단여백을 정보 제공용으로 변경, 이미지 해상도 기준 완화
# 2025.06 수정: 블리드 검사 중복 제거 - pdf_analyzer 결과 참조

"""
preflight_profiles.py - 인쇄 방식별 검사 프로파일
각 인쇄 방식에 맞는 검사 기준을 정의하고 적용
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Any
from config import Config

@dataclass
class PreflightRule:
    """프리플라이트 규칙 정의"""
    name: str
    check_type: str
    expected_value: Any
    severity: str  # 'error', 'warning', 'info'
    auto_fix: bool = False
    description: str = ""

class PreflightProfile:
    """프리플라이트 프로파일 클래스"""
    
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
        self.rules: List[PreflightRule] = []
        
    def add_rule(self, rule: PreflightRule):
        """규칙 추가"""
        self.rules.append(rule)
    
    def check(self, analysis_result: Dict) -> Dict:
        """
        분석 결과를 프로파일 규칙과 비교
        
        Args:
            analysis_result: PDF 분석 결과
            
        Returns:
            검사 결과 딕셔너리
        """
        results = {
            'profile': self.name,
            'passed': [],
            'failed': [],
            'warnings': [],
            'info': [],  # 2025.01 추가: 정보성 메시지
            'auto_fixable': []
        }
        
        for rule in self.rules:
            check_result = self._check_rule(rule, analysis_result)
            
            if check_result['status'] == 'pass':
                results['passed'].append(check_result)
            elif rule.severity == 'error':
                results['failed'].append(check_result)
                if rule.auto_fix:
                    results['auto_fixable'].append(check_result)
            elif rule.severity == 'warning':
                results['warnings'].append(check_result)
            elif rule.severity == 'info':  # 2025.01 추가
                results['info'].append(check_result)
        
        # 전체 상태 결정
        if results['failed']:
            results['overall_status'] = 'fail'
        elif results['warnings']:
            results['overall_status'] = 'warning'
        else:
            results['overall_status'] = 'pass'
        
        return results
    
    def _check_rule(self, rule: PreflightRule, analysis_result: Dict) -> Dict:
        """개별 규칙 검사"""
        result = {
            'rule_name': rule.name,
            'description': rule.description,
            'expected': rule.expected_value,
            'found': None,
            'status': 'pass',
            'message': ''
        }
        
        # 규칙 타입별 검사
        if rule.check_type == 'max_ink_coverage':
            ink_data = analysis_result.get('ink_coverage', {})
            if 'summary' in ink_data:
                max_ink = ink_data['summary']['max_coverage']
                result['found'] = f"{max_ink:.1f}%"
                
                if max_ink > rule.expected_value:
                    result['status'] = 'fail'
                    result['message'] = f"잉크량 {max_ink:.1f}%가 기준 {rule.expected_value}%를 초과"
        
        elif rule.check_type == 'min_resolution':
            images = analysis_result.get('images', {})
            low_res_count = images.get('low_resolution_count', 0)
            result['found'] = f"{low_res_count}개 저해상도 이미지"
            
            if low_res_count > 0:
                result['status'] = 'fail'
                result['message'] = f"{low_res_count}개 이미지가 {rule.expected_value} DPI 미만"
        
        elif rule.check_type == 'color_mode':
            colors = analysis_result.get('colors', {})
            if rule.expected_value == 'CMYK':
                if colors.get('has_rgb') and not colors.get('has_cmyk'):
                    result['status'] = 'fail'
                    result['found'] = 'RGB'
                    result['message'] = "RGB 색상 사용 (CMYK 필요)"
                else:
                    result['found'] = 'CMYK' if colors.get('has_cmyk') else 'Unknown'
        
        elif rule.check_type == 'font_embedding':
            fonts = analysis_result.get('fonts', {})
            not_embedded = sum(1 for f in fonts.values() if not f.get('embedded', False))
            result['found'] = f"{not_embedded}개 미임베딩"
            
            if not_embedded > 0:
                result['status'] = 'fail'
                result['message'] = f"{not_embedded}개 폰트가 임베딩되지 않음"
        
        elif rule.check_type == 'bleed_margin':
            # 2025.06 수정: print_quality의 bleed 결과를 사용 (중복 제거)
            print_quality = analysis_result.get('print_quality', {})
            bleed_info = print_quality.get('bleed', {})
            
            # print_quality_checker에서 이미 처리된 결과 사용
            if bleed_info:
                if not bleed_info.get('has_proper_bleed', True):
                    result['status'] = 'fail'  # severity가 info여도 status는 fail로 유지
                    result['found'] = f"재단 여백 부족"
                    pages_without = len(bleed_info.get('pages_without_bleed', []))
                    result['message'] = f"{pages_without}개 페이지에 {rule.expected_value}mm 재단 여백 부족"
                else:
                    result['found'] = f"{rule.expected_value}mm 이상"
            else:
                # print_quality 검사가 수행되지 않은 경우 pages 정보에서 직접 확인
                pages = analysis_result.get('pages', [])
                pages_without_bleed = []
                
                for page in pages:
                    if page.get('has_bleed'):
                        if page.get('min_bleed', 0) < rule.expected_value:
                            pages_without_bleed.append(page['page_number'])
                    else:
                        pages_without_bleed.append(page['page_number'])
                
                if pages_without_bleed:
                    result['status'] = 'fail'
                    result['found'] = f"재단 여백 부족"
                    result['message'] = f"{len(pages_without_bleed)}개 페이지에 {rule.expected_value}mm 재단 여백 부족"
                else:
                    result['found'] = f"{rule.expected_value}mm 이상"
        
        elif rule.check_type == 'transparency':
            print_quality = analysis_result.get('print_quality', {})
            transparency = print_quality.get('transparency', {})
            
            if transparency.get('has_transparency'):
                result['found'] = '투명도 사용'
                if not rule.expected_value:  # 투명도 불허
                    result['status'] = 'fail'
                    result['message'] = "투명도가 발견됨 (평탄화 필요)"
                else:
                    result['status'] = 'warning'
                    result['message'] = "투명도 사용 중 (확인 필요)"
            else:
                result['found'] = '투명도 없음'
        
        elif rule.check_type == 'spot_colors':
            colors = analysis_result.get('colors', {})
            spot_count = len(colors.get('spot_color_names', []))
            result['found'] = f"{spot_count}개"
            
            if spot_count > rule.expected_value:
                result['status'] = 'fail'
                result['message'] = f"별색 {spot_count}개가 허용치 {rule.expected_value}개 초과"
        
        elif rule.check_type == 'overprint':
            print_quality = analysis_result.get('print_quality', {})
            overprint = print_quality.get('overprint', {})
            
            # 2025.06: 문제가 되는 오버프린트만 체크
            if overprint.get('has_problematic_overprint'):
                result['found'] = '문제가 되는 중복인쇄 설정됨'
                result['status'] = 'warning'
                result['message'] = "문제가 되는 중복인쇄 설정 확인 필요"
            elif overprint.get('has_overprint'):
                result['found'] = '정상적인 중복인쇄 사용'
                # K100% 오버프린트 등 정상적인 경우는 pass
            else:
                result['found'] = '중복인쇄 없음'
        
        return result

# 사전 정의된 프로파일들
class PreflightProfiles:
    """사전 정의된 프리플라이트 프로파일 모음"""
    
    @staticmethod
    def get_offset_printing():
        """옵셋 인쇄용 프로파일 - 2025.01 수정: 재단여백과 해상도 기준 조정"""
        profile = PreflightProfile(
            name="옵셋 인쇄",
            description="일반적인 옵셋 인쇄기용 표준 설정"
        )
        
        # 필수 규칙들
        profile.add_rule(PreflightRule(
            name="최대 잉크량",
            check_type="max_ink_coverage",
            expected_value=300,
            severity="error",
            description="총 잉크량은 300%를 초과할 수 없습니다"
        ))
        
        # 이미지 해상도 기준 완화 (2025.01 수정)
        profile.add_rule(PreflightRule(
            name="최소 이미지 해상도",
            check_type="min_resolution",
            expected_value=150,  # 300에서 150으로 완화
            severity="warning",  # error에서 warning으로 완화
            description="모든 이미지는 150 DPI 이상이어야 합니다"
        ))
        
        profile.add_rule(PreflightRule(
            name="색상 모드",
            check_type="color_mode",
            expected_value="CMYK",
            severity="error",
            auto_fix=True,
            description="CMYK 색상 모드 필수"
        ))
        
        profile.add_rule(PreflightRule(
            name="폰트 임베딩",
            check_type="font_embedding",
            expected_value=True,
            severity="error",
            auto_fix=True,
            description="모든 폰트는 임베딩되어야 합니다"
        ))
        
        # 재단 여백을 정보 제공용으로 변경 (2025.01 수정)
        profile.add_rule(PreflightRule(
            name="재단 여백",
            check_type="bleed_margin",
            expected_value=3,
            severity="info",  # error에서 info로 변경
            description="최소 3mm의 재단 여백 권장"
        ))
        
        # 권장 규칙들
        profile.add_rule(PreflightRule(
            name="투명도",
            check_type="transparency",
            expected_value=False,
            severity="warning",
            description="투명도는 평탄화를 권장합니다"
        ))
        
        profile.add_rule(PreflightRule(
            name="별색 제한",
            check_type="spot_colors",
            expected_value=2,
            severity="warning",
            description="별색은 2개 이하 권장"
        ))
        
        return profile
    
    @staticmethod
    def get_digital_printing():
        """디지털 인쇄용 프로파일 - 2025.01 수정: 재단여백과 해상도 기준 조정"""
        profile = PreflightProfile(
            name="디지털 인쇄",
            description="디지털 인쇄기용 설정 (RGB 허용)"
        )
        
        profile.add_rule(PreflightRule(
            name="최대 잉크량",
            check_type="max_ink_coverage",
            expected_value=280,
            severity="error",
            description="디지털 인쇄는 280% 이하 권장"
        ))
        
        # 이미지 해상도 기준 완화 (2025.01 수정)
        profile.add_rule(PreflightRule(
            name="최소 이미지 해상도",
            check_type="min_resolution",
            expected_value=100,  # 200에서 100으로 완화
            severity="warning",
            description="디지털 인쇄는 100 DPI 이상 권장"
        ))
        
        profile.add_rule(PreflightRule(
            name="폰트 임베딩",
            check_type="font_embedding",
            expected_value=True,
            severity="error",
            description="모든 폰트는 임베딩되어야 합니다"
        ))
        
        # 재단 여백을 정보 제공용으로 변경 (2025.01 수정)
        profile.add_rule(PreflightRule(
            name="재단 여백",
            check_type="bleed_margin",
            expected_value=2,
            severity="info",  # warning에서 info로 변경
            description="최소 2mm의 재단 여백 권장"
        ))
        
        return profile
    
    @staticmethod
    def get_newspaper_printing():
        """신문 인쇄용 프로파일 - 2025.01 수정: 해상도 기준 조정"""
        profile = PreflightProfile(
            name="신문 인쇄",
            description="신문 윤전기용 특수 설정"
        )
        
        profile.add_rule(PreflightRule(
            name="최대 잉크량",
            check_type="max_ink_coverage",
            expected_value=240,
            severity="error",
            description="신문 용지는 240% 이하 필수"
        ))
        
        # 이미지 해상도 기준 완화 (2025.01 수정)
        profile.add_rule(PreflightRule(
            name="최소 이미지 해상도",
            check_type="min_resolution",
            expected_value=72,  # 150에서 72로 완화
            severity="warning",
            description="신문 인쇄는 72 DPI 이상"
        ))
        
        profile.add_rule(PreflightRule(
            name="색상 모드",
            check_type="color_mode",
            expected_value="CMYK",
            severity="error",
            description="CMYK 색상 모드 필수"
        ))
        
        profile.add_rule(PreflightRule(
            name="별색 제한",
            check_type="spot_colors",
            expected_value=0,
            severity="error",
            description="신문 인쇄는 별색 사용 불가"
        ))
        
        return profile
    
    @staticmethod
    def get_large_format_printing():
        """대형 인쇄용 프로파일 - 2025.01 수정: 재단여백과 해상도 기준 조정"""
        profile = PreflightProfile(
            name="대형 인쇄",
            description="배너, 현수막 등 대형 출력용"
        )
        
        # 이미지 해상도 기준 완화 (2025.01 수정)
        profile.add_rule(PreflightRule(
            name="최소 이미지 해상도",
            check_type="min_resolution",
            expected_value=72,  # 100에서 72로 완화
            severity="warning",
            description="대형 인쇄는 72 DPI 이상 (원거리 관람)"
        ))
        
        # 재단 여백을 정보 제공용으로 변경 (2025.01 수정)
        profile.add_rule(PreflightRule(
            name="재단 여백",
            check_type="bleed_margin",
            expected_value=10,
            severity="info",  # error에서 info로 변경
            description="대형 인쇄는 10mm 재단 여백 권장"
        ))
        
        profile.add_rule(PreflightRule(
            name="폰트 임베딩",
            check_type="font_embedding",
            expected_value=True,
            severity="error",
            description="모든 폰트는 임베딩되어야 합니다"
        ))
        
        return profile
    
    @staticmethod
    def get_high_quality_printing():
        """고품질 인쇄용 프로파일 - 2025.01 수정: 해상도 기준만 유지"""
        profile = PreflightProfile(
            name="고품질 인쇄",
            description="화보집, 아트북 등 최고 품질 인쇄"
        )
        
        profile.add_rule(PreflightRule(
            name="최대 잉크량",
            check_type="max_ink_coverage",
            expected_value=320,
            severity="warning",
            description="고품질 용지는 320%까지 허용"
        ))
        
        # 고품질 인쇄는 해상도 기준 유지
        profile.add_rule(PreflightRule(
            name="최소 이미지 해상도",
            check_type="min_resolution",
            expected_value=300,  # 고품질은 300 DPI 유지
            severity="error",
            description="고품질 인쇄는 300 DPI 이상 필수"
        ))
        
        profile.add_rule(PreflightRule(
            name="색상 모드",
            check_type="color_mode",
            expected_value="CMYK",
            severity="error",
            description="CMYK 색상 모드 필수"
        ))
        
        profile.add_rule(PreflightRule(
            name="중복인쇄",
            check_type="overprint",
            expected_value=True,
            severity="info",
            description="중복인쇄 설정 확인 필요"
        ))
        
        return profile
    
    @staticmethod
    def get_all_profiles() -> Dict[str, PreflightProfile]:
        """모든 사전 정의 프로파일 반환"""
        return {
            'offset': PreflightProfiles.get_offset_printing(),
            'digital': PreflightProfiles.get_digital_printing(),
            'newspaper': PreflightProfiles.get_newspaper_printing(),
            'large_format': PreflightProfiles.get_large_format_printing(),
            'high_quality': PreflightProfiles.get_high_quality_printing()
        }
    
    @staticmethod
    def get_profile_by_name(name: str) -> Optional[PreflightProfile]:
        """이름으로 프로파일 가져오기"""
        profiles = PreflightProfiles.get_all_profiles()
        
        # 정확한 매칭
        if name in profiles:
            return profiles[name]
        
        # 부분 매칭
        name_lower = name.lower()
        for key, profile in profiles.items():
            if name_lower in key.lower() or name_lower in profile.name.lower():
                return profile
        
        return None

# 커스텀 프로파일 생성 헬퍼
def create_custom_profile(name: str, description: str, rules: List[Dict]) -> PreflightProfile:
    """
    커스텀 프로파일 생성
    
    Args:
        name: 프로파일 이름
        description: 프로파일 설명
        rules: 규칙 정의 리스트
        
    Returns:
        PreflightProfile 객체
    """
    profile = PreflightProfile(name, description)
    
    for rule_dict in rules:
        rule = PreflightRule(
            name=rule_dict['name'],
            check_type=rule_dict['check_type'],
            expected_value=rule_dict['expected_value'],
            severity=rule_dict.get('severity', 'warning'),
            auto_fix=rule_dict.get('auto_fix', False),
            description=rule_dict.get('description', '')
        )
        profile.add_rule(rule)
    
    return profile
# print_quality_checker.py - 고급 인쇄 품질 검사 엔진
# Phase 2.5: 투명도, 중복인쇄, 재단선 검사
# 2024.12 수정: 중복인쇄 감지 로직 개선 - 더 정확한 감지
# 2025.01 수정: 중복인쇄 검증 완화, 재단선은 정보 제공용으로 변경
# 2025.06 수정: 오버프린트 정밀 감지 개선, 블리드 검사 중복 제거

"""
print_quality_checker.py - 인쇄 품질을 전문적으로 검사하는 클래스
Adobe Acrobat의 프리플라이트와 유사한 고급 검사 기능
"""

import fitz  # PyMuPDF
import pikepdf
from pathlib import Path
from utils import points_to_mm, safe_float
from config import Config
import re

class PrintQualityChecker:
    """인쇄 품질을 전문적으로 검사하는 클래스"""
    
    def __init__(self):
        self.issues = []
        self.warnings = []
        
    def check_all(self, pdf_path, pages_info=None):
        """
        모든 인쇄 품질 검사를 수행
        
        Args:
            pdf_path: PDF 파일 경로
            pages_info: pdf_analyzer에서 전달받은 페이지 정보 (블리드 포함)
        """
        print("\n🔍 고급 인쇄 품질 검사 시작...")
        
        results = {
            'transparency': self.check_transparency(pdf_path) if Config.CHECK_OPTIONS.get('transparency', False) else {'has_transparency': False},
            'overprint': self.check_overprint(pdf_path) if Config.CHECK_OPTIONS.get('overprint', True) else {'has_overprint': False},
            # 블리드 검사는 pdf_analyzer의 결과를 사용
            'bleed': self.process_bleed_info(pages_info) if Config.CHECK_OPTIONS.get('bleed', True) else {'has_proper_bleed': True},
            'spot_colors': self.check_spot_color_usage(pdf_path) if Config.CHECK_OPTIONS.get('spot_colors', True) else {'has_spot_colors': False},
            'image_compression': self.check_image_compression(pdf_path) if Config.CHECK_OPTIONS.get('image_compression', True) else {'total_images': 0},
            'text_size': self.check_minimum_text_size(pdf_path) if Config.CHECK_OPTIONS.get('minimum_text', True) else {'has_small_text': False},
            'issues': self.issues,
            'warnings': self.warnings
        }
        
        return results
    
    def check_transparency(self, pdf_path):
        """
        투명도 사용 검사
        인쇄 시 투명도는 플래튼(평탄화) 처리가 필요할 수 있음
        """
        print("  • 투명도 검사 중...")
        
        transparency_info = {
            'has_transparency': False,
            'transparent_objects': [],
            'pages_with_transparency': [],
            'requires_flattening': False
        }
        
        try:
            doc = fitz.open(pdf_path)
            
            for page_num, page in enumerate(doc, 1):
                # 페이지 내용 분석
                page_dict = page.get_text("dict")
                
                # 투명도 관련 패턴 검사
                has_transparency = False
                
                # 이미지의 알파 채널 검사
                for img in page.get_images():
                    xref = img[0]
                    pix = fitz.Pixmap(doc, xref)
                    if pix.alpha:  # 알파 채널이 있으면 투명도 사용
                        has_transparency = True
                        transparency_info['transparent_objects'].append({
                            'page': page_num,
                            'type': 'image_with_alpha',
                            'xref': xref
                        })
                
                # PDF 명령어에서 투명도 관련 연산자 검사
                contents = page.read_contents()
                if contents:
                    # 투명도 관련 PDF 연산자들
                    transparency_operators = [
                        b'/CA',  # 스트로크 알파
                        b'/ca',  # 채우기 알파
                        b'/BM',  # 블렌드 모드
                        b'/SMask',  # 소프트 마스크
                        b'gs'  # 그래픽 상태 (투명도 포함 가능)
                    ]
                    
                    for op in transparency_operators:
                        if op in contents:
                            has_transparency = True
                            transparency_info['transparent_objects'].append({
                                'page': page_num,
                                'type': 'transparency_operator',
                                'operator': op.decode('utf-8', errors='ignore')
                            })
                            break
                
                if has_transparency:
                    transparency_info['has_transparency'] = True
                    transparency_info['pages_with_transparency'].append(page_num)
            
            doc.close()
            
            # 투명도가 있으면 플래튼 필요
            if transparency_info['has_transparency']:
                transparency_info['requires_flattening'] = True
                self.warnings.append({
                    'type': 'transparency_detected',
                    'severity': 'warning',
                    'message': f"투명도가 {len(transparency_info['pages_with_transparency'])}개 페이지에서 발견됨",
                    'pages': transparency_info['pages_with_transparency'],
                    'suggestion': "인쇄 전 투명도 평탄화(Flatten Transparency)를 권장합니다"
                })
            
            print(f"    ✓ 투명도 검사 완료: {'발견' if transparency_info['has_transparency'] else '없음'}")
            
        except Exception as e:
            print(f"    ⚠️ 투명도 검사 중 오류: {e}")
            self.warnings.append({
                'type': 'transparency_check_error',
                'severity': 'info',
                'message': f"투명도 검사 중 일부 오류 발생: {str(e)}"
            })
        
        return transparency_info
    
    def check_overprint(self, pdf_path):
        """
        중복인쇄(Overprint) 설정 검사
        2025.06 수정: 인쇄상 문제가 되는 경우만 감지하도록 개선
        - 흰색 오버프린트: 위험 (객체가 사라짐)
        - K100% 텍스트 오버프린트: 정상 (녹아웃 방지)
        - 라이트 컬러 오버프린트: 경고
        - 이미지 오버프린트: 오류
        """
        print("  • 중복인쇄 설정 검사 중...")
        
        overprint_info = {
            'has_overprint': False,
            'has_problematic_overprint': False,  # 문제가 되는 오버프린트
            'overprint_objects': [],
            'pages_with_overprint': [],
            'white_overprint_pages': [],  # 흰색 오버프린트 (위험)
            'k_only_overprint_pages': [],  # K100% 오버프린트 (정상)
            'light_color_overprint_pages': [],  # 라이트 컬러 오버프린트 (경고)
            'image_overprint_pages': []  # 이미지 오버프린트 (오류)
        }
        
        try:
            # PyMuPDF로 더 정확한 overprint 검사
            doc = fitz.open(pdf_path)
            
            for page_num, page in enumerate(doc, 1):
                # 페이지 콘텐츠 분석
                content = page.read_contents()
                
                if content:
                    # 오버프린트 명령어 감지
                    has_overprint = False
                    if re.search(rb'\s1\s+OP\s', content) or re.search(rb'\s1\s+op\s', content):
                        has_overprint = True
                    elif re.search(rb'\s1\s+OPM\s', content):
                        has_overprint = True
                    
                    if has_overprint:
                        overprint_info['has_overprint'] = True
                        overprint_info['pages_with_overprint'].append(page_num)
                        
                        # 색상 분석을 위해 페이지 내용 더 자세히 검사
                        # 흰색 오버프린트 감지 (CMYK 0 0 0 0)
                        if re.search(rb'0\s+0\s+0\s+0\s+k.*?1\s+OP', content) or \
                           re.search(rb'0\s+0\s+0\s+0\s+K.*?1\s+OP', content):
                            overprint_info['white_overprint_pages'].append(page_num)
                            overprint_info['has_problematic_overprint'] = True
                        
                        # K100% 오버프린트 감지 (정상적인 인쇄 기법)
                        elif re.search(rb'0\s+0\s+0\s+1\s+k.*?1\s+OP', content) or \
                             re.search(rb'0\s+0\s+0\s+1\s+K.*?1\s+OP', content):
                            overprint_info['k_only_overprint_pages'].append(page_num)
                            # K100% 오버프린트는 정상이므로 문제로 간주하지 않음
            
            doc.close()
            
            # pikepdf로 추가 검증 - ExtGState 내부의 설정 확인
            with pikepdf.open(pdf_path) as pdf:
                for page_num, page in enumerate(pdf.pages, 1):
                    if '/Resources' in page and '/ExtGState' in page.Resources:
                        for gs_name, gs_dict in page.Resources.ExtGState.items():
                            # 오버프린트 설정 확인
                            op_value = gs_dict.get('/OP', False)
                            op_fill_value = gs_dict.get('/op', False)
                            opm_value = gs_dict.get('/OPM', 0)
                            
                            # 실제 오버프린트가 활성화된 경우
                            if ((op_value == True or op_value == 1) or \
                                (op_fill_value == True or op_fill_value == 1)) and \
                               opm_value == 1:
                                
                                if page_num not in overprint_info['pages_with_overprint']:
                                    overprint_info['pages_with_overprint'].append(page_num)
                                    overprint_info['has_overprint'] = True
                                
                                # ExtGState에서는 구체적인 색상 정보를 얻기 어려우므로
                                # 일반적인 오버프린트로 분류
                                overprint_info['overprint_objects'].append({
                                    'page': page_num,
                                    'type': 'extgstate_overprint'
                                })
            
            # 중복된 페이지 번호 제거
            overprint_info['pages_with_overprint'] = sorted(list(set(overprint_info['pages_with_overprint'])))
            overprint_info['white_overprint_pages'] = sorted(list(set(overprint_info['white_overprint_pages'])))
            overprint_info['k_only_overprint_pages'] = sorted(list(set(overprint_info['k_only_overprint_pages'])))
            
            # 문제가 되는 오버프린트에 대해서만 경고
            if overprint_info['white_overprint_pages']:
                self.issues.append({
                    'type': 'white_overprint_detected',
                    'severity': 'error',
                    'message': f"흰색 오버프린트가 {len(overprint_info['white_overprint_pages'])}개 페이지에서 발견됨",
                    'pages': overprint_info['white_overprint_pages'],
                    'suggestion': "흰색 오버프린트는 객체가 사라지는 원인입니다. 오버프린트 설정을 제거하세요"
                })
            
            # K100% 오버프린트는 정보로만 제공
            if overprint_info['k_only_overprint_pages']:
                self.warnings.append({
                    'type': 'k_overprint_detected',
                    'severity': 'info',
                    'message': f"K100% 오버프린트가 {len(overprint_info['k_only_overprint_pages'])}개 페이지에서 발견됨",
                    'pages': overprint_info['k_only_overprint_pages'],
                    'suggestion': "K100% 오버프린트는 정상적인 인쇄 기법입니다 (녹아웃 방지)"
                })
            
            # 기타 오버프린트는 확인 필요
            other_overprint_pages = [p for p in overprint_info['pages_with_overprint'] 
                                    if p not in overprint_info['white_overprint_pages'] 
                                    and p not in overprint_info['k_only_overprint_pages']]
            
            if other_overprint_pages:
                self.warnings.append({
                    'type': 'overprint_detected',
                    'severity': 'warning',
                    'message': f"중복인쇄 설정이 {len(other_overprint_pages)}개 페이지에서 발견됨",
                    'pages': other_overprint_pages,
                    'suggestion': "라이트 컬러의 오버프린트는 객체가 가려질 수 있습니다. 의도적인 설정인지 확인하세요"
                })
            
            print(f"    ✓ 중복인쇄 검사 완료: {'발견' if overprint_info['has_overprint'] else '없음'}")
            if overprint_info['has_problematic_overprint']:
                print(f"    ⚠️  문제가 되는 오버프린트 발견!")
            
        except Exception as e:
            print(f"    ⚠️ 중복인쇄 검사 중 오류: {e}")
        
        return overprint_info
    
    def process_bleed_info(self, pages_info):
        """
        pdf_analyzer에서 전달받은 페이지 정보를 기반으로 블리드 정보 처리
        2025.06 수정: 중복 검사 제거, pdf_analyzer 결과 활용
        """
        print("  • 재단선 여백 정보 처리 중...")
        
        bleed_info = {
            'has_proper_bleed': True,
            'pages_without_bleed': [],
            'bleed_sizes': {},
            'min_required_bleed': Config.STANDARD_BLEED_SIZE
        }
        
        if not pages_info:
            return bleed_info
        
        try:
            # pdf_analyzer에서 전달받은 페이지 정보 처리
            for page_info in pages_info:
                page_num = page_info['page_number']
                
                if page_info.get('has_bleed'):
                    min_bleed = page_info.get('min_bleed', 0)
                    bleed_info['bleed_sizes'][page_num] = {
                        'sizes': page_info.get('bleed_info', {}),
                        'minimum': min_bleed
                    }
                    
                    # 재단 여백이 부족한 경우
                    if min_bleed < Config.STANDARD_BLEED_SIZE:
                        bleed_info['has_proper_bleed'] = False
                        bleed_info['pages_without_bleed'].append({
                            'page': page_num,
                            'current_bleed': min_bleed,
                            'required_bleed': Config.STANDARD_BLEED_SIZE
                        })
                else:
                    # 블리드 박스가 없는 경우
                    bleed_info['has_proper_bleed'] = False
                    bleed_info['pages_without_bleed'].append({
                        'page': page_num,
                        'current_bleed': 0,
                        'required_bleed': Config.STANDARD_BLEED_SIZE
                    })
            
            # 재단 여백 문제를 정보로만 보고
            if not bleed_info['has_proper_bleed']:
                self.warnings.append({
                    'type': 'insufficient_bleed',
                    'severity': 'info',
                    'message': f"{len(bleed_info['pages_without_bleed'])}개 페이지에 재단 여백 부족",
                    'pages': [p['page'] for p in bleed_info['pages_without_bleed']],
                    'suggestion': f"모든 페이지에 최소 {Config.STANDARD_BLEED_SIZE}mm의 재단 여백이 필요합니다"
                })
            
            print(f"    ✓ 재단선 정보 처리 완료: {'정상' if bleed_info['has_proper_bleed'] else '정보 제공됨'}")
            
        except Exception as e:
            print(f"    ⚠️ 재단선 정보 처리 중 오류: {e}")
        
        return bleed_info
    
    def check_spot_color_usage(self, pdf_path):
        """
        별색(Spot Color) 사용 상세 검사
        별색은 추가 비용이 발생하므로 정확한 확인 필요
        """
        print("  • 별색 사용 상세 검사 중...")
        
        spot_color_info = {
            'has_spot_colors': False,
            'spot_colors': {},
            'total_spot_colors': 0,
            'pages_with_spots': []
        }
        
        try:
            with pikepdf.open(pdf_path) as pdf:
                for page_num, page in enumerate(pdf.pages, 1):
                    if '/Resources' in page and '/ColorSpace' in page.Resources:
                        for cs_name, cs_obj in page.Resources.ColorSpace.items():
                            # Separation 색상 공간 확인
                            if isinstance(cs_obj, list) and len(cs_obj) > 0:
                                if str(cs_obj[0]) == '/Separation':
                                    spot_color_info['has_spot_colors'] = True
                                    
                                    # 별색 이름 추출
                                    spot_name = str(cs_obj[1]) if len(cs_obj) > 1 else 'Unknown'
                                    
                                    if spot_name not in spot_color_info['spot_colors']:
                                        spot_color_info['spot_colors'][spot_name] = {
                                            'name': spot_name,
                                            'pages': [],
                                            'is_pantone': 'PANTONE' in spot_name.upper()
                                        }
                                    
                                    spot_color_info['spot_colors'][spot_name]['pages'].append(page_num)
                                    
                                    if page_num not in spot_color_info['pages_with_spots']:
                                        spot_color_info['pages_with_spots'].append(page_num)
            
            spot_color_info['total_spot_colors'] = len(spot_color_info['spot_colors'])
            
            # 별색 사용 보고
            if spot_color_info['has_spot_colors']:
                # PANTONE 색상 확인
                pantone_colors = [name for name, info in spot_color_info['spot_colors'].items() 
                                if info['is_pantone']]
                
                message = f"별색 {spot_color_info['total_spot_colors']}개 사용 중"
                if pantone_colors:
                    message += f" (PANTONE {len(pantone_colors)}개 포함)"
                
                self.warnings.append({
                    'type': 'spot_colors_used',
                    'severity': 'info',
                    'message': message,
                    'spot_colors': list(spot_color_info['spot_colors'].keys()),
                    'suggestion': "별색 사용 시 추가 인쇄 비용이 발생합니다. 의도적인 사용인지 확인하세요"
                })
            
            print(f"    ✓ 별색 검사 완료: {spot_color_info['total_spot_colors']}개 발견")
            
        except Exception as e:
            print(f"    ⚠️ 별색 검사 중 오류: {e}")
        
        return spot_color_info
    
    def check_image_compression(self, pdf_path):
        """
        이미지 압축 품질 검사
        과도한 압축은 인쇄 품질 저하의 원인
        """
        print("  • 이미지 압축 품질 검사 중...")
        
        compression_info = {
            'total_images': 0,
            'jpeg_compressed': 0,
            'low_quality_images': [],
            'compression_types': {}
        }
        
        try:
            doc = fitz.open(pdf_path)
            
            for page_num, page in enumerate(doc, 1):
                for img_index, img in enumerate(page.get_images()):
                    compression_info['total_images'] += 1
                    xref = img[0]
                    
                    # 이미지 정보 추출
                    img_dict = doc.xref_object(xref)
                    
                    # 압축 필터 확인
                    if '/Filter' in img_dict:
                        filter_type = img_dict['/Filter']
                        if isinstance(filter_type, list):
                            filter_type = filter_type[0]
                        
                        filter_name = str(filter_type).replace('/', '')
                        
                        # 압축 타입 카운트
                        if filter_name not in compression_info['compression_types']:
                            compression_info['compression_types'][filter_name] = 0
                        compression_info['compression_types'][filter_name] += 1
                        
                        # JPEG 압축 확인
                        if 'DCTDecode' in filter_name:
                            compression_info['jpeg_compressed'] += 1
                            
                            # 이미지 품질 추정 (간접적)
                            # 실제로는 더 정교한 방법이 필요하지만, 
                            # 여기서는 파일 크기와 해상도 비율로 추정
                            try:
                                pix = fitz.Pixmap(doc, xref)
                                pixel_count = pix.width * pix.height
                                stream = doc.xref_stream(xref)
                                compressed_size = len(stream)
                                
                                # 압축률 계산 (낮을수록 고압축)
                                compression_ratio = compressed_size / pixel_count
                                
                                # 매우 높은 압축률은 품질 저하 의심
                                if compression_ratio < 0.5:  # 임계값
                                    compression_info['low_quality_images'].append({
                                        'page': page_num,
                                        'image_index': img_index,
                                        'compression_ratio': compression_ratio,
                                        'size': f"{pix.width}x{pix.height}"
                                    })
                            except:
                                pass
            
            doc.close()
            
            # 압축 품질 문제 보고
            if compression_info['low_quality_images']:
                self.warnings.append({
                    'type': 'high_compression_detected',
                    'severity': 'warning',
                    'message': f"{len(compression_info['low_quality_images'])}개 이미지가 과도하게 압축됨",
                    'count': len(compression_info['low_quality_images']),
                    'suggestion': "인쇄 품질을 위해 이미지 압축률을 낮추는 것을 권장합니다"
                })
            
            print(f"    ✓ 이미지 압축 검사 완료: {compression_info['total_images']}개 이미지 중 {compression_info['jpeg_compressed']}개 JPEG 압축")
            
        except Exception as e:
            print(f"    ⚠️ 이미지 압축 검사 중 오류: {e}")
        
        return compression_info
    
    def check_minimum_text_size(self, pdf_path):
        """
        최소 텍스트 크기 검사
        너무 작은 텍스트는 인쇄 시 읽기 어려움
        """
        print("  • 최소 텍스트 크기 검사 중...")
        
        text_size_info = {
            'min_size_found': 999,
            'small_text_pages': [],
            'text_sizes': {},
            'has_small_text': False
        }
        
        MIN_TEXT_SIZE = 4.0  # 최소 권장 크기 (포인트)
        
        try:
            doc = fitz.open(pdf_path)
            
            for page_num, page in enumerate(doc, 1):
                # 텍스트 블록 추출
                blocks = page.get_text("dict")
                page_min_size = 999
                
                for block in blocks.get("blocks", []):
                    if block.get("type") == 0:  # 텍스트 블록
                        for line in block.get("lines", []):
                            for span in line.get("spans", []):
                                font_size = span.get("size", 0)
                                
                                if font_size > 0:
                                    # 페이지별 최소 크기 업데이트
                                    if font_size < page_min_size:
                                        page_min_size = font_size
                                    
                                    # 전체 최소 크기 업데이트
                                    if font_size < text_size_info['min_size_found']:
                                        text_size_info['min_size_found'] = font_size
                                    
                                    # 너무 작은 텍스트 확인
                                    if font_size < MIN_TEXT_SIZE:
                                        text_size_info['has_small_text'] = True
                                        if page_num not in [p['page'] for p in text_size_info['small_text_pages']]:
                                            text_size_info['small_text_pages'].append({
                                                'page': page_num,
                                                'min_size': font_size
                                            })
                
                if page_min_size < 999:
                    text_size_info['text_sizes'][page_num] = page_min_size
            
            doc.close()
            
            # 작은 텍스트 경고
            if text_size_info['has_small_text']:
                self.warnings.append({
                    'type': 'small_text_detected',
                    'severity': 'warning',
                    'message': f"{len(text_size_info['small_text_pages'])}개 페이지에 {MIN_TEXT_SIZE}pt 미만의 작은 텍스트 발견",
                    'pages': [p['page'] for p in text_size_info['small_text_pages']],
                    'min_found': f"{text_size_info['min_size_found']:.1f}pt",
                    'suggestion': f"인쇄 가독성을 위해 최소 {MIN_TEXT_SIZE}pt 이상의 텍스트 크기를 권장합니다"
                })
            
            print(f"    ✓ 텍스트 크기 검사 완료: 최소 {text_size_info['min_size_found']:.1f}pt")
            
        except Exception as e:
            print(f"    ⚠️ 텍스트 크기 검사 중 오류: {e}")
        
        return text_size_info
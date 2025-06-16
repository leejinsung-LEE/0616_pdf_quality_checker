# pdf_analyzer.py - PDF 분석 핵심 엔진 (스레드 안전 버전)
# Phase 2.5: 고급 인쇄 검사와 프리플라이트 기능 통합
# 2024.12 수정: 폰트 임베딩 체크 로직 개선 - 올바른 판단
# 2025.01 수정: 이미지 해상도 기준 완화, 페이지 회전 정보 개선
# 2025.01 추가: 스레드 안전성을 위한 인스턴스 변수 제거
# 2025.06 수정: 블리드 검사 통합 - print_quality_checker에 페이지 정보 전달

"""
pdf_analyzer.py - PDF 분석 핵심 엔진 (스레드 안전 버전)
Phase 2.5: 투명도, 중복인쇄, 재단선 검사 및 프리플라이트 통합
폰트 임베딩 감지 정확도 개선
이미지 해상도 기준 완화 및 페이지 회전 정보 추가
스레드 안전성 확보 - 인스턴스 변수 제거
블리드 검사 중복 제거 - 한 곳에서만 수행
"""

import pikepdf
import fitz  # PyMuPDF
from pathlib import Path
from utils import (
    points_to_mm, format_size_mm, safe_str, format_file_size,
    safe_integer, safe_float
)
from config import Config
from ink_calculator import InkCalculator
from print_quality_checker import PrintQualityChecker
from preflight_profiles import PreflightProfiles
import time
import threading

class PDFAnalyzer:
    """PDF 파일을 분석하는 메인 클래스 - 스레드 안전 버전"""
    
    def __init__(self):
        """분석기 초기화"""
        # 스레드별 독립 인스턴스 생성
        self.ink_calculator = InkCalculator()
        self.print_quality_checker = PrintQualityChecker()
        
        # 디버깅용 인스턴스 ID
        self.instance_id = id(self)
        self.thread_id = threading.current_thread().ident
        
    def analyze(self, pdf_path, include_ink_analysis=None, preflight_profile='offset'):
    # include_ink_analysis가 None이면 Config 설정 사용
        if include_ink_analysis is None:
            include_ink_analysis = Config.is_ink_analysis_enabled()        
        """
        PDF 파일을 종합적으로 분석하는 메인 메서드
        스레드 안전성을 위해 모든 데이터를 지역 변수로 처리
        
        Args:
            pdf_path: 분석할 PDF 파일 경로
            include_ink_analysis: 잉크량 분석 포함 여부 (시간이 걸림)
            preflight_profile: 적용할 프리플라이트 프로파일
            
        Returns:
            dict: 분석 결과를 담은 딕셔너리
        """
        # 스레드 정보 로깅
        current_thread = threading.current_thread()
        print(f"\n📄 [Thread {current_thread.ident}] PDF 분석 시작: {Path(pdf_path).name}")
        print(f"   [Analyzer Instance: {self.instance_id}]")
        print(f"🎯 프리플라이트 프로파일: {preflight_profile}")
        start_time = time.time()
        
        # 지역 변수로 PDF와 결과 관리
        local_pdf = None
        local_analysis_result = {}
        
        try:
            # 프리플라이트 프로파일 로드
            current_profile = PreflightProfiles.get_profile_by_name(preflight_profile)
            if not current_profile:
                print(f"⚠️  '{preflight_profile}' 프로파일을 찾을 수 없습니다. 기본(offset) 사용")
                current_profile = PreflightProfiles.get_offset_printing()
            
            # PDF 파일 열기 - 지역 변수로
            local_pdf = pikepdf.open(pdf_path)
            
            # 파일 크기 확인
            file_size = Path(pdf_path).stat().st_size
            
            # 분석 결과를 저장할 딕셔너리 초기화 - 지역 변수로
            local_analysis_result = {
                'filename': Path(pdf_path).name,
                'file_path': str(pdf_path),
                'file_size': file_size,
                'file_size_formatted': format_file_size(file_size),
                'preflight_profile': current_profile.name,
                '_analyzer_instance': self.instance_id,  # 디버깅용
                '_thread_id': current_thread.ident,      # 디버깅용
                'basic_info': self._analyze_basic_info(local_pdf),
                'pages': self._analyze_pages(local_pdf),
                'fonts': self._analyze_fonts(local_pdf, pdf_path),
                'colors': self._analyze_colors(local_pdf),
                'images': self._analyze_images(local_pdf, pdf_path),
                'issues': []  # 발견된 문제점들
            }
            
            # Phase 2.5: 고급 인쇄 품질 검사
            # 2025.06 수정: 페이지 정보를 전달하여 블리드 검사 중복 제거
            if any(Config.CHECK_OPTIONS.values()):
                print(Config.MESSAGES['print_quality_checking'])
                # 페이지 정보를 print_quality_checker에 전달
                print_quality_result = self.print_quality_checker.check_all(
                    pdf_path, 
                    pages_info=local_analysis_result['pages']  # 블리드 정보 포함된 페이지 정보 전달
                )
                local_analysis_result['print_quality'] = print_quality_result
                
                # 고급 검사에서 발견된 문제들 추가
                for issue in print_quality_result.get('issues', []):
                    local_analysis_result['issues'].append(issue)
                for warning in print_quality_result.get('warnings', []):
                    local_analysis_result['issues'].append(warning)
            
            # 잉크량 분석 (선택적)
            if include_ink_analysis:
                print("\n🎨 잉크량 분석 중... (시간이 걸릴 수 있습니다)")
                ink_result = self.ink_calculator.calculate(pdf_path)
                local_analysis_result['ink_coverage'] = ink_result
            
            # 문제점 검사 - local_analysis_result 전달
            self._check_issues(local_analysis_result)
            
            # Phase 2.5: 프리플라이트 검사 수행
            print(f"\n{Config.MESSAGES['preflight_checking']}")
            preflight_result = current_profile.check(local_analysis_result)
            local_analysis_result['preflight_result'] = preflight_result
            
            # 프리플라이트 결과를 이슈에 추가
            self._add_preflight_issues(local_analysis_result, preflight_result)
            
            # 분석 시간 기록
            analysis_time = time.time() - start_time
            local_analysis_result['analysis_time'] = f"{analysis_time:.1f}초"
            
            # 프리플라이트 결과 출력
            self._print_preflight_summary(preflight_result)
            
            print(f"\n✅ [Thread {current_thread.ident}] 분석 완료! (소요시간: {analysis_time:.1f}초)")
            
            return local_analysis_result
            
        except Exception as e:
            print(f"❌ [Thread {current_thread.ident}] PDF 분석 중 오류 발생: {e}")
            return {'error': str(e), '_thread_id': current_thread.ident}
        finally:
            # PDF 파일 닫기
            if local_pdf:
                local_pdf.close()
    
    def _analyze_basic_info(self, pdf_obj):
        """PDF 기본 정보 추출 - pdf 객체를 파라미터로 받음"""
        print("  📋 기본 정보 분석 중...")
        
        info = {
            'page_count': len(pdf_obj.pages),
            'pdf_version': safe_str(pdf_obj.pdf_version),
            'is_encrypted': pdf_obj.is_encrypted,
            'is_linearized': False,
            'title': '',
            'author': '',
            'subject': '',
            'keywords': '',
            'creator': '',
            'producer': '',
            'creation_date': '',
            'modification_date': ''
        }
        
        # 선형화(웹 최적화) 확인
        try:
            if hasattr(pdf_obj, 'is_linearized'):
                info['is_linearized'] = pdf_obj.is_linearized
        except:
            pass
        
        # 메타데이터 추출 (있는 경우)
        if pdf_obj.docinfo:
            info['title'] = safe_str(pdf_obj.docinfo.get('/Title', ''))
            info['author'] = safe_str(pdf_obj.docinfo.get('/Author', ''))
            info['subject'] = safe_str(pdf_obj.docinfo.get('/Subject', ''))
            info['keywords'] = safe_str(pdf_obj.docinfo.get('/Keywords', ''))
            info['creator'] = safe_str(pdf_obj.docinfo.get('/Creator', ''))
            info['producer'] = safe_str(pdf_obj.docinfo.get('/Producer', ''))
            
            # 날짜 정보
            try:
                if '/CreationDate' in pdf_obj.docinfo:
                    info['creation_date'] = safe_str(pdf_obj.docinfo['/CreationDate'])
                if '/ModDate' in pdf_obj.docinfo:
                    info['modification_date'] = safe_str(pdf_obj.docinfo['/ModDate'])
            except:
                pass
        
        print(f"    ✓ 총 {info['page_count']}페이지, PDF {info['pdf_version']}")
        return info
    
    def _analyze_pages(self, pdf_obj):
        """
        각 페이지 정보 분석 - pdf 객체를 파라미터로 받음
        2025.06: 블리드 정보를 여기서만 분석 (중복 제거)
        """
        print("  📐 페이지 정보 분석 중...")
        
        pages_info = []
        
        for page_num, page in enumerate(pdf_obj.pages, 1):
            # 모든 박스 정보 추출
            mediabox = page.MediaBox if '/MediaBox' in page else None
            cropbox = page.CropBox if '/CropBox' in page else mediabox
            bleedbox = page.BleedBox if '/BleedBox' in page else cropbox
            trimbox = page.TrimBox if '/TrimBox' in page else cropbox
            artbox = page.ArtBox if '/ArtBox' in page else cropbox
            
            # MediaBox 좌표값 추출
            if mediabox:
                left = float(mediabox[0])
                bottom = float(mediabox[1])
                right = float(mediabox[2])
                top = float(mediabox[3])
                
                # 페이지 크기 계산
                width = right - left
                height = top - bottom
                
                # mm 단위로 변환
                width_mm = points_to_mm(width)
                height_mm = points_to_mm(height)
                
                # 페이지 회전 정보
                rotation = int(page.get('/Rotate', 0))
                
                # 회전을 고려한 실제 표시 크기
                if rotation in [90, 270]:
                    display_width_mm = height_mm
                    display_height_mm = width_mm
                else:
                    display_width_mm = width_mm
                    display_height_mm = height_mm
                
                # 표준 용지 크기 감지 (회전 고려)
                paper_size = Config.get_paper_size_name(display_width_mm, display_height_mm)
                
                # 회전 정보를 포함한 크기 표시
                size_formatted_with_rotation = format_size_mm(width, height)
                if rotation != 0:
                    size_formatted_with_rotation += f" ({rotation}° 회전)"
                
                page_info = {
                    'page_number': page_num,
                    'width_pt': width,
                    'height_pt': height,
                    'width_mm': width_mm,
                    'height_mm': height_mm,
                    'display_width_mm': display_width_mm,
                    'display_height_mm': display_height_mm,
                    'size_formatted': format_size_mm(width, height),
                    'size_formatted_with_rotation': size_formatted_with_rotation,
                    'paper_size': paper_size,
                    'rotation': rotation,
                    'is_rotated': rotation != 0,
                    'mediabox': [left, bottom, right, top],
                    'has_bleed': False,
                    'bleed_info': {},
                    'min_bleed': 0  # 2025.06 추가: print_quality_checker에서 참조
                }
                
                # Phase 2.5: 상세 재단선 정보
                # 2025.06: 여기서만 블리드 계산 수행
                if trimbox and bleedbox and trimbox != bleedbox:
                    page_info['has_bleed'] = True
                    
                    # 각 방향별 재단 여백 계산
                    trim_coords = [float(x) for x in trimbox]
                    bleed_coords = [float(x) for x in bleedbox]
                    
                    page_info['bleed_info'] = {
                        'left': points_to_mm(trim_coords[0] - bleed_coords[0]),
                        'bottom': points_to_mm(trim_coords[1] - bleed_coords[1]),
                        'right': points_to_mm(bleed_coords[2] - trim_coords[2]),
                        'top': points_to_mm(bleed_coords[3] - trim_coords[3])
                    }
                    
                    # 최소 재단 여백
                    min_bleed = min(page_info['bleed_info'].values())
                    page_info['min_bleed'] = min_bleed
                
                pages_info.append(page_info)
                
                # 처음 3페이지만 상세 출력
                if page_num <= 3:
                    size_str = f"{page_info['size_formatted']}"
                    if paper_size != 'Custom':
                        size_str += f" ({paper_size})"
                    if rotation != 0:
                        size_str += f" - {rotation}° 회전"
                    print(f"    ✓ {page_num}페이지: {size_str}")
                    if page_info['has_bleed']:
                        print(f"      재단여백: {page_info['min_bleed']:.1f}mm")
        
        if len(pages_info) > 3:
            print(f"    ... 그 외 {len(pages_info) - 3}페이지")
        
        return pages_info
    
    def _analyze_fonts(self, pdf_obj, pdf_path):
        """
        폰트 정보 분석 - pdf 객체와 경로를 파라미터로 받음
        PyMuPDF의 폰트 정보를 기준으로 판단
        """
        print("  🔤 폰트 정보 분석 중...")
        
        fonts_info = {}
        font_count = 0
        
        try:
            # PyMuPDF를 사용한 폰트 분석 - 별도의 문서 객체 사용
            doc_fitz = fitz.open(pdf_path)
            
            # 각 페이지의 폰트 정보 수집
            for page_num, page in enumerate(pdf_obj.pages, 1):
                # PyMuPDF로 폰트 리스트 가져오기
                fitz_page = doc_fitz[page_num - 1]
                fitz_fonts = fitz_page.get_fonts()
                
                # fitz 폰트 정보를 기준으로 처리
                for font_data in fitz_fonts:
                    if len(font_data) >= 5:
                        font_count += 1
                        
                        xref = font_data[0]
                        ext = font_data[1]
                        font_type = font_data[2]
                        basename = font_data[3]
                        fontname = font_data[4]
                        
                        # 폰트 정보 구성
                        font_info = {
                            'page': page_num,
                            'name': fontname,
                            'type': font_type,
                            'subtype': '',
                            'embedded': ext != "",
                            'subset': False,
                            'encoding': font_data[5] if len(font_data) > 5 else '',
                            'base_font': basename
                        }
                        
                        # 서브셋 여부 확인
                        if '+' in basename:
                            font_info['subset'] = True
                            font_info['embedded'] = True
                        
                        # 포함 표시 확인
                        if '(포함됨)' in fontname or '(embedded)' in fontname.lower():
                            font_info['embedded'] = True
                        elif '(포함 안 됨)' in fontname or '(not embedded)' in fontname.lower():
                            font_info['embedded'] = False
                        
                        # 표준 14 폰트 확인
                        standard_fonts = [
                            'Times-Roman', 'Times-Bold', 'Times-Italic', 'Times-BoldItalic',
                            'Helvetica', 'Helvetica-Bold', 'Helvetica-Oblique', 'Helvetica-BoldOblique',
                            'Courier', 'Courier-Bold', 'Courier-Oblique', 'Courier-BoldOblique',
                            'Symbol', 'ZapfDingbats'
                        ]
                        
                        if basename in standard_fonts:
                            font_info['embedded'] = True
                            font_info['is_standard'] = True
                        else:
                            font_info['is_standard'] = False
                        
                        # pikepdf로 추가 정보 확인 (보조적으로만 사용)
                        if '/Resources' in page and '/Font' in page.Resources:
                            for font_name, font_obj in page.Resources.Font.items():
                                if hasattr(font_obj, 'BaseFont'):
                                    base_font_pikepdf = safe_str(font_obj.BaseFont)
                                    if base_font_pikepdf == basename or basename in base_font_pikepdf:
                                        if hasattr(font_obj, 'Subtype'):
                                            font_info['subtype'] = safe_str(font_obj.Subtype)
                                        
                                        if '/FontDescriptor' in font_obj and not font_info['embedded']:
                                            descriptor = font_obj.FontDescriptor
                                            if any(key in descriptor for key in ['/FontFile', '/FontFile2', '/FontFile3']):
                                                font_info['embedded'] = True
                        
                        # 폰트 정보 저장
                        key = f"{fontname}_{page_num}"
                        fonts_info[key] = font_info
            
            doc_fitz.close()
            
            print(f"    ✓ 총 {font_count}개 폰트 발견")
            
            # 임베딩되지 않은 폰트 개수
            not_embedded = sum(1 for f in fonts_info.values() 
                             if not f['embedded'] and not f.get('is_standard', False))
            if not_embedded > 0:
                print(f"    ⚠️  {not_embedded}개 폰트가 임베딩되지 않음")
            
            # 서브셋 폰트 개수
            subset_count = sum(1 for f in fonts_info.values() if f['subset'])
            if subset_count > 0:
                print(f"    ✓ {subset_count}개 서브셋 폰트 발견 (최적화됨)")
                
        except Exception as e:
            print(f"    ⚠️  폰트 분석 중 일부 오류: {e}")
        
        return fonts_info
    
    def _analyze_colors(self, pdf_obj):
        """색상 공간 정보 분석 - pdf 객체를 파라미터로 받음"""
        print("  🎨 색상 정보 분석 중...")
        
        color_info = {
            'color_spaces': set(),
            'has_rgb': False,
            'has_cmyk': False,
            'has_gray': False,
            'has_spot_colors': False,
            'spot_color_names': [],
            'spot_color_details': {},
            'icc_profiles': []
        }
        
        try:
            for page_num, page in enumerate(pdf_obj.pages, 1):
                if '/Resources' in page:
                    resources = page.Resources
                    
                    # ColorSpace 확인
                    if '/ColorSpace' in resources:
                        for cs_name, cs_obj in resources.ColorSpace.items():
                            color_space = safe_str(cs_name)
                            color_info['color_spaces'].add(color_space)
                            
                            # RGB 확인
                            if 'RGB' in color_space.upper():
                                color_info['has_rgb'] = True
                            
                            # CMYK 확인
                            if 'CMYK' in color_space.upper():
                                color_info['has_cmyk'] = True
                            
                            # Gray 확인
                            if 'GRAY' in color_space.upper():
                                color_info['has_gray'] = True
                            
                            # 별색 확인
                            if isinstance(cs_obj, list) and len(cs_obj) > 0:
                                if safe_str(cs_obj[0]) == '/Separation':
                                    color_info['has_spot_colors'] = True
                                    if len(cs_obj) > 1:
                                        spot_name = safe_str(cs_obj[1])
                                        if spot_name not in color_info['spot_color_names']:
                                            color_info['spot_color_names'].append(spot_name)
                                            
                                            color_info['spot_color_details'][spot_name] = {
                                                'name': spot_name,
                                                'pages': [page_num],
                                                'is_pantone': 'PANTONE' in spot_name.upper(),
                                                'color_space': color_space
                                            }
                                        else:
                                            color_info['spot_color_details'][spot_name]['pages'].append(page_num)
                            
                            # ICC 프로파일 확인
                            if isinstance(cs_obj, list) and len(cs_obj) > 0:
                                if safe_str(cs_obj[0]) == '/ICCBased':
                                    color_info['icc_profiles'].append(color_space)
            
            # 결과 요약
            print(f"    ✓ 색상 공간: {', '.join(color_info['color_spaces']) if color_info['color_spaces'] else '기본'}")
            if color_info['has_rgb']:
                print("    ✓ RGB 색상 사용")
            if color_info['has_cmyk']:
                print("    ✓ CMYK 색상 사용")
            if color_info['has_spot_colors']:
                print(f"    ✓ 별색 {len(color_info['spot_color_names'])}개 사용: {', '.join(color_info['spot_color_names'][:3])}")
                if len(color_info['spot_color_names']) > 3:
                    print(f"       ... 그 외 {len(color_info['spot_color_names'])-3}개")
                
        except Exception as e:
            print(f"    ⚠️  색상 분석 중 일부 오류: {e}")
        
        # set을 list로 변환 (JSON 저장을 위해)
        color_info['color_spaces'] = list(color_info['color_spaces'])
        
        return color_info
    
    def _analyze_images(self, pdf_obj, pdf_path):
        """이미지 정보 분석 - pdf 객체와 경로를 파라미터로 받음"""
        print("  🖼️  이미지 정보 분석 중...")
        
        image_info = {
            'total_count': 0,
            'low_resolution_count': 0,
            'images': [],
            'resolution_categories': {
                'critical': 0,
                'warning': 0,
                'acceptable': 0,
                'optimal': 0
            }
        }
        
        try:
            # PyMuPDF를 사용한 이미지 분석 - 별도의 문서 객체 사용
            doc = fitz.open(pdf_path)
            
            for page_num, page in enumerate(doc, 1):
                # 페이지의 이미지 목록 가져오기
                image_list = page.get_images()
                
                for img_index, img in enumerate(image_list):
                    image_info['total_count'] += 1
                    
                    # 이미지 정보 추출
                    xref = img[0]
                    pix = fitz.Pixmap(doc, xref)
                    
                    img_data = {
                        'page': page_num,
                        'width': pix.width,
                        'height': pix.height,
                        'dpi': 0,
                        'resolution_category': '',
                        'colorspace': pix.colorspace.name if pix.colorspace else 'Unknown',
                        'size_bytes': len(pix.samples),
                        'has_alpha': pix.alpha
                    }
                    
                    # DPI 계산
                    if img[2] > 0 and img[3] > 0:
                        img_width_pt = img[2]
                        img_height_pt = img[3]
                        
                        dpi_x = pix.width / (img_width_pt / 72.0)
                        dpi_y = pix.height / (img_height_pt / 72.0)
                        img_data['dpi'] = min(dpi_x, dpi_y)
                        
                        # 해상도 카테고리 분류
                        if img_data['dpi'] < Config.MIN_IMAGE_DPI:
                            img_data['resolution_category'] = 'critical'
                            image_info['resolution_categories']['critical'] += 1
                            image_info['low_resolution_count'] += 1
                        elif img_data['dpi'] < Config.WARNING_IMAGE_DPI:
                            img_data['resolution_category'] = 'warning'
                            image_info['resolution_categories']['warning'] += 1
                        elif img_data['dpi'] < Config.OPTIMAL_IMAGE_DPI:
                            img_data['resolution_category'] = 'acceptable'
                            image_info['resolution_categories']['acceptable'] += 1
                        else:
                            img_data['resolution_category'] = 'optimal'
                            image_info['resolution_categories']['optimal'] += 1
                    
                    image_info['images'].append(img_data)
                    
                    # 메모리 정리
                    pix = None
            
            doc.close()
            
            print(f"    ✓ 총 {image_info['total_count']}개 이미지 발견")
            if image_info['low_resolution_count'] > 0:
                print(f"    ⚠️  {image_info['low_resolution_count']}개 이미지가 저해상도 ({Config.MIN_IMAGE_DPI} DPI 미만)")
            
            # 해상도 분포 출력
            if image_info['total_count'] > 0:
                print(f"    • 최적(300 DPI↑): {image_info['resolution_categories']['optimal']}개")
                print(f"    • 양호(150-300): {image_info['resolution_categories']['acceptable']}개")
                print(f"    • 주의(72-150): {image_info['resolution_categories']['warning']}개")
                print(f"    • 위험(72 미만): {image_info['resolution_categories']['critical']}개")
                
        except Exception as e:
            print(f"    ⚠️  이미지 분석 중 일부 오류: {e}")
        
        return image_info
    
    def _check_issues(self, analysis_result):
        """
        발견된 문제점들을 종합하여 체크 - analysis_result를 파라미터로 받음
        2025.06: 블리드 관련 이슈는 print_quality_checker에서 처리하므로 제거
        """
        print("\n🔍 문제점 검사 중...")
        
        issues = analysis_result['issues']
        
        # 1. 페이지 크기 일관성 검사 (회전 고려)
        pages = analysis_result['pages']
        if pages:
            # 회전을 고려한 표시 크기로 그룹화
            size_count = {}
            for page in pages:
                size_key = (round(page['display_width_mm']), round(page['display_height_mm']))
                if size_key not in size_count:
                    size_count[size_key] = {
                        'pages': [],
                        'size_str': f"{page['display_width_mm']:.0f}×{page['display_height_mm']:.0f}mm",
                        'paper_size': page['paper_size'],
                        'rotation': page['rotation']
                    }
                size_count[size_key]['pages'].append(page)
            
            # 가장 일반적인 크기
            common_size_info = max(size_count.items(), key=lambda x: len(x[1]['pages']))
            common_size_key = common_size_info[0]
            common_size_data = common_size_info[1]
            
            # 크기가 다른 페이지들 수집
            inconsistent_pages_detail = []
            for size_key, size_data in size_count.items():
                if size_key != common_size_key:
                    for page in size_data['pages']:
                        inconsistent_pages_detail.append({
                            'page': page['page_number'],
                            'size': size_data['size_str'],
                            'paper_size': size_data['paper_size'],
                            'rotation': page['rotation']
                        })
            
            # 페이지 크기 불일치를 하나의 이슈로 통합
            if inconsistent_pages_detail:
                detail_msg = f"기준 크기: {common_size_data['size_str']} ({common_size_data['paper_size']})"
                
                issues.append({
                    'type': 'page_size_inconsistent',
                    'severity': 'warning',
                    'message': f"페이지 크기 불일치",
                    'base_size': common_size_data['size_str'],
                    'base_paper': common_size_data['paper_size'],
                    'affected_pages': [p['page'] for p in inconsistent_pages_detail],
                    'page_details': inconsistent_pages_detail,
                    'suggestion': f"모든 페이지를 동일한 크기로 통일하세요 ({detail_msg})"
                })
        
        # 2. 폰트 임베딩 검사
        fonts = analysis_result['fonts']
        font_issues = {}
        
        for font_key, font_info in fonts.items():
            if not font_info['embedded'] and not font_info.get('is_standard', False):
                font_name = font_info.get('base_font', font_info['name'])
                if font_name not in font_issues:
                    font_issues[font_name] = []
                font_issues[font_name].append(font_info['page'])
        
        # 폰트 임베딩 이슈를 하나로 통합
        if font_issues:
            all_pages = []
            all_fonts = list(font_issues.keys())
            for pages_list in font_issues.values():
                all_pages.extend(pages_list)
            all_pages = sorted(list(set(all_pages)))
            
            issues.append({
                'type': 'font_not_embedded',
                'severity': 'error',
                'message': f"폰트 미임베딩 - {len(all_fonts)}개 폰트",
                'affected_pages': all_pages,
                'fonts': all_fonts,
                'suggestion': "PDF 내보내기 시 '모든 폰트 포함' 옵션을 선택하세요"
            })
        
        # 3. RGB 색상 사용 검사
        colors = analysis_result['colors']
        if colors['has_rgb'] and not colors['has_cmyk']:
            issues.append({
                'type': 'rgb_only',
                'severity': 'warning',
                'message': "RGB 색상만 사용됨 (인쇄용은 CMYK 권장)",
                'suggestion': "인쇄 품질을 위해 CMYK로 변환하세요"
            })
        
        # 4. 별색 사용 검사
        if colors['has_spot_colors'] and colors['spot_color_names']:
            pantone_colors = [name for name in colors['spot_color_names'] 
                            if 'PANTONE' in name.upper()]
            
            severity = 'info'
            suggestion = "별색 사용 시 추가 인쇄 비용이 발생할 수 있습니다"
            
            if len(colors['spot_color_names']) > 2:
                severity = 'warning'
                suggestion = "별색이 많습니다. 비용 절감을 위해 CMYK 변환을 고려하세요"
            
            spot_pages = []
            for spot_detail in colors['spot_color_details'].values():
                spot_pages.extend(spot_detail['pages'])
            spot_pages = sorted(list(set(spot_pages)))
            
            issues.append({
                'type': 'spot_colors',
                'severity': severity,
                'message': f"별색 {len(colors['spot_color_names'])}개 사용: {', '.join(colors['spot_color_names'][:3])}",
                'affected_pages': spot_pages,
                'spot_colors': colors['spot_color_names'],
                'pantone_count': len(pantone_colors),
                'suggestion': suggestion
            })
        
        # 5. 이미지 해상도 검사
        images = analysis_result.get('images', {})
        if images.get('low_resolution_count', 0) > 0:
            low_res_images = [img for img in images.get('images', []) 
                            if img['dpi'] > 0 and img['dpi'] < Config.MIN_IMAGE_DPI]
            
            low_res_pages = []
            min_dpi = float('inf')
            for img in low_res_images:
                low_res_pages.append(img['page'])
                if img['dpi'] < min_dpi:
                    min_dpi = img['dpi']
            low_res_pages = sorted(list(set(low_res_pages)))
            
            issues.append({
                'type': 'low_resolution_image',
                'severity': 'error',
                'message': f"저해상도 이미지 - {images['low_resolution_count']}개",
                'affected_pages': low_res_pages,
                'min_dpi': min_dpi,
                'suggestion': f"인쇄 품질을 위해 최소 {Config.MIN_IMAGE_DPI} DPI 이상으로 교체하세요"
            })
        
        # 주의가 필요한 이미지 (72-150 DPI)도 정보 제공
        if images.get('resolution_categories', {}).get('warning', 0) > 0:
            warning_images = [img for img in images.get('images', [])
                            if img.get('resolution_category') == 'warning']
            warning_pages = sorted(list(set([img['page'] for img in warning_images])))
            
            issues.append({
                'type': 'medium_resolution_image',
                'severity': 'info',
                'message': f"중간 해상도 이미지 - {len(warning_images)}개 (72-150 DPI)",
                'affected_pages': warning_pages,
                'suggestion': "일반 문서용으로는 사용 가능하나, 고품질 인쇄에는 부적합할 수 있습니다"
            })
        
        # 6. 잉크량 검사
        ink = analysis_result.get('ink_coverage', {})
        if 'summary' in ink and ink['summary']['problem_pages']:
            problem_pages = []
            max_coverage = 0
            for problem in ink['summary']['problem_pages']:
                problem_pages.append(problem['page'])
                if problem['max_coverage'] > max_coverage:
                    max_coverage = problem['max_coverage']
            
            issues.append({
                'type': 'high_ink_coverage',
                'severity': 'error',
                'message': f"잉크량 초과 - 최대 {max_coverage:.1f}%",
                'affected_pages': problem_pages,
                'suggestion': f"잉크량을 {Config.MAX_INK_COVERAGE}% 이하로 조정하세요"
            })
        
        # 블리드 관련 이슈는 print_quality_checker에서 처리하므로 여기서는 제거
        
        # 결과 출력
        if issues:
            print(f"\n⚠️  발견된 문제: {len(issues)}개")
            
            # 심각도별 분류
            errors = [i for i in issues if i['severity'] == 'error']
            warnings = [i for i in issues if i['severity'] == 'warning']
            infos = [i for i in issues if i['severity'] == 'info']
            
            if errors:
                print(f"\n❌ 오류 ({len(errors)}개):")
                for issue in errors[:3]:
                    print(f"  • {issue['message']}")
                if len(errors) > 3:
                    print(f"  ... 그 외 {len(errors) - 3}개")
            
            if warnings:
                print(f"\n⚠️  경고 ({len(warnings)}개):")
                for issue in warnings[:3]:
                    print(f"  • {issue['message']}")
                if len(warnings) > 3:
                    print(f"  ... 그 외 {len(warnings) - 3}개")
            
            if infos:
                print(f"\nℹ️  정보 ({len(infos)}개):")
                for issue in infos[:2]:
                    print(f"  • {issue['message']}")
        else:
            print("\n✅ 기본 검사에서 문제점이 발견되지 않았습니다!")
    
    def _add_preflight_issues(self, analysis_result, preflight_result):
        """
        프리플라이트 결과를 이슈에 추가 - 중복 제거
        2025.06: 블리드 관련 중복 제거 개선
        """
        issues = analysis_result['issues']
        
        # 프리플라이트 결과를 이슈에 추가
        for failed in preflight_result['failed']:
            # 블리드 관련 이슈는 print_quality_checker에서 이미 처리했으므로 제외
            if 'bleed' not in failed['rule_name'].lower():
                issues.append({
                    'type': 'preflight_failed',
                    'severity': 'error',
                    'message': f"[프리플라이트] {failed['rule_name']}: {failed['message']}",
                    'rule': failed['rule_name'],
                    'expected': failed['expected'],
                    'found': failed['found']
                })
        
        for warning in preflight_result['warnings']:
            issues.append({
                'type': 'preflight_warning',
                'severity': 'warning',
                'message': f"[프리플라이트] {warning['rule_name']}: {warning['message']}",
                'rule': warning['rule_name'],
                'expected': warning['expected'],
                'found': warning['found']
            })
        
        # 정보성 메시지도 추가 (블리드 관련은 제외)
        for info in preflight_result.get('info', []):
            # 블리드 관련 정보는 이미 print_quality_checker에서 처리됨
            if 'bleed' not in info['rule_name'].lower():
                issues.append({
                    'type': 'preflight_info',
                    'severity': 'info',
                    'message': f"[프리플라이트] {info['rule_name']}: {info['message']}",
                    'rule': info['rule_name'],
                    'expected': info['expected'],
                    'found': info['found']
                })
    
    def _print_preflight_summary(self, preflight_result):
        """프리플라이트 결과 요약 출력"""
        print(f"\n📋 프리플라이트 검사 결과 ({preflight_result['profile']})")
        print("=" * 50)
        
        status = preflight_result['overall_status']
        if status == 'pass':
            print("✅ 상태: 통과 - 인쇄 준비 완료!")
        elif status == 'warning':
            print("⚠️  상태: 경고 - 확인 필요")
        else:
            print("❌ 상태: 실패 - 수정 필요")
        
        print(f"\n• 통과: {len(preflight_result['passed'])}개 항목")
        print(f"• 실패: {len(preflight_result['failed'])}개 항목")
        print(f"• 경고: {len(preflight_result['warnings'])}개 항목")
        print(f"• 정보: {len(preflight_result.get('info', []))}개 항목")
        
        if preflight_result['failed']:
            print("\n[실패 항목]")
            for failed in preflight_result['failed'][:3]:
                print(f"  ❌ {failed['rule_name']}: {failed['message']}")
            if len(preflight_result['failed']) > 3:
                print(f"  ... 그 외 {len(preflight_result['failed'])-3}개")
        
        if preflight_result['auto_fixable']:
            print(f"\n💡 {len(preflight_result['auto_fixable'])}개 항목은 자동 수정 가능합니다")
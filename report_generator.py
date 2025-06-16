# report_generator.py - 분석 결과를 보고서로 만드는 파일입니다
# Phase 2.5: 프리플라이트와 고급 검사 결과를 포함한 보고서 생성
# 2024.12 개선: 문제 유형별로 그룹화하여 한눈에 보기 쉽게 표시
# 2025.01 추가: 자동 수정 전후 비교 보고서 기능
# 2025.01 개선: 상단 요약, 다열 레이아웃, 페이지 크기 상세 정보

"""
report_generator.py - 분석 결과 보고서 생성
Phase 2.5: 프리플라이트 검사 결과와 고급 인쇄 품질 정보 추가
문제 유형별 그룹화로 가독성 개선
자동 수정 전후 비교 기능 추가
상단 요약 및 다열 레이아웃 개선
"""

from pathlib import Path
from datetime import datetime
from config import Config
from utils import format_datetime, get_severity_color, truncate_text
import json
import fitz  # PyMuPDF - 썸네일 생성용
import base64
from io import BytesIO
from collections import defaultdict

class ReportGenerator:
    """분석 결과를 읽기 쉬운 보고서로 만드는 클래스"""
    
    def __init__(self):
        self.config = Config()
    
    def generate_reports(self, analysis_result, format_type='both'):
        """
        보고서 생성 메인 메서드
        
        Args:
            analysis_result: PDFAnalyzer의 분석 결과
            format_type: 'text', 'html', 또는 'both'
            
        Returns:
            dict: 생성된 보고서 경로들
        """
        report_paths = {}
        
        if format_type in ['text', 'both']:
            text_path = self.save_text_report(analysis_result)
            report_paths['text'] = text_path
        
        if format_type in ['html', 'both']:
            html_path = self.save_html_report(analysis_result)
            report_paths['html'] = html_path
        
        return report_paths
    
    def create_pdf_thumbnail(self, pdf_path, max_width=300, page_num=0):
        """
        PDF 첫 페이지의 썸네일 생성
        
        Args:
            pdf_path: PDF 파일 경로
            max_width: 썸네일 최대 너비 (픽셀)
            page_num: 썸네일로 만들 페이지 번호 (0부터 시작)
            
        Returns:
            str: Base64 인코딩된 이미지 데이터 URL
        """
        try:
            # PDF 열기
            doc = fitz.open(pdf_path)
            
            # 페이지 가져오기
            if page_num >= len(doc):
                page_num = 0
            page = doc[page_num]
            
            # 썸네일 크기 계산
            rect = page.rect
            zoom = max_width / rect.width
            mat = fitz.Matrix(zoom, zoom)
            
            # 페이지를 이미지로 렌더링
            pix = page.get_pixmap(matrix=mat, alpha=False)
            
            # PNG 형식으로 변환
            img_data = pix.tobytes("png")
            
            # Base64로 인코딩
            img_base64 = base64.b64encode(img_data).decode()
            
            # 페이지 수 정보 저장
            total_pages = len(doc)
            
            doc.close()
            
            # 데이터 URL 형식으로 반환
            return {
                'data_url': f"data:image/png;base64,{img_base64}",
                'page_shown': page_num + 1,
                'total_pages': total_pages
            }
            
        except Exception as e:
            print(f"썸네일 생성 실패: {e}")
            # 실패 시 빈 이미지 데이터 반환
            return {
                'data_url': '',
                'page_shown': 0,
                'total_pages': 0
            }
    
    def create_page_preview(self, pdf_path, page_num, max_width=200):
        """
        특정 페이지의 미리보기 생성
        
        Args:
            pdf_path: PDF 파일 경로
            page_num: 페이지 번호 (0부터 시작)
            max_width: 미리보기 최대 너비 (픽셀)
            
        Returns:
            str: Base64 인코딩된 이미지 데이터 URL
        """
        try:
            doc = fitz.open(pdf_path)
            
            if page_num >= len(doc):
                return None
                
            page = doc[page_num]
            
            # 미리보기 크기 계산
            rect = page.rect
            zoom = max_width / rect.width
            mat = fitz.Matrix(zoom, zoom)
            
            # 페이지를 이미지로 렌더링
            pix = page.get_pixmap(matrix=mat, alpha=False)
            
            # PNG 형식으로 변환
            img_data = pix.tobytes("png")
            
            # Base64로 인코딩
            img_base64 = base64.b64encode(img_data).decode()
            
            doc.close()
            
            return f"data:image/png;base64,{img_base64}"
            
        except Exception as e:
            print(f"페이지 미리보기 생성 실패: {e}")
            return None
    
    def get_error_summary(self, analysis_result):
        """
        주요 오류 요약 정보 생성
        
        Args:
            analysis_result: 분석 결과
            
        Returns:
            list: 주요 오류 요약 리스트
        """
        issues = analysis_result.get('issues', [])
        errors = [i for i in issues if i['severity'] == 'error']
        
        summary = []
        
        # 오류 유형별 집계
        error_types = {}
        for error in errors:
            error_type = error.get('type', 'unknown')
            if error_type not in error_types:
                error_types[error_type] = 0
            error_types[error_type] += 1
        
        # 주요 오류 요약 (최대 3개)
        type_info_map = {
            'font_not_embedded': '폰트 미임베딩',
            'high_ink_coverage': '잉크량 초과',
            'low_resolution_image': '저해상도 이미지',
            'insufficient_bleed': '재단여백 부족',
            'preflight_failed': '프리플라이트 실패'
        }
        
        for error_type, count in sorted(error_types.items(), key=lambda x: x[1], reverse=True)[:3]:
            type_name = type_info_map.get(error_type, error_type)
            summary.append(f"{type_name} ({count}건)")
        
        return summary
    
    def group_issues_by_type(self, analysis_result):
        """
        문제점들을 유형별로 그룹화
        
        Args:
            analysis_result: 분석 결과
            
        Returns:
            dict: 유형별로 그룹화된 문제점
        """
        type_groups = defaultdict(list)
        
        # 모든 이슈 수집
        issues = analysis_result.get('issues', [])
        
        # 우선순위 정의 (표시 순서)
        type_priority = {
            'font_not_embedded': 1,
            'high_ink_coverage': 2,
            'low_resolution_image': 3,
            'insufficient_bleed': 4,
            'page_size_inconsistent': 5,
            'spot_colors': 6,
            'transparency_detected': 7,
            'overprint_detected': 8,
            'small_text_detected': 9,
            'high_compression_detected': 10,
            'rgb_only': 11,
            'medium_resolution_image': 12,
            'preflight_failed': 13,
            'preflight_warning': 14,
            'preflight_info': 15
        }
        
        # 유형별로 그룹화
        for issue in issues:
            issue_type = issue.get('type', 'unknown')
            type_groups[issue_type].append(issue)
        
        # 우선순위에 따라 정렬
        sorted_groups = dict(sorted(
            type_groups.items(),
            key=lambda x: type_priority.get(x[0], 999)
        ))
        
        return sorted_groups
    
    def format_page_list(self, pages, max_display=10):
        """
        페이지 리스트를 읽기 쉬운 형식으로 변환
        
        Args:
            pages: 페이지 번호 리스트
            max_display: 최대 표시 개수
            
        Returns:
            str: 포맷된 페이지 리스트
        """
        if not pages:
            return ""
        
        pages = sorted(set(pages))
        
        if len(pages) == 1:
            return f"{pages[0]}페이지"
        elif len(pages) <= max_display:
            return f"{', '.join(map(str, pages))} 페이지"
        else:
            # 연속된 페이지를 범위로 표시
            ranges = []
            start = pages[0]
            end = pages[0]
            
            for i in range(1, len(pages)):
                if pages[i] == end + 1:
                    end = pages[i]
                else:
                    if start == end:
                        ranges.append(str(start))
                    else:
                        ranges.append(f"{start}-{end}")
                    start = pages[i]
                    end = pages[i]
            
            # 마지막 범위 추가
            if start == end:
                ranges.append(str(start))
            else:
                ranges.append(f"{start}-{end}")
            
            # 범위가 너무 많으면 요약
            if len(ranges) > 5:
                return f"{ranges[0]}, {ranges[1]}, ... {ranges[-1]} ({len(pages)}개 페이지)"
            else:
                return f"{', '.join(ranges)} 페이지"
    
    def get_issue_type_info(self, issue_type):
        """
        이슈 타입에 대한 표시 정보 반환
        
        Args:
            issue_type: 이슈 타입
            
        Returns:
            dict: 제목, 아이콘 등의 정보
        """
        type_info = {
            'font_not_embedded': {
                'title': '폰트 미임베딩',
                'icon': '🔤',
                'color': '#e74c3c'
            },
            'high_ink_coverage': {
                'title': '잉크량 초과',
                'icon': '💧',
                'color': '#e74c3c'
            },
            'low_resolution_image': {
                'title': '저해상도 이미지',
                'icon': '🖼️',
                'color': '#e74c3c'
            },
            'medium_resolution_image': {
                'title': '중간해상도 이미지',
                'icon': '🖼️',
                'color': '#3498db'
            },
            'insufficient_bleed': {
                'title': '재단 여백 부족',
                'icon': '📐',
                'color': '#3498db'
            },
            'page_size_inconsistent': {
                'title': '페이지 크기 불일치',
                'icon': '📄',
                'color': '#f39c12'
            },
            'spot_colors': {
                'title': '별색 사용',
                'icon': '🎨',
                'color': '#3498db'
            },
            'transparency_detected': {
                'title': '투명도 사용',
                'icon': '👻',
                'color': '#f39c12'
            },
            'overprint_detected': {
                'title': '중복인쇄 설정',
                'icon': '🔄',
                'color': '#3498db'
            },
            'small_text_detected': {
                'title': '작은 텍스트',
                'icon': '🔍',
                'color': '#f39c12'
            },
            'high_compression_detected': {
                'title': '과도한 이미지 압축',
                'icon': '🗜️',
                'color': '#f39c12'
            },
            'rgb_only': {
                'title': 'RGB 색상만 사용',
                'icon': '🌈',
                'color': '#f39c12'
            },
            'preflight_failed': {
                'title': '프리플라이트 실패',
                'icon': '❌',
                'color': '#e74c3c'
            },
            'preflight_warning': {
                'title': '프리플라이트 경고',
                'icon': '⚠️',
                'color': '#f39c12'
            },
            'preflight_info': {
                'title': '프리플라이트 정보',
                'icon': 'ℹ️',
                'color': '#3498db'
            }
        }
        
        return type_info.get(issue_type, {
            'title': '기타 문제',
            'icon': 'ℹ️',
            'color': '#95a5a6'
        })
    
    def get_severity_info(self, severity):
        """
        심각도별 정보 반환 (5단계 체계)
        
        Args:
            severity: 심각도
            
        Returns:
            dict: 심각도 정보
        """
        severity_info = {
            'critical': {
                'name': 'CRITICAL',
                'color': '#8b0000',
                'icon': '🚫'
            },
            'error': {
                'name': 'ERROR',
                'color': '#dc3545',
                'icon': '❌'
            },
            'warning': {
                'name': 'WARNING',
                'color': '#ffc107',
                'icon': '⚠️'
            },
            'info': {
                'name': 'INFO',
                'color': '#007bff',
                'icon': 'ℹ️'
            },
            'ok': {
                'name': 'OK',
                'color': '#28a745',
                'icon': '✅'
            }
        }
        
        return severity_info.get(severity, severity_info['info'])
    
    def format_fix_comparison(self, fix_comparison):
        """
        수정 전후 비교 데이터를 보고서용으로 포맷
        
        Args:
            fix_comparison: 수정 전후 비교 데이터
            
        Returns:
            dict: 포맷된 비교 데이터
        """
        if not fix_comparison:
            return None
        
        before = fix_comparison.get('before', {})
        after = fix_comparison.get('after', {})
        modifications = fix_comparison.get('modifications', [])
        
        # 주요 변경사항 추출
        changes = []
        
        # 폰트 변경 확인
        before_fonts = before.get('fonts', {})
        after_fonts = after.get('fonts', {})
        before_not_embedded = sum(1 for f in before_fonts.values() if not f.get('embedded', False))
        after_not_embedded = sum(1 for f in after_fonts.values() if not f.get('embedded', False))
        
        if before_not_embedded > 0 and after_not_embedded == 0:
            changes.append({
                'type': 'font',
                'before': f"{before_not_embedded}개 폰트 미임베딩",
                'after': "모든 폰트 임베딩됨",
                'status': 'fixed'
            })
        
        # 색상 모드 변경 확인
        before_colors = before.get('colors', {})
        after_colors = after.get('colors', {})
        
        if before_colors.get('has_rgb') and not after_colors.get('has_rgb'):
            changes.append({
                'type': 'color',
                'before': "RGB 색상 사용",
                'after': "CMYK 색상으로 변환됨",
                'status': 'fixed'
            })
        
        # 이슈 개수 비교
        before_issues = before.get('issues', [])
        after_issues = after.get('issues', [])
        before_errors = sum(1 for i in before_issues if i['severity'] == 'error')
        after_errors = sum(1 for i in after_issues if i['severity'] == 'error')
        
        return {
            'modifications': modifications,
            'changes': changes,
            'before_errors': before_errors,
            'after_errors': after_errors,
            'fixed_count': before_errors - after_errors
        }
    
    def generate_text_report(self, analysis_result):
        """
        텍스트 형식의 보고서 생성 - 문제 유형별 그룹화 + 자동 수정 결과
        
        Args:
            analysis_result: PDFAnalyzer의 분석 결과
            
        Returns:
            str: 보고서 내용
        """
        # 오류가 있는 경우
        if 'error' in analysis_result:
            return f"분석 실패: {analysis_result['error']}"
        
        # 보고서 헤더
        report = []
        report.append("=" * 70)
        report.append("PDF 품질 검수 보고서 (Phase 2.5)")
        report.append("=" * 70)
        report.append(f"생성 일시: {format_datetime()}")
        report.append(f"파일명: {analysis_result['filename']}")
        report.append(f"파일 크기: {analysis_result.get('file_size_formatted', 'N/A')}")
        report.append(f"프리플라이트 프로파일: {analysis_result.get('preflight_profile', 'N/A')}")
        report.append(f"분석 소요시간: {analysis_result.get('analysis_time', 'N/A')}")
        
        # 첫 페이지 정보 추가 (2025.01)
        pages = analysis_result.get('pages', [])
        if pages:
            first_page = pages[0]
            report.append(f"첫 페이지 크기: {first_page['size_formatted']} ({first_page['paper_size']})")
            if first_page.get('rotation', 0) != 0:
                report.append(f"  - {first_page['rotation']}° 회전됨")
        
        # 자동 수정 정보 (있는 경우)
        if 'auto_fix_applied' in analysis_result:
            report.append("")
            report.append("🔧 자동 수정 적용됨")
            report.append("-" * 50)
            for mod in analysis_result['auto_fix_applied']:
                report.append(f"  • {mod}")
        
        report.append("")
        
        # 주요 오류 요약 (2025.01)
        error_summary = self.get_error_summary(analysis_result)
        if error_summary:
            report.append("❗ 주요 오류 요약")
            report.append("-" * 50)
            for summary in error_summary:
                report.append(f"  • {summary}")
            report.append("")
        
        # 프리플라이트 결과 요약
        preflight = analysis_result.get('preflight_result', {})
        if preflight:
            report.append("🎯 프리플라이트 검사 결과")
            report.append("-" * 50)
            
            status = preflight.get('overall_status', 'unknown')
            if status == 'pass':
                report.append("  ✅ 상태: 통과 - 인쇄 준비 완료!")
            elif status == 'warning':
                report.append("  ⚠️  상태: 경고 - 확인 필요")
            else:
                report.append("  ❌ 상태: 실패 - 수정 필요")
            
            report.append(f"  • 통과: {len(preflight.get('passed', []))}개 항목")
            report.append(f"  • 실패: {len(preflight.get('failed', []))}개 항목")
            report.append(f"  • 경고: {len(preflight.get('warnings', []))}개 항목")
            report.append(f"  • 정보: {len(preflight.get('info', []))}개 항목")
            
            if preflight.get('auto_fixable'):
                report.append(f"  • 자동 수정 가능: {len(preflight['auto_fixable'])}개 항목")
            report.append("")
        
        # 기본 정보
        basic = analysis_result['basic_info']
        report.append("📋 기본 정보")
        report.append("-" * 50)
        report.append(f"  • 총 페이지 수: {basic['page_count']}페이지")
        report.append(f"  • PDF 버전: {basic['pdf_version']}")
        report.append(f"  • 제목: {basic['title'] or '(없음)'}")
        report.append(f"  • 작성자: {basic['author'] or '(없음)'}")
        report.append(f"  • 생성 프로그램: {basic['creator'] or '(없음)'}")
        report.append(f"  • PDF 생성기: {basic['producer'] or '(없음)'}")
        if basic.get('is_linearized'):
            report.append(f"  • 웹 최적화: ✓")
        report.append("")
        
        # 수정 전후 비교 (있는 경우)
        if 'fix_comparison' in analysis_result:
            comparison = self.format_fix_comparison(analysis_result['fix_comparison'])
            if comparison:
                report.append("📊 자동 수정 결과")
                report.append("=" * 70)
                report.append(f"수정 전 오류: {comparison['before_errors']}개 → 수정 후 오류: {comparison['after_errors']}개")
                report.append(f"해결된 문제: {comparison['fixed_count']}개")
                report.append("")
                
                if comparison['changes']:
                    report.append("변경 내역:")
                    for change in comparison['changes']:
                        report.append(f"  • {change['type'].upper()}: {change['before']} → {change['after']}")
                report.append("")
        
        # 문제 유형별 요약
        type_groups = self.group_issues_by_type(analysis_result)
        
        if type_groups:
            report.append("🚨 발견된 문제점 (유형별)")
            report.append("=" * 70)
            
            for issue_type, issues in type_groups.items():
                if not issues:
                    continue
                
                type_info = self.get_issue_type_info(issue_type)
                report.append(f"\n{type_info['icon']} [{type_info['title']}]")
                report.append("-" * 50)
                
                # 첫 번째 이슈를 대표로 사용
                main_issue = issues[0]
                
                # 영향받는 모든 페이지 수집
                all_pages = []
                for issue in issues:
                    if 'affected_pages' in issue:
                        all_pages.extend(issue['affected_pages'])
                    elif 'pages' in issue:
                        all_pages.extend(issue['pages'])
                    elif 'page' in issue and issue['page']:
                        all_pages.append(issue['page'])
                
                all_pages = sorted(set(all_pages))
                
                # 기본 메시지
                report.append(f"상태: {main_issue['message']}")
                
                # 영향받는 페이지
                if all_pages:
                    page_str = self.format_page_list(all_pages)
                    report.append(f"영향 페이지: {page_str}")
                
                # 추가 정보
                if issue_type == 'font_not_embedded' and 'fonts' in main_issue:
                    report.append(f"문제 폰트 ({len(main_issue['fonts'])}개):")
                    for font in main_issue['fonts'][:5]:
                        report.append(f"  - {font}")
                    if len(main_issue['fonts']) > 5:
                        report.append(f"  ... 그 외 {len(main_issue['fonts']) - 5}개")
                
                elif issue_type == 'low_resolution_image' and 'min_dpi' in main_issue:
                    report.append(f"최저 해상도: {main_issue['min_dpi']:.0f} DPI")
                
                elif issue_type == 'page_size_inconsistent' and 'page_details' in main_issue:
                    report.append(f"기준 크기: {main_issue['base_size']} ({main_issue['base_paper']})")
                    report.append("다른 크기 페이지:")
                    for detail in main_issue['page_details'][:5]:
                        rotation_info = f" - {detail['rotation']}° 회전" if detail['rotation'] != 0 else ""
                        report.append(f"  - {detail['page']}페이지: {detail['size']} ({detail['paper_size']}){rotation_info}")
                    if len(main_issue['page_details']) > 5:
                        report.append(f"  ... 그 외 {len(main_issue['page_details']) - 5}개")
                
                elif issue_type == 'insufficient_bleed':
                    report.append(f"현재: 0mm / 필요: {Config.STANDARD_BLEED_SIZE}mm")
                
                elif issue_type == 'high_ink_coverage':
                    report.append(f"권장: {Config.MAX_INK_COVERAGE}% 이하")
                
                elif issue_type == 'spot_colors' and 'spot_colors' in main_issue:
                    report.append(f"별색 목록:")
                    for color in main_issue['spot_colors'][:5]:
                        report.append(f"  - {color}")
                    if len(main_issue['spot_colors']) > 5:
                        report.append(f"  ... 그 외 {len(main_issue['spot_colors']) - 5}개")
                
                # 해결 방법
                if 'suggestion' in main_issue:
                    report.append(f"💡 해결방법: {main_issue['suggestion']}")
                    
                    # 자동 수정 가능 표시
                    if issue_type == 'font_not_embedded':
                        report.append("   → 자동 수정 가능: 폰트 아웃라인 변환")
                    elif issue_type == 'rgb_only':
                        report.append("   → 자동 수정 가능: RGB→CMYK 변환")
            
            report.append("")
        else:
            report.append("\n✅ 발견된 문제점이 없습니다!")
            report.append("")
        
        # 통계 정보
        report.append("📊 전체 통계")
        report.append("-" * 50)
        
        # 페이지 크기 통계
        size_groups = {}
        for page in pages:
            size_key = f"{page['size_formatted']} ({page['paper_size']})"
            if page.get('rotation', 0) != 0:
                size_key += f" - {page['rotation']}° 회전"
            if size_key not in size_groups:
                size_groups[size_key] = []
            size_groups[size_key].append(page['page_number'])
        
        report.append(f"  • 페이지 크기: {len(size_groups)}종")
        for size_key, page_nums in size_groups.items():
            report.append(f"    - {size_key}: {len(page_nums)}페이지")
        
        # 폰트 통계
        fonts = analysis_result['fonts']
        not_embedded = sum(1 for f in fonts.values() if not f.get('embedded', False))
        report.append(f"\n  • 폰트: 총 {len(fonts)}개 (미임베딩 {not_embedded}개)")
        
        # 이미지 통계
        images = analysis_result.get('images', {})
        if images.get('total_count', 0) > 0:
            report.append(f"  • 이미지: 총 {images['total_count']}개")
            
            # 해상도 분포 표시
            res_cat = images.get('resolution_categories', {})
            if res_cat:
                report.append(f"    - 최적(300 DPI↑): {res_cat.get('optimal', 0)}개")
                report.append(f"    - 양호(150-300): {res_cat.get('acceptable', 0)}개")
                report.append(f"    - 주의(72-150): {res_cat.get('warning', 0)}개")
                report.append(f"    - 위험(72 미만): {res_cat.get('critical', 0)}개")
        
        # 잉크량 통계
        ink = analysis_result.get('ink_coverage', {})
        if 'summary' in ink:
            report.append(f"  • 잉크량: 평균 {ink['summary']['avg_coverage']:.1f}%, 최대 {ink['summary']['max_coverage']:.1f}%")
        
        report.append("")
        report.append("=" * 70)
        report.append("보고서 끝")
        
        return "\n".join(report)
    
    def generate_html_report(self, analysis_result):
        """
        HTML 형식의 보고서 생성 - 상단 요약 + 다열 레이아웃 + 자동 수정 결과
        
        Args:
            analysis_result: PDFAnalyzer의 분석 결과
            
        Returns:
            str: HTML 보고서 내용
        """
        # 오류가 있는 경우
        if 'error' in analysis_result:
            return f"""
            <html>
            <body style="font-family: sans-serif; padding: 20px;">
                <h1 style="color: #e74c3c;">PDF 분석 실패</h1>
                <p>오류: {analysis_result['error']}</p>
            </body>
            </html>
            """
        
        # PDF 썸네일 생성
        pdf_path = analysis_result.get('file_path', '')
        thumbnail_data = {'data_url': '', 'page_shown': 0, 'total_pages': 0}
        if pdf_path and Path(pdf_path).exists():
            thumbnail_data = self.create_pdf_thumbnail(pdf_path)
        
        # 문제 유형별로 그룹화
        type_groups = self.group_issues_by_type(analysis_result)
        
        # 프리플라이트 결과 확인
        preflight = analysis_result.get('preflight_result', {})
        preflight_status = preflight.get('overall_status', 'unknown')
        
        # 문제점 분류
        issues = analysis_result.get('issues', [])
        error_count = sum(1 for i in issues if i['severity'] == 'error')
        warning_count = sum(1 for i in issues if i['severity'] == 'warning')
        info_count = sum(1 for i in issues if i['severity'] == 'info')
        
        # 전체 상태 결정
        if preflight_status == 'fail' or error_count > 0:
            overall_status = 'error'
            status_text = '수정 필요'
            status_color = '#ef4444'
            status_icon = '❌'
        elif preflight_status == 'warning' or warning_count > 0:
            overall_status = 'warning'
            status_text = '확인 필요'
            status_color = '#f59e0b'
            status_icon = '⚠️'
        else:
            overall_status = 'success'
            status_text = '인쇄 준비 완료'
            status_color = '#10b981'
            status_icon = '✅'
        
        # 자동 수정이 적용된 경우 상태 업데이트
        if 'auto_fix_applied' in analysis_result:
            status_text = '자동 수정 완료'
            status_icon = '🔧'
        
        # 페이지 정보
        pages = analysis_result.get('pages', [])
        first_page = pages[0] if pages else None
        
        # 주요 오류 요약
        error_summary = self.get_error_summary(analysis_result)
        
        # 페이지 크기 통계 계산
        size_groups = {}
        for page in pages:
            size_key = f"{page['size_formatted']} ({page['paper_size']})"
            if size_key not in size_groups:
                size_groups[size_key] = []
            size_groups[size_key].append(page['page_number'])
        
        # HTML 템플릿 생성
        html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PDF 품질 검수 보고서 - {analysis_result['filename']}</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: 'Segoe UI', 'Malgun Gothic', sans-serif;
            background: #f8f9fa;
            color: #212529;
            line-height: 1.6;
        }}
        
        /* 라이트 테마 변수 */
        :root {{
            --bg-primary: #ffffff;
            --bg-secondary: #f8f9fa;
            --bg-card: #ffffff;
            --text-primary: #212529;
            --text-secondary: #6c757d;
            --accent-green: #28a745;
            --accent-yellow: #ffc107;
            --accent-red: #dc3545;
            --accent-blue: #007bff;
            --border: #dee2e6;
        }}
        
        /* 헤더 */
        .header {{
            background: var(--bg-primary);
            border-bottom: 2px solid var(--border);
            padding: 1.5rem 2rem;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        
        .header-content {{
            max-width: 1400px;
            margin: 0 auto;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        
        .header-title {{
            display: flex;
            align-items: center;
            gap: 1rem;
        }}
        
        .header-title h1 {{
            font-size: 1.75rem;
            font-weight: 600;
            color: var(--text-primary);
        }}
        
        .logo-icon {{
            width: 48px;
            height: 48px;
            background: linear-gradient(135deg, #007bff 0%, #6610f2 100%);
            border-radius: 12px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.5rem;
            color: white;
        }}
        
        .header-meta {{
            display: flex;
            flex-direction: column;
            align-items: flex-end;
            gap: 0.25rem;
            font-size: 0.875rem;
            color: var(--text-secondary);
        }}
        
        /* 메인 컨테이너 */
        .container {{
            max-width: 1400px;
            margin: 2rem auto;
            padding: 0 2rem;
        }}
        
        /* 상태 배너 개선 - 상단 요약 추가 */
        .status-banner {{
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 2rem;
            margin-bottom: 2rem;
            box-shadow: 0 2px 4px rgba(0,0,0,0.05);
            display: flex;
            gap: 2rem;
        }}
        
        .status-content {{
            flex: 1;
        }}
        
        .status-header {{
            display: flex;
            align-items: center;
            gap: 1rem;
            margin-bottom: 1rem;
        }}
        
        .status-icon {{
            font-size: 3rem;
        }}
        
        .status-text h2 {{
            font-size: 2rem;
            color: {status_color};
            margin-bottom: 0.25rem;
        }}
        
        .status-text p {{
            color: var(--text-secondary);
        }}
        
        /* 빠른 요약 섹션 */
        .quick-summary {{
            background: var(--bg-secondary);
            border-radius: 6px;
            padding: 1rem;
            margin-top: 1rem;
        }}
        
        .quick-summary h4 {{
            font-size: 0.875rem;
            color: var(--text-secondary);
            margin-bottom: 0.5rem;
        }}
        
        .summary-grid {{
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 0.75rem;
        }}
        
        .summary-item {{
            display: flex;
            align-items: center;
            gap: 0.5rem;
            font-size: 0.875rem;
        }}
        
        .summary-item-icon {{
            width: 20px;
            height: 20px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 0.75rem;
        }}
        
        .summary-item-icon.error {{
            background: rgba(220, 53, 69, 0.1);
            color: var(--accent-red);
        }}
        
        .summary-item-icon.info {{
            background: rgba(0, 123, 255, 0.1);
            color: var(--accent-blue);
        }}
        
        /* PDF 썸네일 */
        .pdf-thumbnail {{
            width: 200px;
            background: var(--bg-secondary);
            border-radius: 8px;
            padding: 1rem;
            text-align: center;
            border: 1px solid var(--border);
        }}
        
        .thumbnail-image {{
            width: 100%;
            border-radius: 4px;
            margin-bottom: 0.5rem;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
        }}
        
        .thumbnail-placeholder {{
            width: 100%;
            height: 260px;
            background: var(--bg-secondary);
            border: 2px dashed var(--border);
            border-radius: 4px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 3rem;
            color: var(--text-secondary);
            margin-bottom: 0.5rem;
        }}
        
        .page-indicator {{
            font-size: 0.875rem;
            color: var(--text-secondary);
        }}
        
        /* 자동 수정 알림 */
        .auto-fix-banner {{
            background: #d4edda;
            border: 1px solid #c3e6cb;
            border-radius: 6px;
            padding: 1rem;
            margin-bottom: 1rem;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }}
        
        .auto-fix-banner .icon {{
            font-size: 1.5rem;
        }}
        
        .auto-fix-banner .content {{
            flex: 1;
        }}
        
        .auto-fix-banner .title {{
            font-weight: 600;
            color: #155724;
            margin-bottom: 0.25rem;
        }}
        
        .auto-fix-banner .modifications {{
            color: #155724;
            font-size: 0.875rem;
        }}
        
        /* 수정 전후 비교 섹션 */
        .comparison-section {{
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 2rem;
            margin-bottom: 2rem;
            box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        }}
        
        .comparison-header {{
            display: flex;
            align-items: center;
            gap: 1rem;
            margin-bottom: 1.5rem;
            padding-bottom: 1rem;
            border-bottom: 2px solid var(--border);
        }}
        
        .comparison-content {{
            display: grid;
            grid-template-columns: 1fr auto 1fr;
            gap: 2rem;
            align-items: center;
        }}
        
        .before-after {{
            text-align: center;
        }}
        
        .before-after h4 {{
            color: var(--text-secondary);
            margin-bottom: 0.5rem;
        }}
        
        .metric {{
            font-size: 2.5rem;
            font-weight: 700;
            margin-bottom: 0.5rem;
        }}
        
        .metric.error {{
            color: var(--accent-red);
        }}
        
        .metric.success {{
            color: var(--accent-green);
        }}
        
        .arrow {{
            font-size: 2rem;
            color: var(--accent-green);
        }}
        
        .change-list {{
            margin-top: 1.5rem;
            padding: 1rem;
            background: var(--bg-secondary);
            border-radius: 4px;
        }}
        
        .change-item {{
            display: flex;
            align-items: center;
            gap: 0.5rem;
            padding: 0.5rem 0;
            border-bottom: 1px solid var(--border);
        }}
        
        .change-item:last-child {{
            border-bottom: none;
        }}
        
        .change-item .icon {{
            color: var(--accent-green);
        }}
        
        /* 통계 카드 그리드 */
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 1.5rem;
            margin-bottom: 2rem;
        }}
        
        .stat-card {{
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 1.5rem;
            box-shadow: 0 2px 4px rgba(0,0,0,0.05);
            transition: all 0.3s;
        }}
        
        .stat-card:hover {{
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(0,0,0,0.1);
        }}
        
        .stat-card.success {{ border-left: 4px solid var(--accent-green); }}
        .stat-card.warning {{ border-left: 4px solid var(--accent-yellow); }}
        .stat-card.error {{ border-left: 4px solid var(--accent-red); }}
        .stat-card.info {{ border-left: 4px solid var(--accent-blue); }}
        
        .stat-header {{
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 0.5rem;
        }}
        
        .stat-label {{
            color: var(--text-secondary);
            font-size: 0.875rem;
            font-weight: 500;
        }}
        
        .stat-icon {{
            font-size: 1.5rem;
            opacity: 0.8;
        }}
        
        .stat-value {{
            font-size: 2rem;
            font-weight: 700;
            color: var(--text-primary);
            margin-bottom: 0.25rem;
        }}
        
        .stat-change {{
            font-size: 0.875rem;
            color: var(--text-secondary);
        }}
        
        /* 문제 유형별 섹션 - 다열 레이아웃 개선 */
        .issues-by-type-section {{
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 2rem;
            margin-bottom: 2rem;
            box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        }}
        
        .section-header {{
            display: flex;
            align-items: center;
            gap: 1rem;
            margin-bottom: 1.5rem;
            padding-bottom: 1rem;
            border-bottom: 2px solid var(--border);
        }}
        
        .section-icon {{
            font-size: 1.5rem;
            color: var(--accent-blue);
        }}
        
        .section-title {{
            font-size: 1.5rem;
            font-weight: 600;
            color: var(--text-primary);
        }}
        
        /* 문제 유형 그리드 - 다열 레이아웃 */
        .issues-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 1rem;
        }}
        
        /* 문제 유형 카드 */
        .issue-type-card {{
            background: var(--bg-secondary);
            border: 1px solid var(--border);
            border-radius: 6px;
            padding: 1.5rem;
            transition: all 0.2s;
            height: 100%;
            display: flex;
            flex-direction: column;
        }}
        
        .issue-type-card:hover {{
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }}
        
        .issue-type-header {{
            display: flex;
            align-items: center;
            gap: 1rem;
            margin-bottom: 1rem;
        }}
        
        .issue-type-icon {{
            font-size: 2rem;
        }}
        
        .issue-type-title {{
            font-size: 1.25rem;
            font-weight: 600;
            color: var(--text-primary);
            flex: 1;
        }}
        
        .issue-type-severity {{
            padding: 0.25rem 0.75rem;
            border-radius: 12px;
            font-size: 0.75rem;
            font-weight: 600;
        }}
        
        .severity-critical {{
            background: rgba(139, 0, 0, 0.1);
            color: #8b0000;
        }}
        
        .severity-error {{
            background: rgba(220, 53, 69, 0.1);
            color: var(--accent-red);
        }}
        
        .severity-warning {{
            background: rgba(255, 193, 7, 0.1);
            color: #856404;
        }}
        
        .severity-info {{
            background: rgba(0, 123, 255, 0.1);
            color: var(--accent-blue);
        }}
        
        .issue-type-content {{
            flex: 1;
            display: flex;
            flex-direction: column;
        }}
        
        .issue-info {{
            margin-bottom: 0.75rem;
            color: var(--text-secondary);
            font-size: 0.875rem;
        }}
        
        .issue-pages {{
            background: white;
            border: 1px solid var(--border);
            border-radius: 4px;
            padding: 0.75rem;
            margin: 0.5rem 0;
            font-size: 0.875rem;
        }}
        
        .issue-suggestion {{
            background: rgba(0, 123, 255, 0.05);
            border-left: 3px solid var(--accent-blue);
            padding: 0.75rem;
            margin-top: auto;
            font-size: 0.875rem;
            color: var(--text-primary);
        }}
        
        .auto-fixable {{
            background: rgba(40, 167, 69, 0.05);
            border-left: 3px solid var(--accent-green);
            padding: 0.5rem;
            margin-top: 0.5rem;
            font-size: 0.875rem;
            color: #155724;
        }}
        
        .font-list, .color-list, .page-detail-list {{
            list-style: none;
            padding: 0;
            margin: 0.5rem 0;
        }}
        
        .font-list li, .color-list li, .page-detail-list li {{
            padding: 0.25rem 0;
            font-family: monospace;
            font-size: 0.875rem;
            color: var(--text-secondary);
        }}
        
        /* 상세 정보 섹션 */
        .details-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 2rem;
            margin-top: 2rem;
        }}
        
        .detail-card {{
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 1.5rem;
            box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        }}
        
        .detail-header {{
            display: flex;
            align-items: center;
            gap: 0.5rem;
            margin-bottom: 1rem;
            font-weight: 600;
            color: var(--text-primary);
        }}
        
        .info-grid {{
            display: grid;
            gap: 0.5rem;
        }}
        
        .info-row {{
            display: flex;
            justify-content: space-between;
            padding: 0.5rem 0;
            border-bottom: 1px solid var(--bg-secondary);
        }}
        
        .info-label {{
            color: var(--text-secondary);
            font-size: 0.875rem;
        }}
        
        .info-value {{
            color: var(--text-primary);
            font-weight: 500;
            text-align: right;
        }}
        
        /* 액션 버튼 */
        .action-buttons {{
            display: flex;
            gap: 1rem;
            margin-top: 2rem;
            padding-top: 2rem;
            border-top: 2px solid var(--border);
        }}
        
        .btn {{
            padding: 0.75rem 1.5rem;
            border: none;
            border-radius: 6px;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.2s;
            display: flex;
            align-items: center;
            gap: 0.5rem;
            text-decoration: none;
        }}
        
        .btn-primary {{
            background: var(--accent-blue);
            color: white;
        }}
        
        .btn-primary:hover {{
            background: #0056b3;
            transform: translateY(-1px);
            box-shadow: 0 4px 8px rgba(0, 123, 255, 0.2);
        }}
        
        .btn-secondary {{
            background: var(--bg-secondary);
            color: var(--text-primary);
            border: 1px solid var(--border);
        }}
        
        .btn-secondary:hover {{
            background: var(--border);
        }}
        
        /* 프린트 스타일 */
        @media print {{
            body {{
                background: white;
                color: black;
            }}
            
            .header {{
                display: none;
            }}
            
            .btn {{
                display: none;
            }}
            
            .issue-type-card {{
                break-inside: avoid;
            }}
            
            .issues-grid {{
                grid-template-columns: 1fr;
            }}
        }}
        
        /* 반응형 */
        @media (max-width: 768px) {{
            .header-content {{
                flex-direction: column;
                align-items: flex-start;
                gap: 1rem;
            }}
            
            .status-banner {{
                flex-direction: column;
            }}
            
            .stats-grid {{
                grid-template-columns: 1fr;
            }}
            
            .issues-grid {{
                grid-template-columns: 1fr;
            }}
            
            .comparison-content {{
                grid-template-columns: 1fr;
                text-align: center;
            }}
            
            .arrow {{
                transform: rotate(90deg);
            }}
        }}
    </style>
</head>
<body>
    <!-- 헤더 -->
    <header class="header">
        <div class="header-content">
            <div class="header-title">
                <div class="logo-icon">📊</div>
                <h1>PDF 품질 검수 리포트</h1>
            </div>
            <div class="header-meta">
                <span>📅 {format_datetime()}</span>
                <span>🎯 프로파일: {analysis_result.get('preflight_profile', 'N/A')}</span>
            </div>
        </div>
    </header>
    
    <div class="container">
"""

        # 자동 수정 알림 배너 (있는 경우)
        if 'auto_fix_applied' in analysis_result:
            html += f"""
        <div class="auto-fix-banner">
            <div class="icon">🔧</div>
            <div class="content">
                <div class="title">자동 수정이 적용되었습니다</div>
                <div class="modifications">
                    {', '.join(analysis_result['auto_fix_applied'])}
                </div>
            </div>
        </div>
"""

        html += f"""
        <!-- 상태 배너 -->
        <div class="status-banner">
            <div class="status-content">
                <div class="status-header">
                    <div class="status-icon">{status_icon}</div>
                    <div class="status-text">
                        <h2>{status_text}</h2>
                        <p>{analysis_result['filename']} • {analysis_result.get('file_size_formatted', 'N/A')}</p>
                    </div>
                </div>
                
                <!-- 주요 통계 -->
                <div style="display: flex; gap: 3rem; margin-top: 1.5rem;">
                    <div>
                        <div style="font-size: 2rem; font-weight: 700;">{analysis_result['basic_info']['page_count']}</div>
                        <div style="color: var(--text-secondary); font-size: 0.875rem;">총 페이지</div>
                    </div>
                    <div>
                        <div style="font-size: 2rem; font-weight: 700; color: var(--accent-red);">{error_count}</div>
                        <div style="color: var(--text-secondary); font-size: 0.875rem;">오류</div>
                    </div>
                    <div>
                        <div style="font-size: 2rem; font-weight: 700; color: var(--accent-yellow);">{warning_count}</div>
                        <div style="color: var(--text-secondary); font-size: 0.875rem;">경고</div>
                    </div>
                    <div>
                        <div style="font-size: 2rem; font-weight: 700;">{analysis_result.get('analysis_time', 'N/A')}</div>
                        <div style="color: var(--text-secondary); font-size: 0.875rem;">분석 시간</div>
                    </div>
                </div>
                
                <!-- 빠른 요약 -->
                <div class="quick-summary">
                    <h4>빠른 요약</h4>
                    <div class="summary-grid">
"""
        
        # 첫 페이지 크기 정보
        if first_page:
            rotation_info = f" ({first_page['rotation']}° 회전)" if first_page.get('rotation', 0) != 0 else ""
            html += f"""
                        <div class="summary-item">
                            <div class="summary-item-icon info">📐</div>
                            <span>페이지 크기: {first_page['size_formatted']} ({first_page['paper_size']}){rotation_info}</span>
                        </div>
"""
        
        # 주요 오류 요약
        if error_summary:
            for idx, summary in enumerate(error_summary[:3]):
                html += f"""
                        <div class="summary-item">
                            <div class="summary-item-icon error">!</div>
                            <span>{summary}</span>
                        </div>
"""
        
        html += """
                    </div>
                </div>
            </div>
            
            <!-- PDF 썸네일 -->
            <div class="pdf-thumbnail">
"""
        
        # 썸네일 추가
        if thumbnail_data['data_url']:
            html += f"""
                <img src="{thumbnail_data['data_url']}" alt="PDF 미리보기" class="thumbnail-image">
                <div class="page-indicator">{thumbnail_data['page_shown']} / {thumbnail_data['total_pages']} 페이지</div>
"""
        else:
            html += """
                <div class="thumbnail-placeholder">📄</div>
                <div class="page-indicator">미리보기 없음</div>
"""
        
        html += """
            </div>
        </div>
"""

        # 수정 전후 비교 섹션 (있는 경우)
        if 'fix_comparison' in analysis_result:
            comparison = self.format_fix_comparison(analysis_result['fix_comparison'])
            if comparison:
                html += f"""
        <!-- 수정 전후 비교 -->
        <div class="comparison-section">
            <div class="comparison-header">
                <div class="section-icon">📊</div>
                <h2 class="section-title">자동 수정 결과</h2>
            </div>
            
            <div class="comparison-content">
                <div class="before-after">
                    <h4>수정 전</h4>
                    <div class="metric error">{comparison['before_errors']}</div>
                    <div>오류</div>
                </div>
                
                <div class="arrow">→</div>
                
                <div class="before-after">
                    <h4>수정 후</h4>
                    <div class="metric success">{comparison['after_errors']}</div>
                    <div>오류</div>
                </div>
            </div>
            
            <div class="change-list">
                <h4 style="margin-bottom: 1rem;">적용된 수정 사항</h4>
"""
                for change in comparison['changes']:
                    html += f"""
                <div class="change-item">
                    <span class="icon">✓</span>
                    <strong>{change['type'].upper()}:</strong>
                    <span>{change['before']} → {change['after']}</span>
                </div>
"""
                html += """
            </div>
        </div>
"""

        # 문제 유형별 섹션 - 다열 레이아웃
        if type_groups:
            html += """
        <!-- 문제 유형별 요약 -->
        <div class="issues-by-type-section">
            <div class="section-header">
                <div class="section-icon">🚨</div>
                <h2 class="section-title">발견된 문제점 (유형별)</h2>
            </div>
            
            <div class="issues-grid">
"""
            
            for issue_type, issues in type_groups.items():
                if not issues:
                    continue
                
                type_info = self.get_issue_type_info(issue_type)
                main_issue = issues[0]
                severity = main_issue['severity']
                severity_info = self.get_severity_info(severity)
                
                # 영향받는 모든 페이지 수집
                all_pages = []
                for issue in issues:
                    if 'affected_pages' in issue:
                        all_pages.extend(issue['affected_pages'])
                    elif 'pages' in issue:
                        all_pages.extend(issue['pages'])
                    elif 'page' in issue and issue['page']:
                        all_pages.append(issue['page'])
                
                all_pages = sorted(set(all_pages))
                
                html += f"""
            <div class="issue-type-card">
                <div class="issue-type-header">
                    <div class="issue-type-icon">{type_info['icon']}</div>
                    <div class="issue-type-title">{type_info['title']}</div>
                    <div class="issue-type-severity severity-{severity}">{severity_info['name']}</div>
                </div>
                
                <div class="issue-type-content">
"""
                
                # 기본 메시지
                html += f'<div class="issue-info">{main_issue["message"]}</div>'
                
                # 영향받는 페이지
                if all_pages:
                    page_str = self.format_page_list(all_pages, max_display=20)
                    html += f'<div class="issue-pages"><strong>영향 페이지:</strong> {page_str}</div>'
                
                # 유형별 추가 정보
                if issue_type == 'font_not_embedded' and 'fonts' in main_issue:
                    html += '<div class="issue-info"><strong>문제 폰트:</strong></div>'
                    html += '<ul class="font-list">'
                    for font in main_issue['fonts'][:5]:
                        html += f'<li>• {font}</li>'
                    if len(main_issue['fonts']) > 5:
                        html += f'<li>... 그 외 {len(main_issue["fonts"]) - 5}개</li>'
                    html += '</ul>'
                
                elif issue_type == 'low_resolution_image' and 'min_dpi' in main_issue:
                    html += f'<div class="issue-info"><strong>최저 해상도:</strong> {main_issue["min_dpi"]:.0f} DPI (권장: {Config.MIN_IMAGE_DPI} DPI 이상)</div>'
                
                elif issue_type == 'page_size_inconsistent' and 'page_details' in main_issue:
                    html += f'<div class="issue-info"><strong>기준 크기:</strong> {main_issue["base_size"]} ({main_issue["base_paper"]})</div>'
                    html += '<div class="issue-info"><strong>다른 크기 페이지:</strong></div>'
                    html += '<ul class="page-detail-list">'
                    for detail in main_issue['page_details'][:3]:
                        rotation_info = f" - {detail['rotation']}° 회전" if detail['rotation'] != 0 else ""
                        html += f'<li>• {detail["page"]}p: {detail["size"]} ({detail["paper_size"]}){rotation_info}</li>'
                    if len(main_issue['page_details']) > 3:
                        html += f'<li>... 그 외 {len(main_issue["page_details"]) - 3}개</li>'
                    html += '</ul>'
                
                elif issue_type == 'insufficient_bleed':
                    html += f'<div class="issue-info"><strong>현재:</strong> 0mm / <strong>필요:</strong> {Config.STANDARD_BLEED_SIZE}mm</div>'
                
                elif issue_type == 'high_ink_coverage':
                    html += f'<div class="issue-info"><strong>권장:</strong> {Config.MAX_INK_COVERAGE}% 이하</div>'
                
                elif issue_type == 'spot_colors' and 'spot_colors' in main_issue:
                    html += '<div class="issue-info"><strong>별색 목록:</strong></div>'
                    html += '<ul class="color-list">'
                    for color in main_issue['spot_colors'][:5]:
                        pantone_badge = ' <span style="color: #e74c3c;">[PANTONE]</span>' if 'PANTONE' in color else ''
                        html += f'<li>• {color}{pantone_badge}</li>'
                    if len(main_issue['spot_colors']) > 5:
                        html += f'<li>... 그 외 {len(main_issue["spot_colors"]) - 5}개</li>'
                    html += '</ul>'
                
                elif issue_type == 'rgb_only':
                    html += '<div class="issue-info">인쇄용 PDF는 CMYK 색상 사용을 권장합니다</div>'
                
                # 해결 방법
                if 'suggestion' in main_issue:
                    html += f'<div class="issue-suggestion">💡 <strong>해결방법:</strong> {main_issue["suggestion"]}</div>'
                
                # 자동 수정 가능 표시
                if issue_type == 'font_not_embedded':
                    html += '<div class="auto-fixable">🔧 자동 수정 가능: 폰트 아웃라인 변환</div>'
                elif issue_type == 'rgb_only':
                    html += '<div class="auto-fixable">🔧 자동 수정 가능: RGB→CMYK 변환</div>'
                
                html += """
                </div>
            </div>
"""
            
            html += """
            </div>
        </div>
"""
        else:
            html += """
        <div class="issues-by-type-section">
            <div style="text-align: center; padding: 3rem; color: var(--accent-green);">
                <div style="font-size: 4rem; margin-bottom: 1rem;">✅</div>
                <h2 style="font-size: 1.5rem; margin-bottom: 0.5rem;">문제점이 발견되지 않았습니다!</h2>
                <p style="color: var(--text-secondary);">PDF가 인쇄 준비가 완료된 상태입니다.</p>
            </div>
        </div>
"""

        # 통계 카드들
        html += """
        <!-- 통계 카드 -->
        <div class="stats-grid">
"""
        
        # 페이지 일관성
        most_common_size = max(size_groups.items(), key=lambda x: len(x[1])) if size_groups else (None, [])
        page_consistency = (len(most_common_size[1]) / len(pages) * 100) if pages and most_common_size else 100
        
        html += f"""
            <div class="stat-card {'error' if page_consistency < 100 else 'success'}">
                <div class="stat-header">
                    <div class="stat-label">페이지 일관성</div>
                    <div class="stat-icon">📄</div>
                </div>
                <div class="stat-value">{page_consistency:.0f}%</div>
                <div class="stat-change">{len(size_groups)}개 크기 유형</div>
            </div>
"""
        
        # 폰트 임베딩
        fonts = analysis_result['fonts']
        embedded_fonts = sum(1 for f in fonts.values() if f.get('embedded', False))
        font_percentage = (embedded_fonts / len(fonts) * 100) if fonts else 100
        
        html += f"""
            <div class="stat-card {'error' if font_percentage < 100 else 'success'}">
                <div class="stat-header">
                    <div class="stat-label">폰트 임베딩</div>
                    <div class="stat-icon">🔤</div>
                </div>
                <div class="stat-value">{font_percentage:.0f}%</div>
                <div class="stat-change">{embedded_fonts}/{len(fonts)}개 임베딩됨</div>
            </div>
"""
        
        # 이미지 품질
        images = analysis_result.get('images', {})
        total_images = images.get('total_count', 0)
        low_res_images = images.get('low_resolution_count', 0)
        image_quality = ((total_images - low_res_images) / total_images * 100) if total_images else 100
        
        html += f"""
            <div class="stat-card {'error' if low_res_images > 0 else 'success'}">
                <div class="stat-header">
                    <div class="stat-label">이미지 품질</div>
                    <div class="stat-icon">🖼️</div>
                </div>
                <div class="stat-value">{image_quality:.0f}%</div>
                <div class="stat-change">{total_images}개 중 {low_res_images}개 저해상도</div>
            </div>
"""
        
        # 잉크량
        ink = analysis_result.get('ink_coverage', {})
        if 'summary' in ink:
            max_ink = ink['summary']['max_coverage']
            ink_status = 'error' if max_ink > 300 else 'warning' if max_ink > 280 else 'success'
            
            html += f"""
            <div class="stat-card {ink_status}">
                <div class="stat-header">
                    <div class="stat-label">최대 잉크량</div>
                    <div class="stat-icon">💧</div>
                </div>
                <div class="stat-value">{max_ink:.0f}%</div>
                <div class="stat-change">평균 {ink['summary']['avg_coverage']:.0f}%</div>
            </div>
"""
        
        html += """
        </div>
        
        <!-- 상세 정보 -->
        <div class="details-grid">
            <!-- 기본 정보 -->
            <div class="detail-card">
                <div class="detail-header">
                    <span>📋</span>
                    <span>기본 정보</span>
                </div>
                <div class="info-grid">
"""
        
        basic = analysis_result['basic_info']
        html += f"""
                    <div class="info-row">
                        <span class="info-label">PDF 버전</span>
                        <span class="info-value">{basic['pdf_version']}</span>
                    </div>
                    <div class="info-row">
                        <span class="info-label">제목</span>
                        <span class="info-value">{basic['title'] or '(없음)'}</span>
                    </div>
                    <div class="info-row">
                        <span class="info-label">작성자</span>
                        <span class="info-value">{basic['author'] or '(없음)'}</span>
                    </div>
                    <div class="info-row">
                        <span class="info-label">생성 프로그램</span>
                        <span class="info-value">{basic['creator'] or '(없음)'}</span>
                    </div>
"""
        
        html += """
                </div>
            </div>
            
            <!-- 색상 정보 -->
            <div class="detail-card">
                <div class="detail-header">
                    <span>🎨</span>
                    <span>색상 정보</span>
                </div>
                <div class="info-grid">
"""
        
        colors = analysis_result['colors']
        color_modes = []
        if colors['has_rgb']:
            color_modes.append("RGB")
        if colors['has_cmyk']:
            color_modes.append("CMYK")
        if colors['has_gray']:
            color_modes.append("Grayscale")
        
        html += f"""
                    <div class="info-row">
                        <span class="info-label">색상 모드</span>
                        <span class="info-value">{', '.join(color_modes) if color_modes else '기본'}</span>
                    </div>
                    <div class="info-row">
                        <span class="info-label">별색 사용</span>
                        <span class="info-value">{len(colors.get('spot_color_names', []))}개</span>
                    </div>
"""
        
        if colors.get('spot_color_names'):
            for spot_name in colors['spot_color_names'][:3]:
                html += f"""
                    <div class="info-row">
                        <span class="info-label" style="padding-left: 1rem;">• {spot_name}</span>
                        <span class="info-value">{'PANTONE' if 'PANTONE' in spot_name else '커스텀'}</span>
                    </div>
"""
        
        html += """
                </div>
            </div>
        </div>
        
        <!-- 액션 버튼 -->
        <div class="action-buttons">
            <button class="btn btn-primary" onclick="window.print()">
                🖨️ 보고서 인쇄
            </button>
            <button class="btn btn-secondary" onclick="saveReport()">
                💾 저장하기
            </button>
        </div>
    </div>
    
    <script>
        // 보고서 저장 기능
        function saveReport() {
            const element = document.documentElement;
            const opt = {
                margin: 10,
                filename: 'pdf_report.pdf',
                image: { type: 'jpeg', quality: 0.98 },
                html2canvas: { scale: 2 },
                jsPDF: { unit: 'mm', format: 'a4', orientation: 'portrait' }
            };
            
            // html2pdf 라이브러리가 있으면 PDF로 저장
            if (typeof html2pdf !== 'undefined') {
                html2pdf().from(element).set(opt).save();
            } else {
                // 없으면 HTML로 저장
                const blob = new Blob([document.documentElement.outerHTML], {type: 'text/html'});
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = 'pdf_report_{analysis_result["filename"].replace(".pdf", "")}.html';
                a.click();
            }
        }
    </script>
</body>
</html>
"""
        
        return html
    
    def save_text_report(self, analysis_result, output_path=None):
        """
        텍스트 보고서를 파일로 저장
        
        Args:
            analysis_result: 분석 결과
            output_path: 저장할 경로 (None이면 기본 경로 사용)
            
        Returns:
            Path: 저장된 파일 경로
        """
        # 보고서 내용 생성
        report_content = self.generate_text_report(analysis_result)
        
        # 저장 경로 결정
        if output_path is None:
            from utils import create_report_filename
            filename = analysis_result.get('filename', 'unknown.pdf')
            report_name = create_report_filename(filename, 'text')
            output_path = self.config.REPORTS_PATH / report_name
        
        # 파일로 저장
        output_path = Path(output_path)
        output_path.write_text(report_content, encoding='utf-8')
        
        print(f"  ✓ 텍스트 보고서 저장: {output_path.name}")
        return output_path
    
    def save_html_report(self, analysis_result, output_path=None):
        """
        HTML 보고서를 파일로 저장
        
        Args:
            analysis_result: 분석 결과
            output_path: 저장할 경로 (None이면 기본 경로 사용)
            
        Returns:
            Path: 저장된 파일 경로
        """
        # 보고서 내용 생성
        report_content = self.generate_html_report(analysis_result)
        
        # 저장 경로 결정
        if output_path is None:
            from utils import create_report_filename
            filename = analysis_result.get('filename', 'unknown.pdf')
            report_name = create_report_filename(filename, 'html')
            output_path = self.config.REPORTS_PATH / report_name
        
        # 파일로 저장
        output_path = Path(output_path)
        output_path.write_text(report_content, encoding='utf-8')
        
        print(f"  ✓ HTML 보고서 저장: {output_path.name}")
        return output_path
    
    def save_json_report(self, analysis_result, output_path=None):
        """
        JSON 형식으로 분석 결과 저장 (API 연동용)
        
        Args:
            analysis_result: 분석 결과
            output_path: 저장할 경로
            
        Returns:
            Path: 저장된 파일 경로
        """
        if output_path is None:
            filename = analysis_result.get('filename', 'unknown.pdf')
            json_name = filename.replace('.pdf', '_data.json')
            output_path = self.config.REPORTS_PATH / json_name
        
        # JSON으로 저장
        output_path = Path(output_path)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(analysis_result, f, ensure_ascii=False, indent=2)
        
        return output_path
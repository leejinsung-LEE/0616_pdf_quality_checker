# pdf_comparator.py - PDF 비교 검사 모듈
# 두 PDF 파일의 차이점을 찾아내고 시각적으로 표시하는 기능

"""
pdf_comparator.py - PDF 비교 검사 엔진
두 PDF 파일을 비교하여 변경사항을 감지하고 리포트를 생성합니다.
"""

import fitz  # PyMuPDF
import numpy as np
from pathlib import Path
from datetime import datetime
import json
from typing import Dict, List, Tuple, Optional, Any
from PIL import Image, ImageDraw, ImageFont, ImageChops
import io
import base64

# 프로젝트 모듈
from config import Config
from utils import format_datetime, format_file_size, points_to_mm
from simple_logger import SimpleLogger


class PDFComparator:
    """PDF 비교 검사를 수행하는 클래스"""
    
    def __init__(self):
        """비교기 초기화"""
        self.logger = SimpleLogger()
        self.doc1 = None
        self.doc2 = None
        self.comparison_result = {}
        
        # 비교 설정
        self.settings = {
            'pixel_threshold': 5,  # 픽셀 차이 임계값
            'text_compare': True,  # 텍스트 내용 비교
            'image_compare': True,  # 이미지 비교
            'visual_compare': True,  # 시각적 비교
            'highlight_color': (255, 0, 0, 100),  # 차이점 표시 색상 (빨간색)
            'comparison_dpi': 150,  # 비교용 렌더링 해상도
        }
        
    def compare(self, pdf_path1: Path, pdf_path2: Path, output_dir: Path = None) -> Dict:
        """
        두 PDF 파일을 비교하는 메인 메서드
        
        Args:
            pdf_path1: 원본 PDF 경로
            pdf_path2: 비교할 PDF 경로
            output_dir: 비교 결과를 저장할 디렉토리
            
        Returns:
            dict: 비교 결과
        """
        self.logger.log(f"PDF 비교 시작: {pdf_path1.name} vs {pdf_path2.name}")
        
        try:
            # PDF 열기
            self.doc1 = fitz.open(pdf_path1)
            self.doc2 = fitz.open(pdf_path2)
            
            # 출력 디렉토리 설정
            if output_dir is None:
                output_dir = Config.REPORTS_PATH / f"compare_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # 비교 결과 초기화
            self.comparison_result = {
                'file1': {
                    'name': pdf_path1.name,
                    'path': str(pdf_path1),
                    'size': pdf_path1.stat().st_size,
                    'pages': len(self.doc1)
                },
                'file2': {
                    'name': pdf_path2.name,
                    'path': str(pdf_path2),
                    'size': pdf_path2.stat().st_size,
                    'pages': len(self.doc2)
                },
                'comparison_date': format_datetime(),
                'output_dir': str(output_dir),
                'summary': {},
                'page_comparisons': [],
                'differences': []
            }
            
            # 1. 기본 정보 비교
            self._compare_basic_info()
            
            # 2. 페이지별 비교
            self._compare_pages(output_dir)
            
            # 3. 전체 요약 생성
            self._generate_summary()
            
            # 4. 비교 리포트 생성
            self._generate_comparison_report(output_dir)
            
            self.logger.log("PDF 비교 완료")
            
            return self.comparison_result
            
        except Exception as e:
            self.logger.error(f"PDF 비교 중 오류: {str(e)}")
            return {'error': str(e)}
            
        finally:
            # 문서 닫기
            if self.doc1:
                self.doc1.close()
            if self.doc2:
                self.doc2.close()
    
    def _compare_basic_info(self):
        """PDF 기본 정보 비교"""
        self.logger.log("기본 정보 비교 중...")
        
        differences = []
        
        # 페이지 수 비교
        if len(self.doc1) != len(self.doc2):
            differences.append({
                'type': 'page_count',
                'severity': 'major',
                'description': f"페이지 수 차이: {len(self.doc1)}페이지 → {len(self.doc2)}페이지",
                'value1': len(self.doc1),
                'value2': len(self.doc2)
            })
        
        # 메타데이터 비교
        metadata_keys = ['/Title', '/Author', '/Subject', '/Creator', '/Producer']
        for key in metadata_keys:
            val1 = self.doc1.metadata.get(key, '')
            val2 = self.doc2.metadata.get(key, '')
            if val1 != val2:
                differences.append({
                    'type': 'metadata',
                    'severity': 'minor',
                    'description': f"{key} 변경: '{val1}' → '{val2}'",
                    'key': key,
                    'value1': val1,
                    'value2': val2
                })
        
        self.comparison_result['differences'].extend(differences)
    
    def _compare_pages(self, output_dir: Path):
        """페이지별 상세 비교"""
        self.logger.log("페이지별 비교 시작...")
        
        max_pages = max(len(self.doc1), len(self.doc2))
        
        for page_num in range(max_pages):
            self.logger.log(f"  {page_num + 1}/{max_pages} 페이지 비교 중...")
            
            # 페이지 존재 여부 확인
            if page_num >= len(self.doc1):
                self.comparison_result['page_comparisons'].append({
                    'page': page_num + 1,
                    'status': 'added',
                    'description': '새로 추가된 페이지'
                })
                continue
                
            if page_num >= len(self.doc2):
                self.comparison_result['page_comparisons'].append({
                    'page': page_num + 1,
                    'status': 'deleted',
                    'description': '삭제된 페이지'
                })
                continue
            
            # 페이지 비교
            page1 = self.doc1[page_num]
            page2 = self.doc2[page_num]
            
            page_comparison = {
                'page': page_num + 1,
                'differences': []
            }
            
            # 1. 페이지 크기 비교
            size_diff = self._compare_page_size(page1, page2)
            if size_diff:
                page_comparison['differences'].append(size_diff)
            
            # 2. 텍스트 내용 비교
            if self.settings['text_compare']:
                text_diffs = self._compare_text_content(page1, page2)
                page_comparison['differences'].extend(text_diffs)
            
            # 3. 시각적 비교 (픽셀 단위)
            if self.settings['visual_compare']:
                visual_diff = self._compare_visual(page1, page2, page_num + 1, output_dir)
                if visual_diff:
                    page_comparison['differences'].append(visual_diff)
            
            # 4. 이미지 비교
            if self.settings['image_compare']:
                image_diffs = self._compare_images(page1, page2)
                page_comparison['differences'].extend(image_diffs)
            
            # 페이지 상태 결정
            if not page_comparison['differences']:
                page_comparison['status'] = 'identical'
                page_comparison['description'] = '변경 없음'
            else:
                page_comparison['status'] = 'modified'
                page_comparison['description'] = f"{len(page_comparison['differences'])}개 차이점 발견"
            
            self.comparison_result['page_comparisons'].append(page_comparison)
    
    def _compare_page_size(self, page1, page2) -> Optional[Dict]:
        """페이지 크기 비교"""
        rect1 = page1.rect
        rect2 = page2.rect
        
        # 크기가 다른 경우
        tolerance = 1  # 1포인트 오차 허용
        if (abs(rect1.width - rect2.width) > tolerance or 
            abs(rect1.height - rect2.height) > tolerance):
            
            return {
                'type': 'page_size',
                'severity': 'major',
                'description': f"페이지 크기 변경: {rect1.width:.1f}x{rect1.height:.1f} → {rect2.width:.1f}x{rect2.height:.1f}",
                'size1': (rect1.width, rect1.height),
                'size2': (rect2.width, rect2.height)
            }
        
        return None
    
    def _compare_text_content(self, page1, page2) -> List[Dict]:
        """텍스트 내용 비교"""
        differences = []
        
        # 텍스트 추출
        text1 = page1.get_text()
        text2 = page2.get_text()
        
        # 간단한 비교 (전체 텍스트)
        if text1 != text2:
            # 텍스트 블록 단위로 상세 비교
            blocks1 = page1.get_text("dict")["blocks"]
            blocks2 = page2.get_text("dict")["blocks"]
            
            # 텍스트 블록만 필터링
            text_blocks1 = [b for b in blocks1 if b["type"] == 0]
            text_blocks2 = [b for b in blocks2 if b["type"] == 0]
            
            # 블록 수가 다른 경우
            if len(text_blocks1) != len(text_blocks2):
                differences.append({
                    'type': 'text_structure',
                    'severity': 'major',
                    'description': f"텍스트 블록 수 변경: {len(text_blocks1)}개 → {len(text_blocks2)}개"
                })
            
            # 각 블록의 텍스트 비교
            for i, (block1, block2) in enumerate(zip(text_blocks1, text_blocks2)):
                text1 = self._extract_block_text(block1)
                text2 = self._extract_block_text(block2)
                
                if text1 != text2:
                    differences.append({
                        'type': 'text_content',
                        'severity': 'major',
                        'description': f"텍스트 변경 감지 (블록 {i+1})",
                        'text1': text1[:100] + "..." if len(text1) > 100 else text1,
                        'text2': text2[:100] + "..." if len(text2) > 100 else text2,
                        'position': (block1["bbox"][0], block1["bbox"][1])
                    })
        
        return differences
    
    def _extract_block_text(self, block) -> str:
        """텍스트 블록에서 텍스트 추출"""
        text = ""
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                text += span.get("text", "")
        return text.strip()
    
    def _compare_visual(self, page1, page2, page_num: int, output_dir: Path) -> Optional[Dict]:
        """시각적 비교 (픽셀 단위)"""
        # 페이지를 이미지로 렌더링
        zoom = self.settings['comparison_dpi'] / 72.0
        mat = fitz.Matrix(zoom, zoom)
        
        pix1 = page1.get_pixmap(matrix=mat)
        pix2 = page2.get_pixmap(matrix=mat)
        
        # PIL 이미지로 변환
        img1 = Image.open(io.BytesIO(pix1.tobytes("png")))
        img2 = Image.open(io.BytesIO(pix2.tobytes("png")))
        
        # 크기가 다른 경우 맞춤
        if img1.size != img2.size:
            # 더 큰 크기에 맞춤
            max_width = max(img1.width, img2.width)
            max_height = max(img1.height, img2.height)
            
            # 캔버스 생성
            canvas1 = Image.new('RGB', (max_width, max_height), 'white')
            canvas2 = Image.new('RGB', (max_width, max_height), 'white')
            
            canvas1.paste(img1, (0, 0))
            canvas2.paste(img2, (0, 0))
            
            img1 = canvas1
            img2 = canvas2
        
        # 차이 계산
        diff = ImageChops.difference(img1, img2)
        
        # 차이가 있는지 확인
        if diff.getbbox():
            # 차이점 하이라이트 이미지 생성
            diff_highlighted = self._create_diff_visualization(img1, img2, diff)
            
            # 차이 이미지 저장
            diff_path = output_dir / f"page_{page_num}_diff.png"
            diff_highlighted.save(diff_path)
            
            # 차이 영역 계산
            diff_pixels = np.array(diff)
            total_pixels = diff_pixels.shape[0] * diff_pixels.shape[1]
            changed_pixels = np.sum(diff_pixels > self.settings['pixel_threshold'])
            change_percentage = (changed_pixels / total_pixels) * 100
            
            return {
                'type': 'visual',
                'severity': 'major' if change_percentage > 10 else 'minor',
                'description': f"시각적 차이 {change_percentage:.1f}% 감지",
                'change_percentage': change_percentage,
                'diff_image': str(diff_path),
                'bbox': diff.getbbox()
            }
        
        return None
    
    def _create_diff_visualization(self, img1: Image, img2: Image, diff: Image) -> Image:
        """차이점 시각화 이미지 생성"""
        # 기본 이미지는 img2 (새 버전)
        result = img2.copy()
        
        # 차이점을 빨간색으로 표시
        diff_array = np.array(diff)
        mask = np.any(diff_array > self.settings['pixel_threshold'], axis=2)
        
        # 오버레이 생성
        overlay = Image.new('RGBA', img2.size, (255, 255, 255, 0))
        draw = ImageDraw.Draw(overlay)
        
        # 변경된 영역을 사각형으로 표시
        # 연결된 컴포넌트 찾기 (간단한 구현)
        from scipy import ndimage
        labeled, num_features = ndimage.label(mask)
        
        for i in range(1, num_features + 1):
            component = (labeled == i)
            rows = np.any(component, axis=1)
            cols = np.any(component, axis=0)
            rmin, rmax = np.where(rows)[0][[0, -1]]
            cmin, cmax = np.where(cols)[0][[0, -1]]
            
            # 사각형 그리기
            draw.rectangle(
                [(cmin-5, rmin-5), (cmax+5, rmax+5)],
                outline=(255, 0, 0, 255),
                width=3
            )
        
        # 결과 이미지에 오버레이 합성
        result = Image.alpha_composite(result.convert('RGBA'), overlay)
        
        return result.convert('RGB')
    
    def _compare_images(self, page1, page2) -> List[Dict]:
        """페이지 내 이미지 비교"""
        differences = []
        
        # 이미지 목록 가져오기
        images1 = page1.get_images()
        images2 = page2.get_images()
        
        # 이미지 수 비교
        if len(images1) != len(images2):
            differences.append({
                'type': 'image_count',
                'severity': 'major',
                'description': f"이미지 수 변경: {len(images1)}개 → {len(images2)}개"
            })
        
        # 각 이미지 비교 (간단한 구현)
        for i, (img1, img2) in enumerate(zip(images1, images2)):
            # 이미지 크기 비교
            if img1[2:4] != img2[2:4]:  # width, height
                differences.append({
                    'type': 'image_size',
                    'severity': 'minor',
                    'description': f"이미지 {i+1} 크기 변경",
                    'size1': img1[2:4],
                    'size2': img2[2:4]
                })
        
        return differences
    
    def _generate_summary(self):
        """전체 비교 요약 생성"""
        summary = {
            'total_pages': max(len(self.doc1), len(self.doc2)),
            'identical_pages': 0,
            'modified_pages': 0,
            'added_pages': 0,
            'deleted_pages': 0,
            'total_differences': 0,
            'major_differences': 0,
            'minor_differences': 0,
            'change_types': {}
        }
        
        # 페이지별 통계
        for page_comp in self.comparison_result['page_comparisons']:
            status = page_comp.get('status', 'identical')
            if status == 'identical':
                summary['identical_pages'] += 1
            elif status == 'modified':
                summary['modified_pages'] += 1
            elif status == 'added':
                summary['added_pages'] += 1
            elif status == 'deleted':
                summary['deleted_pages'] += 1
            
            # 차이점 통계
            for diff in page_comp.get('differences', []):
                summary['total_differences'] += 1
                if diff['severity'] == 'major':
                    summary['major_differences'] += 1
                else:
                    summary['minor_differences'] += 1
                
                # 타입별 카운트
                diff_type = diff['type']
                summary['change_types'][diff_type] = summary['change_types'].get(diff_type, 0) + 1
        
        # 일치율 계산
        if summary['total_pages'] > 0:
            summary['similarity_percentage'] = (summary['identical_pages'] / summary['total_pages']) * 100
        else:
            summary['similarity_percentage'] = 100
        
        self.comparison_result['summary'] = summary
    
    def _generate_comparison_report(self, output_dir: Path):
        """비교 리포트 생성"""
        self.logger.log("비교 리포트 생성 중...")
        
        # HTML 리포트 생성
        html_path = output_dir / "comparison_report.html"
        html_content = self._create_html_report()
        html_path.write_text(html_content, encoding='utf-8')
        
        # JSON 데이터 저장
        json_path = output_dir / "comparison_data.json"
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(self.comparison_result, f, ensure_ascii=False, indent=2)
        
        self.logger.log(f"비교 리포트 생성 완료: {output_dir}")
    
    def _create_html_report(self) -> str:
        """HTML 형식의 비교 리포트 생성"""
        summary = self.comparison_result['summary']
        
        # 전체 상태 결정
        if summary['total_differences'] == 0:
            status_color = '#10b981'
            status_text = '완전 일치'
            status_icon = '✅'
        elif summary['major_differences'] > 0:
            status_color = '#ef4444'
            status_text = '주요 변경사항 있음'
            status_icon = '⚠️'
        else:
            status_color = '#f59e0b'
            status_text = '경미한 변경사항'
            status_icon = 'ℹ️'
        
        html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PDF 비교 리포트 - {self.comparison_result['file1']['name']} vs {self.comparison_result['file2']['name']}</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: 'Segoe UI', 'Malgun Gothic', sans-serif;
            background: #f3f4f6;
            color: #1f2937;
            line-height: 1.6;
        }}
        
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            padding: 2rem;
        }}
        
        .header {{
            background: white;
            border-radius: 12px;
            padding: 2rem;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
            margin-bottom: 2rem;
        }}
        
        .header h1 {{
            font-size: 2rem;
            margin-bottom: 1rem;
            color: #111827;
        }}
        
        .status-banner {{
            background: {status_color};
            color: white;
            padding: 1rem 1.5rem;
            border-radius: 8px;
            display: inline-flex;
            align-items: center;
            gap: 0.5rem;
            margin-bottom: 1rem;
        }}
        
        .status-icon {{
            font-size: 1.5rem;
        }}
        
        .file-info {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 2rem;
            margin-top: 1.5rem;
        }}
        
        .file-card {{
            background: #f9fafb;
            padding: 1rem;
            border-radius: 8px;
            border: 1px solid #e5e7eb;
        }}
        
        .file-card h3 {{
            font-size: 0.875rem;
            color: #6b7280;
            margin-bottom: 0.5rem;
        }}
        
        .file-card .filename {{
            font-weight: 600;
            color: #111827;
            margin-bottom: 0.5rem;
        }}
        
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1rem;
            margin-bottom: 2rem;
        }}
        
        .stat-card {{
            background: white;
            padding: 1.5rem;
            border-radius: 8px;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
            text-align: center;
        }}
        
        .stat-value {{
            font-size: 2rem;
            font-weight: 700;
            color: #111827;
            margin-bottom: 0.25rem;
        }}
        
        .stat-label {{
            font-size: 0.875rem;
            color: #6b7280;
        }}
        
        .pages-section {{
            background: white;
            border-radius: 12px;
            padding: 2rem;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
            margin-bottom: 2rem;
        }}
        
        .pages-section h2 {{
            font-size: 1.5rem;
            margin-bottom: 1.5rem;
            color: #111827;
        }}
        
        .page-item {{
            border: 1px solid #e5e7eb;
            border-radius: 8px;
            padding: 1rem;
            margin-bottom: 1rem;
            background: #f9fafb;
        }}
        
        .page-item.modified {{
            border-color: #fbbf24;
            background: #fffbeb;
        }}
        
        .page-item.added {{
            border-color: #34d399;
            background: #ecfdf5;
        }}
        
        .page-item.deleted {{
            border-color: #f87171;
            background: #fef2f2;
        }}
        
        .page-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 0.5rem;
        }}
        
        .page-number {{
            font-weight: 600;
            color: #111827;
        }}
        
        .page-status {{
            font-size: 0.875rem;
            padding: 0.25rem 0.75rem;
            border-radius: 9999px;
            font-weight: 500;
        }}
        
        .status-identical {{ background: #d1fae5; color: #065f46; }}
        .status-modified {{ background: #fed7aa; color: #92400e; }}
        .status-added {{ background: #d1fae5; color: #065f46; }}
        .status-deleted {{ background: #fee2e2; color: #991b1b; }}
        
        .diff-list {{
            margin-top: 1rem;
            padding-left: 1.5rem;
        }}
        
        .diff-item {{
            margin-bottom: 0.5rem;
            color: #4b5563;
            font-size: 0.875rem;
        }}
        
        .diff-image {{
            margin-top: 1rem;
            max-width: 100%;
            border: 1px solid #e5e7eb;
            border-radius: 4px;
        }}
        
        .summary-section {{
            background: white;
            border-radius: 12px;
            padding: 2rem;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
        }}
        
        .change-types {{
            margin-top: 1.5rem;
        }}
        
        .change-type {{
            display: flex;
            justify-content: space-between;
            padding: 0.5rem 0;
            border-bottom: 1px solid #e5e7eb;
        }}
        
        .similarity-meter {{
            margin: 2rem 0;
            text-align: center;
        }}
        
        .similarity-bar {{
            width: 100%;
            height: 30px;
            background: #e5e7eb;
            border-radius: 15px;
            overflow: hidden;
            position: relative;
        }}
        
        .similarity-fill {{
            height: 100%;
            background: linear-gradient(to right, #ef4444, #f59e0b, #10b981);
            width: {summary['similarity_percentage']:.1f}%;
            transition: width 1s ease;
        }}
        
        .similarity-text {{
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            font-weight: 600;
            color: #111827;
        }}
    </style>
</head>
<body>
    <div class="container">
        <!-- 헤더 -->
        <div class="header">
            <h1>PDF 비교 리포트</h1>
            
            <div class="status-banner">
                <span class="status-icon">{status_icon}</span>
                <span>{status_text}</span>
            </div>
            
            <div class="file-info">
                <div class="file-card">
                    <h3>원본 파일</h3>
                    <div class="filename">{self.comparison_result['file1']['name']}</div>
                    <div style="font-size: 0.875rem; color: #6b7280;">
                        {self.comparison_result['file1']['pages']} 페이지 • {format_file_size(self.comparison_result['file1']['size'])}
                    </div>
                </div>
                <div class="file-card">
                    <h3>비교 파일</h3>
                    <div class="filename">{self.comparison_result['file2']['name']}</div>
                    <div style="font-size: 0.875rem; color: #6b7280;">
                        {self.comparison_result['file2']['pages']} 페이지 • {format_file_size(self.comparison_result['file2']['size'])}
                    </div>
                </div>
            </div>
        </div>
        
        <!-- 일치율 표시 -->
        <div class="summary-section">
            <h2 style="text-align: center; margin-bottom: 1rem;">전체 일치율</h2>
            <div class="similarity-meter">
                <div class="similarity-bar">
                    <div class="similarity-fill"></div>
                    <div class="similarity-text">{summary['similarity_percentage']:.1f}%</div>
                </div>
            </div>
        </div>
        
        <!-- 통계 카드 -->
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-value">{summary['total_pages']}</div>
                <div class="stat-label">전체 페이지</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" style="color: #10b981;">{summary['identical_pages']}</div>
                <div class="stat-label">동일 페이지</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" style="color: #f59e0b;">{summary['modified_pages']}</div>
                <div class="stat-label">수정된 페이지</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" style="color: #ef4444;">{summary['total_differences']}</div>
                <div class="stat-label">총 차이점</div>
            </div>
        </div>
        
        <!-- 페이지별 상세 -->
        <div class="pages-section">
            <h2>페이지별 비교 결과</h2>
"""
        
        # 변경된 페이지만 표시 (최대 20개)
        changed_pages = [p for p in self.comparison_result['page_comparisons'] if p['status'] != 'identical']
        
        for page_comp in changed_pages[:20]:
            status_class = f"status-{page_comp['status']}"
            
            html += f"""
            <div class="page-item {page_comp['status']}">
                <div class="page-header">
                    <div class="page-number">페이지 {page_comp['page']}</div>
                    <div class="page-status {status_class}">{page_comp['description']}</div>
                </div>
"""
            
            if page_comp.get('differences'):
                html += '<div class="diff-list">'
                for diff in page_comp['differences']:
                    html += f'<div class="diff-item">• {diff["description"]}</div>'
                    
                    # 차이 이미지가 있으면 표시
                    if diff.get('diff_image'):
                        img_path = Path(diff['diff_image'])
                        if img_path.exists():
                            html += f'<img src="{img_path.name}" class="diff-image" alt="차이점 시각화">'
                
                html += '</div>'
            
            html += '</div>'
        
        if len(changed_pages) > 20:
            html += f'<p style="text-align: center; color: #6b7280; margin-top: 1rem;">... 외 {len(changed_pages) - 20}개 페이지</p>'
        
        html += """
        </div>
        
        <!-- 변경 유형 요약 -->
        <div class="summary-section">
            <h2>변경 유형별 요약</h2>
            <div class="change-types">
"""
        
        # 변경 타입별 통계
        change_type_names = {
            'page_size': '페이지 크기',
            'text_content': '텍스트 내용',
            'text_structure': '텍스트 구조',
            'visual': '시각적 변경',
            'image_count': '이미지 수',
            'image_size': '이미지 크기',
            'metadata': '메타데이터'
        }
        
        for change_type, count in summary['change_types'].items():
            type_name = change_type_names.get(change_type, change_type)
            html += f"""
                <div class="change-type">
                    <span>{type_name}</span>
                    <span style="font-weight: 600;">{count}건</span>
                </div>
"""
        
        html += f"""
            </div>
        </div>
    </div>
    
    <script>
        // 페이지 로드 시 애니메이션
        document.addEventListener('DOMContentLoaded', function() {{
            const fill = document.querySelector('.similarity-fill');
            setTimeout(() => {{
                fill.style.width = '{summary['similarity_percentage']:.1f}%';
            }}, 100);
        }});
    </script>
</body>
</html>
"""
        
        return html


# 명령줄 인터페이스를 위한 함수
def compare_pdfs_cli(pdf1_path: str, pdf2_path: str, output_dir: str = None):
    """명령줄에서 PDF 비교를 실행하는 함수"""
    comparator = PDFComparator()
    
    # 경로 객체로 변환
    pdf1 = Path(pdf1_path)
    pdf2 = Path(pdf2_path)
    
    if not pdf1.exists():
        print(f"❌ 파일을 찾을 수 없습니다: {pdf1}")
        return
    
    if not pdf2.exists():
        print(f"❌ 파일을 찾을 수 없습니다: {pdf2}")
        return
    
    # 출력 디렉토리 설정
    if output_dir:
        output = Path(output_dir)
    else:
        output = None
    
    print(f"\n📊 PDF 비교 시작")
    print(f"원본: {pdf1.name}")
    print(f"비교: {pdf2.name}")
    print("-" * 50)
    
    # 비교 실행
    result = comparator.compare(pdf1, pdf2, output)
    
    if 'error' in result:
        print(f"\n❌ 오류 발생: {result['error']}")
        return
    
    # 결과 출력
    summary = result['summary']
    print(f"\n✅ 비교 완료!")
    print(f"\n📈 전체 일치율: {summary['similarity_percentage']:.1f}%")
    print(f"\n📊 페이지 통계:")
    print(f"  • 전체: {summary['total_pages']}페이지")
    print(f"  • 동일: {summary['identical_pages']}페이지")
    print(f"  • 수정: {summary['modified_pages']}페이지")
    print(f"  • 추가: {summary['added_pages']}페이지")
    print(f"  • 삭제: {summary['deleted_pages']}페이지")
    
    print(f"\n🔍 차이점 통계:")
    print(f"  • 총 차이점: {summary['total_differences']}개")
    print(f"  • 주요 변경: {summary['major_differences']}개")
    print(f"  • 경미한 변경: {summary['minor_differences']}개")
    
    print(f"\n📁 리포트 위치: {result['output_dir']}")
    

# 사용 예시
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 3:
        print("사용법: python pdf_comparator.py <원본.pdf> <비교.pdf> [출력폴더]")
        sys.exit(1)
    
    pdf1 = sys.argv[1]
    pdf2 = sys.argv[2]
    output = sys.argv[3] if len(sys.argv) > 3 else None
    
    compare_pdfs_cli(pdf1, pdf2, output)
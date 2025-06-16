# ink_calculator.py - PDF의 잉크량을 계산하는 핵심 엔진입니다
# Phase 2의 가장 중요한 기능으로, Adobe Acrobat과 유사한 정확도를 목표로 합니다

"""
ink_calculator.py - 잉크량 계산 엔진
PyMuPDF(fitz)를 사용하여 각 페이지의 CMYK 잉크 사용량을 분석합니다
"""

import fitz  # PyMuPDF
import numpy as np
from pathlib import Path
from utils import safe_float, safe_div, calculate_coverage_percentage, calculate_ink_coverage_stats
from config import Config

class InkCalculator:
    """PDF 파일의 잉크량을 계산하는 클래스"""
    
    def __init__(self):
        """잉크 계산기 초기화"""
        self.doc = None
        self.dpi = Config.INK_CALCULATION_DPI  # 계산에 사용할 해상도
        
    def calculate(self, pdf_path, page_numbers=None):
        """
        PDF 파일의 잉크량을 계산하는 메인 메서드
        
        Args:
            pdf_path: PDF 파일 경로
            page_numbers: 분석할 페이지 번호 리스트 (None이면 전체)
            
        Returns:
            dict: 페이지별 잉크량 정보
        """
        print(f"\n🎨 잉크량 계산 시작...")
        print(f"  • 해상도: {self.dpi} DPI")
        
        try:
            # PDF 열기
            self.doc = fitz.open(pdf_path)
            total_pages = len(self.doc)
            
            # 분석할 페이지 결정
            if page_numbers is None:
                page_numbers = range(total_pages)
            else:
                # 페이지 번호를 0-based 인덱스로 변환
                page_numbers = [p-1 for p in page_numbers if 0 <= p-1 < total_pages]
            
            results = {
                'total_pages': total_pages,
                'analyzed_pages': len(page_numbers),
                'pages': {},
                'summary': {
                    'max_coverage': 0,
                    'avg_coverage': 0,
                    'problem_pages': []
                }
            }
            
            # 각 페이지 분석
            for idx, page_num in enumerate(page_numbers):
                print(f"  • {page_num+1}/{total_pages} 페이지 분석 중...", end='\r')
                
                page_result = self._analyze_page(page_num)
                results['pages'][page_num+1] = page_result
                
                # 요약 정보 업데이트
                if page_result['max_coverage'] > results['summary']['max_coverage']:
                    results['summary']['max_coverage'] = page_result['max_coverage']
                
                if page_result['max_coverage'] > Config.MAX_INK_COVERAGE:
                    results['summary']['problem_pages'].append({
                        'page': page_num+1,
                        'max_coverage': page_result['max_coverage'],
                        'over_300_percent': page_result['stats']['over_300']
                    })
            
            # 평균 계산
            if results['pages']:
                avg_list = [p['avg_coverage'] for p in results['pages'].values()]
                results['summary']['avg_coverage'] = sum(avg_list) / len(avg_list)
            
            print(f"\n  ✓ 잉크량 계산 완료!")
            print(f"  • 최대 잉크량: {results['summary']['max_coverage']:.1f}%")
            print(f"  • 평균 잉크량: {results['summary']['avg_coverage']:.1f}%")
            
            if results['summary']['problem_pages']:
                print(f"  ⚠️  {len(results['summary']['problem_pages'])}개 페이지에서 과도한 잉크량 발견")
            
            return results
            
        except Exception as e:
            print(f"\n❌ 잉크량 계산 중 오류: {e}")
            return {'error': str(e)}
        finally:
            if self.doc:
                self.doc.close()
    
    def _analyze_page(self, page_num):
        """
        단일 페이지의 잉크량 분석
        
        Args:
            page_num: 페이지 번호 (0-based)
            
        Returns:
            dict: 페이지 잉크량 정보
        """
        page = self.doc[page_num]
        
        # 페이지를 픽스맵으로 렌더링
        # matrix를 사용해서 DPI 설정
        zoom = self.dpi / 72.0  # PDF는 72 DPI가 기본
        matrix = fitz.Matrix(zoom, zoom)
        
        # CMYK 색상 공간으로 렌더링
        # colorspace=fitz.csGRAY는 그레이스케일, fitz.csRGB는 RGB
        # CMYK를 직접 얻기 위해 다른 방법 사용
        pix = page.get_pixmap(matrix=matrix, alpha=False)
        
        # 픽스맵을 numpy 배열로 변환
        img_data = np.frombuffer(pix.samples, dtype=np.uint8)
        
        # 이미지 데이터 재구성
        if pix.n == 3:  # RGB
            img_data = img_data.reshape(pix.height, pix.width, 3)
            # RGB를 CMYK로 변환 (간단한 변환)
            coverage_map = self._rgb_to_coverage_map(img_data)
        elif pix.n == 4:  # RGBA 또는 CMYK
            img_data = img_data.reshape(pix.height, pix.width, 4)
            # CMYK로 가정하고 처리
            coverage_map = self._cmyk_to_coverage_map(img_data)
        elif pix.n == 1:  # 그레이스케일
            img_data = img_data.reshape(pix.height, pix.width)
            # 그레이스케일을 K 채널로만 처리
            coverage_map = (img_data / 255.0) * 100
        else:
            # 기타 색상 공간은 기본값으로 처리
            coverage_map = np.zeros((pix.height, pix.width))
        
        # 통계 계산
        stats = calculate_ink_coverage_stats(coverage_map)
        
        # 문제 영역 찾기 (300% 초과)
        problem_areas = self._find_problem_areas(coverage_map, Config.MAX_INK_COVERAGE)
        
        return {
            'page_number': page_num + 1,
            'width': pix.width,
            'height': pix.height,
            'max_coverage': stats['max'],
            'avg_coverage': stats['average'],
            'stats': stats,
            'problem_areas': problem_areas
        }
    
    def _rgb_to_coverage_map(self, rgb_data):
        """
        RGB 이미지 데이터를 잉크 커버리지 맵으로 변환
        
        Args:
            rgb_data: numpy array (height, width, 3)
            
        Returns:
            numpy array: 커버리지 맵 (height, width)
        """
        # 간단한 RGB to CMYK 변환
        # K = 1 - max(R, G, B)
        # C = (1-R-K)/(1-K)
        # M = (1-G-K)/(1-K)  
        # Y = (1-B-K)/(1-K)
        
        # 정규화 (0-1 범위로)
        rgb_norm = rgb_data / 255.0
        
        # K 채널 계산
        k = 1 - np.max(rgb_norm, axis=2)
        
        # 각 픽셀의 총 잉크량 계산
        coverage = np.zeros(rgb_data.shape[:2])
        
        for i in range(rgb_data.shape[0]):
            for j in range(rgb_data.shape[1]):
                r, g, b = rgb_norm[i, j]
                k_val = k[i, j]
                
                if k_val < 1:
                    c = (1 - r - k_val) / (1 - k_val)
                    m = (1 - g - k_val) / (1 - k_val)
                    y = (1 - b - k_val) / (1 - k_val)
                else:
                    c = m = y = 0
                
                # 총 잉크량 (0-400% 범위)
                total = (c + m + y + k_val) * 100
                coverage[i, j] = min(total, 400)
        
        return coverage
    
    def _cmyk_to_coverage_map(self, cmyk_data):
        """
        CMYK 이미지 데이터를 잉크 커버리지 맵으로 변환
        
        Args:
            cmyk_data: numpy array (height, width, 4)
            
        Returns:
            numpy array: 커버리지 맵 (height, width)
        """
        # 각 채널을 퍼센트로 변환하고 합산
        coverage = np.sum(cmyk_data, axis=2) / 255.0 * 100
        return np.minimum(coverage, 400)  # 최대 400%
    
    def _find_problem_areas(self, coverage_map, threshold):
        """
        임계값을 초과하는 문제 영역 찾기
        
        Args:
            coverage_map: 커버리지 맵
            threshold: 임계값 (%)
            
        Returns:
            list: 문제 영역 정보
        """
        # 임계값 초과 픽셀 찾기
        problem_mask = coverage_map > threshold
        
        if not np.any(problem_mask):
            return []
        
        # 연결된 영역 찾기 (간단한 구현)
        problem_areas = []
        
        # 전체 문제 픽셀 수와 비율
        total_pixels = coverage_map.size
        problem_pixels = np.sum(problem_mask)
        problem_percent = (problem_pixels / total_pixels) * 100
        
        if problem_percent > 0.1:  # 0.1% 이상일 때만 보고
            problem_areas.append({
                'type': 'high_coverage',
                'threshold': threshold,
                'affected_percent': problem_percent,
                'max_found': float(np.max(coverage_map[problem_mask]))
            })
        
        return problem_areas
    
    def generate_heatmap(self, pdf_path, page_num, output_path=None):
        """
        특정 페이지의 잉크량 히트맵 생성 (선택적 기능)
        
        Args:
            pdf_path: PDF 파일 경로
            page_num: 페이지 번호 (1-based)
            output_path: 출력 이미지 경로
            
        Returns:
            str: 생성된 이미지 경로
        """
        try:
            import matplotlib.pyplot as plt
            import matplotlib.colors as mcolors
            
            # PDF 열기
            doc = fitz.open(pdf_path)
            page = doc[page_num - 1]
            
            # 페이지 렌더링
            zoom = 2  # 2배 확대
            matrix = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=matrix, alpha=False)
            
            # 커버리지 맵 생성
            img_data = np.frombuffer(pix.samples, dtype=np.uint8)
            if pix.n == 3:
                img_data = img_data.reshape(pix.height, pix.width, 3)
                coverage_map = self._rgb_to_coverage_map(img_data)
            else:
                # 기타 처리
                coverage_map = np.zeros((pix.height, pix.width))
            
            # 히트맵 생성
            fig, ax = plt.subplots(figsize=(10, 14))
            
            # 색상 맵 설정 (녹색-노란색-빨간색)
            colors = ['#00ff00', '#ffff00', '#ff0000', '#800080']
            n_bins = 100
            cmap = mcolors.LinearSegmentedColormap.from_list('ink', colors, N=n_bins)
            
            # 히트맵 그리기
            im = ax.imshow(coverage_map, cmap=cmap, vmin=0, vmax=400)
            
            # 컬러바 추가
            cbar = plt.colorbar(im, ax=ax)
            cbar.set_label('잉크량 (%)', rotation=270, labelpad=20)
            
            # 제목 설정
            ax.set_title(f'페이지 {page_num} 잉크량 히트맵', fontsize=16, pad=20)
            ax.axis('off')
            
            # 저장
            if output_path is None:
                output_path = f"heatmap_page_{page_num}.png"
            
            plt.tight_layout()
            plt.savefig(output_path, dpi=150, bbox_inches='tight')
            plt.close()
            
            doc.close()
            
            print(f"  ✓ 히트맵 생성 완료: {output_path}")
            return output_path
            
        except ImportError:
            print("  ⚠️  matplotlib가 설치되지 않아 히트맵을 생성할 수 없습니다")
            return None
        except Exception as e:
            print(f"  ❌ 히트맵 생성 실패: {e}")
            return None
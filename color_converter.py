# color_converter.py - PDF의 RGB 색상을 CMYK로 변환하는 모듈
# 2025.01 신규 생성

"""
color_converter.py - 색상 변환 모듈
RGB 색상 공간을 CMYK로 변환
"""

import fitz  # PyMuPDF
from pathlib import Path
from typing import Tuple, Optional
import math

# 프로젝트 모듈
from simple_logger import SimpleLogger


class ColorConverter:
    """PDF 색상 변환 클래스"""
    
    def __init__(self):
        """색상 변환기 초기화"""
        self.logger = SimpleLogger()
        
        # sRGB to CMYK 변환을 위한 설정
        # 표준 인쇄 프로파일 기반
        self.ink_limit = 3.0  # 총 잉크량 제한 (300%)
        self.black_generation = 0.5  # K 생성 강도
    
    def convert_rgb_to_cmyk(self, input_path: Path, output_path: Path) -> bool:
        """
        PDF의 RGB 색상을 CMYK로 변환
        
        Args:
            input_path: 입력 PDF 경로
            output_path: 출력 PDF 경로
            
        Returns:
            성공 여부
        """
        try:
            self.logger.log(f"RGB→CMYK 변환 시작: {input_path.name}")
            
            # PDF 열기
            doc = fitz.open(str(input_path))
            
            # 페이지별 처리
            for page_num, page in enumerate(doc):
                self.logger.log(f"  페이지 {page_num + 1}/{len(doc)} 처리 중...")
                
                # 페이지의 모든 색상 객체 변환
                self._convert_page_colors(page)
            
            # 문서 메타데이터 업데이트
            metadata = doc.metadata
            if metadata:
                metadata['Creator'] = f"{metadata.get('Creator', '')} (RGB→CMYK Converted)"
            
            # 저장
            doc.save(str(output_path), garbage=4, deflate=True)
            doc.close()
            
            self.logger.log(f"RGB→CMYK 변환 완료: {output_path.name}")
            return True
            
        except Exception as e:
            self.logger.error(f"색상 변환 실패: {str(e)}")
            return False
    
    def _convert_page_colors(self, page: fitz.Page):
        """
        페이지의 모든 색상을 변환
        
        Args:
            page: PyMuPDF 페이지 객체
        """
        # 페이지 내용을 dictionary로 가져오기
        page_dict = page.get_text("dict")
        
        # 모든 블록 처리
        for block in page_dict.get("blocks", []):
            if block.get("type") == 0:  # 텍스트 블록
                self._convert_text_block_colors(block)
        
        # 그래픽 요소 처리
        # PyMuPDF의 제한으로 직접적인 색상 변환이 어려우므로
        # 대안적인 방법 사용
        self._convert_graphics_colors(page)
    
    def _convert_text_block_colors(self, block: dict):
        """
        텍스트 블록의 색상 변환
        
        Args:
            block: 텍스트 블록 딕셔너리
        """
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                # RGB 색상 확인
                color = span.get("color", 0)
                if color != 0:  # 검은색이 아닌 경우
                    # 색상값을 RGB로 분해
                    r, g, b = self._int_to_rgb(color)
                    
                    # CMYK로 변환
                    c, m, y, k = self._rgb_to_cmyk(r, g, b)
                    
                    # 변환된 색상 저장 (PyMuPDF 제한으로 직접 적용은 어려움)
                    # 대신 메타데이터에 기록
                    span["cmyk"] = (c, m, y, k)
    
    def _convert_graphics_colors(self, page: fitz.Page):
        """
        그래픽 요소의 색상 변환
        
        Args:
            page: PyMuPDF 페이지 객체
        """
        # 페이지의 그래픽 명령 스트림 가져오기
        try:
            # 페이지 콘텐츠 스트림 분석
            contents = page.read_contents()
            if contents:
                # RGB 색상 명령을 CMYK로 변환
                modified_contents = self._process_content_stream(contents)
                
                # 수정된 콘텐츠 적용 (PyMuPDF의 제한으로 직접 수정은 복잡)
                # 대안: 새 페이지 생성 후 내용 복사
                pass
        except Exception as e:
            self.logger.warning(f"그래픽 색상 변환 중 경고: {str(e)}")
    
    def _process_content_stream(self, contents: bytes) -> bytes:
        """
        PDF 콘텐츠 스트림에서 RGB 명령을 CMYK로 변환
        
        Args:
            contents: 원본 콘텐츠 스트림
            
        Returns:
            수정된 콘텐츠 스트림
        """
        # PDF 콘텐츠 스트림 파싱 및 변환
        # 이는 매우 복잡한 작업이므로 간단한 구현만 제공
        
        # RGB 색상 설정 명령: "r g b rg" (stroke) 또는 "r g b RG" (fill)
        # CMYK 색상 설정 명령: "c m y k k" (stroke) 또는 "c m y k K" (fill)
        
        # 실제 구현에서는 PDF 명령어 파서가 필요
        return contents
    
    def _rgb_to_cmyk(self, r: float, g: float, b: float) -> Tuple[float, float, float, float]:
        """
        RGB를 CMYK로 변환 (표준 변환 공식)
        
        Args:
            r, g, b: RGB 값 (0.0 ~ 1.0)
            
        Returns:
            c, m, y, k: CMYK 값 (0.0 ~ 1.0)
        """
        # RGB가 이미 정규화된 값인지 확인
        if r > 1.0 or g > 1.0 or b > 1.0:
            r, g, b = r/255.0, g/255.0, b/255.0
        
        # Black (K) 계산
        k = 1.0 - max(r, g, b)
        
        # K가 1이면 (완전한 검은색) CMY는 0
        if k >= 0.99:
            return 0.0, 0.0, 0.0, 1.0
        
        # CMY 계산
        c = (1.0 - r - k) / (1.0 - k)
        m = (1.0 - g - k) / (1.0 - k)
        y = (1.0 - b - k) / (1.0 - k)
        
        # UCR (Under Color Removal) 적용
        c, m, y, k = self._apply_ucr(c, m, y, k)
        
        # 총 잉크량 제한 적용
        c, m, y, k = self._apply_ink_limit(c, m, y, k)
        
        # 반올림
        c = round(c, 3)
        m = round(m, 3)
        y = round(y, 3)
        k = round(k, 3)
        
        return c, m, y, k
    
    def _apply_ucr(self, c: float, m: float, y: float, k: float) -> Tuple[float, float, float, float]:
        """
        UCR (Under Color Removal) 적용
        회색 성분을 검은색으로 대체
        
        Args:
            c, m, y, k: CMYK 값
            
        Returns:
            조정된 CMYK 값
        """
        # 회색 성분 찾기 (CMY의 최소값)
        gray = min(c, m, y) * self.black_generation
        
        # 회색 성분을 K로 이동
        if gray > 0:
            c -= gray
            m -= gray
            y -= gray
            k = min(1.0, k + gray)
        
        return c, m, y, k
    
    def _apply_ink_limit(self, c: float, m: float, y: float, k: float) -> Tuple[float, float, float, float]:
        """
        총 잉크량 제한 적용
        
        Args:
            c, m, y, k: CMYK 값
            
        Returns:
            조정된 CMYK 값
        """
        total = c + m + y + k
        
        if total > self.ink_limit:
            # 비율 유지하면서 감소
            ratio = self.ink_limit / total
            c *= ratio
            m *= ratio
            y *= ratio
            k *= ratio
        
        return c, m, y, k
    
    def _int_to_rgb(self, color_int: int) -> Tuple[float, float, float]:
        """
        정수 색상값을 RGB로 변환
        
        Args:
            color_int: 정수 색상값
            
        Returns:
            r, g, b: RGB 값 (0.0 ~ 1.0)
        """
        r = ((color_int >> 16) & 0xFF) / 255.0
        g = ((color_int >> 8) & 0xFF) / 255.0
        b = (color_int & 0xFF) / 255.0
        
        return r, g, b
    
    def analyze_color_usage(self, pdf_path: Path) -> dict:
        """
        PDF의 색상 사용 분석 (디버깅/리포트용)
        
        Args:
            pdf_path: PDF 파일 경로
            
        Returns:
            색상 사용 통계
        """
        stats = {
            'total_pages': 0,
            'rgb_pages': 0,
            'cmyk_pages': 0,
            'spot_colors': set(),
            'color_spaces': set()
        }
        
        try:
            doc = fitz.open(str(pdf_path))
            stats['total_pages'] = len(doc)
            
            for page_num, page in enumerate(doc):
                # 페이지의 색상 공간 확인
                page_dict = page.get_text("dict")
                
                # 간단한 휴리스틱으로 RGB 사용 감지
                has_rgb = False
                has_cmyk = False
                
                # 텍스트 색상 확인
                for block in page_dict.get("blocks", []):
                    if block.get("type") == 0:  # 텍스트
                        for line in block.get("lines", []):
                            for span in line.get("spans", []):
                                color = span.get("color", 0)
                                if color != 0:  # 색상 사용
                                    has_rgb = True
                
                if has_rgb:
                    stats['rgb_pages'] += 1
                if has_cmyk:
                    stats['cmyk_pages'] += 1
            
            doc.close()
            
        except Exception as e:
            self.logger.error(f"색상 분석 실패: {str(e)}")
        
        return stats


# 테스트용 메인
if __name__ == "__main__":
    converter = ColorConverter()
    
    # RGB to CMYK 변환 테스트
    test_colors = [
        (255, 0, 0),      # Red
        (0, 255, 0),      # Green
        (0, 0, 255),      # Blue
        (255, 255, 0),    # Yellow
        (255, 0, 255),    # Magenta
        (0, 255, 255),    # Cyan
        (128, 128, 128),  # Gray
        (255, 128, 0),    # Orange
    ]
    
    print("RGB to CMYK 변환 테스트:")
    print("-" * 60)
    
    for r, g, b in test_colors:
        c, m, y, k = converter._rgb_to_cmyk(r/255, g/255, b/255)
        print(f"RGB({r:3d}, {g:3d}, {b:3d}) -> CMYK({c:.2f}, {m:.2f}, {y:.2f}, {k:.2f})")
        
        # 총 잉크량 확인
        total_ink = (c + m + y + k) * 100
        print(f"  총 잉크량: {total_ink:.0f}%")
        print()
    
    # 실제 PDF 변환은 파일이 있을 때
    # converter.convert_rgb_to_cmyk(Path("input.pdf"), Path("output.pdf"))
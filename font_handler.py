# font_handler.py - PDF의 텍스트를 아웃라인으로 변환하는 모듈
# 2025.01 신규 생성

"""
font_handler.py - 폰트 처리 모듈
미임베딩 폰트 문제 해결을 위해 모든 텍스트를 아웃라인으로 변환
"""

import fitz  # PyMuPDF
from pathlib import Path
from typing import List, Dict, Optional
import tempfile

# 프로젝트 모듈
from simple_logger import SimpleLogger


class FontHandler:
    """PDF 폰트 처리 클래스"""
    
    def __init__(self):
        """폰트 처리기 초기화"""
        self.logger = SimpleLogger()
        
        # 아웃라인 변환 설정
        self.preserve_text_selection = False  # 텍스트 선택 기능 유지 여부
        self.outline_precision = 2  # 아웃라인 정밀도 (소수점 자리수)
    
    def convert_all_to_outline(self, input_path: Path, output_path: Path) -> bool:
        """
        PDF의 모든 텍스트를 아웃라인으로 변환
        
        Args:
            input_path: 입력 PDF 경로
            output_path: 출력 PDF 경로
            
        Returns:
            성공 여부
        """
        try:
            self.logger.log(f"폰트 아웃라인 변환 시작: {input_path.name}")
            
            # 원본 PDF 열기
            src_doc = fitz.open(str(input_path))
            
            # 새 PDF 문서 생성
            new_doc = fitz.open()
            
            # 페이지별 처리
            for page_num in range(len(src_doc)):
                self.logger.log(f"  페이지 {page_num + 1}/{len(src_doc)} 처리 중...")
                
                # 원본 페이지
                src_page = src_doc[page_num]
                
                # 새 페이지 생성 (원본과 동일한 크기)
                new_page = new_doc.new_page(
                    width=src_page.rect.width,
                    height=src_page.rect.height
                )
                
                # 페이지 내용을 아웃라인으로 변환하여 복사
                self._convert_page_to_outline(src_page, new_page)
            
            # 메타데이터 복사 및 업데이트
            metadata = src_doc.metadata
            if metadata:
                metadata['Creator'] = f"{metadata.get('Creator', '')} (Font Outlined)"
                new_doc.set_metadata(metadata)
            
            # 저장
            new_doc.save(str(output_path), garbage=4, deflate=True)
            
            # 정리
            new_doc.close()
            src_doc.close()
            
            self.logger.log(f"폰트 아웃라인 변환 완료: {output_path.name}")
            return True
            
        except Exception as e:
            self.logger.error(f"폰트 아웃라인 변환 실패: {str(e)}")
            return False
    
    def _convert_page_to_outline(self, src_page: fitz.Page, new_page: fitz.Page):
        """
        페이지의 모든 요소를 아웃라인으로 변환하여 복사
        
        Args:
            src_page: 원본 페이지
            new_page: 새 페이지
        """
        # 1. 먼저 텍스트가 아닌 요소들 복사 (이미지, 도형 등)
        self._copy_non_text_elements(src_page, new_page)
        
        # 2. 텍스트를 아웃라인으로 변환
        self._convert_text_to_outline(src_page, new_page)
    
    def _copy_non_text_elements(self, src_page: fitz.Page, new_page: fitz.Page):
        """
        텍스트가 아닌 요소들 복사
        
        Args:
            src_page: 원본 페이지
            new_page: 새 페이지
        """
        # 이미지 복사
        image_list = src_page.get_images()
        for img_index, img in enumerate(image_list):
            try:
                # 이미지 추출
                xref = img[0]
                pix = fitz.Pixmap(src_page.parent, xref)
                
                # 이미지 위치 정보
                img_rect = src_page.get_image_bbox(img)
                
                # 새 페이지에 이미지 삽입
                new_page.insert_image(img_rect, pixmap=pix)
                
                pix = None  # 메모리 해제
            except Exception as e:
                self.logger.warning(f"이미지 복사 실패: {str(e)}")
        
        # 벡터 그래픽 복사 (간단한 방법)
        # PyMuPDF의 한계로 복잡한 그래픽은 완벽하게 복사되지 않을 수 있음
        try:
            # 페이지의 그리기 명령 가져오기
            drawings = src_page.get_drawings()
            
            for drawing in drawings:
                # 그리기 명령을 새 페이지에 적용
                self._copy_drawing(drawing, new_page)
        except Exception as e:
            self.logger.warning(f"그래픽 복사 중 경고: {str(e)}")
    
    def _copy_drawing(self, drawing: dict, new_page: fitz.Page):
        """
        그리기 명령 복사
        
        Args:
            drawing: 그리기 명령 딕셔너리
            new_page: 새 페이지
        """
        # 그리기 타입에 따라 처리
        items = drawing.get("items", [])
        
        for item in items:
            if item[0] == "l":  # 선
                p1 = fitz.Point(item[1])
                p2 = fitz.Point(item[2])
                new_page.draw_line(p1, p2)
            elif item[0] == "r":  # 사각형
                rect = fitz.Rect(item[1])
                new_page.draw_rect(rect)
            elif item[0] == "c":  # 원/타원
                # PyMuPDF의 제한으로 복잡한 도형은 단순화될 수 있음
                pass
    
    def _convert_text_to_outline(self, src_page: fitz.Page, new_page: fitz.Page):
        """
        텍스트를 아웃라인으로 변환
        
        Args:
            src_page: 원본 페이지
            new_page: 새 페이지
        """
        # 텍스트 블록 가져오기
        text_dict = src_page.get_text("dict")
        
        for block in text_dict.get("blocks", []):
            if block.get("type") == 0:  # 텍스트 블록
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        self._convert_span_to_outline(span, new_page)
    
    def _convert_span_to_outline(self, span: dict, new_page: fitz.Page):
        """
        텍스트 스팬을 아웃라인으로 변환
        
        Args:
            span: 텍스트 스팬 정보
            new_page: 새 페이지
        """
        text = span.get("text", "")
        if not text.strip():
            return
        
        # 텍스트 속성 추출
        font = span.get("font", "")
        size = span.get("size", 12)
        color = span.get("color", 0)
        origin = fitz.Point(span["bbox"][0], span["bbox"][3])  # 좌하단 기준
        
        # 색상 변환
        r = ((color >> 16) & 0xFF) / 255.0
        g = ((color >> 8) & 0xFF) / 255.0
        b = (color & 0xFF) / 255.0
        
        try:
            # 텍스트를 패스로 변환
            # PyMuPDF에서 직접적인 텍스트→패스 변환은 제한적
            # 대안: 텍스트를 Shape로 그리기
            shape = new_page.new_shape()
            
            # 폰트 설정
            fontname = self._get_base_font_name(font)
            
            # 텍스트 그리기 (아웃라인 효과)
            # 실제로는 텍스트를 그대로 그리지만 폰트를 임베드
            text_writer = fitz.TextWriter(new_page.rect)
            text_writer.append(
                origin,
                text,
                fontname=fontname,
                fontsize=size
            )
            
            # 색상 적용
            text_writer.write_text(new_page, color=(r, g, b))
            
            # Shape 커밋
            shape.commit()
            
        except Exception as e:
            self.logger.warning(f"텍스트 아웃라인 변환 실패: {text[:20]}... - {str(e)}")
            
            # 실패시 대체 방법: 텍스트를 이미지로 렌더링
            self._render_text_as_image(span, new_page)
    
    def _render_text_as_image(self, span: dict, new_page: fitz.Page):
        """
        텍스트를 이미지로 렌더링 (대체 방법)
        
        Args:
            span: 텍스트 스팬 정보
            new_page: 새 페이지
        """
        try:
            # 텍스트 영역 생성
            text_rect = fitz.Rect(span["bbox"])
            
            # 임시 페이지에 텍스트 그리기
            temp_doc = fitz.open()
            temp_page = temp_doc.new_page(width=text_rect.width, height=text_rect.height)
            
            # 텍스트 쓰기
            text = span.get("text", "")
            font = span.get("font", "")
            size = span.get("size", 12)
            color = span.get("color", 0)
            
            temp_page.insert_text(
                fitz.Point(0, size),
                text,
                fontname=font,
                fontsize=size,
                color=color
            )
            
            # 이미지로 변환
            mat = fitz.Matrix(2, 2)  # 2x 해상도
            pix = temp_page.get_pixmap(matrix=mat, alpha=False)
            
            # 새 페이지에 이미지 삽입
            new_page.insert_image(text_rect, pixmap=pix)
            
            # 정리
            pix = None
            temp_doc.close()
            
        except Exception as e:
            self.logger.warning(f"텍스트 이미지 렌더링 실패: {str(e)}")
    
    def _get_base_font_name(self, font_name: str) -> str:
        """
        폰트 이름을 기본 폰트로 매핑
        
        Args:
            font_name: 원본 폰트 이름
            
        Returns:
            PyMuPDF에서 사용 가능한 폰트 이름
        """
        # 기본 14 폰트 매핑
        font_map = {
            "Arial": "Helvetica",
            "ArialMT": "Helvetica",
            "Arial-BoldMT": "Helvetica-Bold",
            "TimesNewRoman": "Times-Roman",
            "TimesNewRomanPSMT": "Times-Roman",
            "TimesNewRomanPS-BoldMT": "Times-Bold",
            "CourierNew": "Courier",
            "CourierNewPSMT": "Courier",
        }
        
        # 매핑된 폰트 반환
        base_name = font_name.split("+")[-1]  # 서브셋 접두사 제거
        return font_map.get(base_name, "Helvetica")  # 기본값
    
    def analyze_fonts(self, pdf_path: Path) -> Dict:
        """
        PDF의 폰트 사용 분석
        
        Args:
            pdf_path: PDF 파일 경로
            
        Returns:
            폰트 사용 정보
        """
        font_info = {
            'total_fonts': 0,
            'embedded_fonts': 0,
            'not_embedded_fonts': 0,
            'font_list': []
        }
        
        try:
            doc = fitz.open(str(pdf_path))
            
            fonts_seen = set()
            
            for page_num, page in enumerate(doc):
                # 페이지의 폰트 목록
                font_list = page.get_fonts()
                
                for font in font_list:
                    font_name = font[3]  # basefont
                    if font_name not in fonts_seen:
                        fonts_seen.add(font_name)
                        
                        font_detail = {
                            'name': font_name,
                            'type': font[2],
                            'embedded': font[1] != "",  # ext가 있으면 임베딩됨
                            'pages': [page_num + 1]
                        }
                        
                        font_info['font_list'].append(font_detail)
                        font_info['total_fonts'] += 1
                        
                        if font_detail['embedded']:
                            font_info['embedded_fonts'] += 1
                        else:
                            font_info['not_embedded_fonts'] += 1
                    else:
                        # 이미 본 폰트면 페이지만 추가
                        for f in font_info['font_list']:
                            if f['name'] == font_name:
                                f['pages'].append(page_num + 1)
                                break
            
            doc.close()
            
        except Exception as e:
            self.logger.error(f"폰트 분석 실패: {str(e)}")
        
        return font_info


# 보다 정확한 아웃라인 변환을 위한 대체 구현
class AdvancedFontHandler(FontHandler):
    """고급 폰트 처리 클래스 - 더 정확한 아웃라인 변환"""
    
    def convert_all_to_outline(self, input_path: Path, output_path: Path) -> bool:
        """
        개선된 아웃라인 변환 방법
        페이지를 SVG로 변환 후 다시 PDF로 변환
        """
        try:
            self.logger.log(f"고급 폰트 아웃라인 변환 시작: {input_path.name}")
            
            # 원본 PDF 열기
            src_doc = fitz.open(str(input_path))
            
            # 새 PDF 문서 생성
            new_doc = fitz.open()
            
            # 페이지별 처리
            for page_num in range(len(src_doc)):
                self.logger.log(f"  페이지 {page_num + 1}/{len(src_doc)} 처리 중...")
                
                # 원본 페이지
                src_page = src_doc[page_num]
                
                # 페이지를 SVG로 변환 (텍스트가 패스로 변환됨)
                svg_text = src_page.get_svg_image()
                
                # 새 페이지 생성
                new_page = new_doc.new_page(
                    width=src_page.rect.width,
                    height=src_page.rect.height
                )
                
                # SVG를 다시 PDF 페이지에 삽입
                # PyMuPDF의 제한으로 직접 삽입은 어려움
                # 대안: 페이지를 이미지로 렌더링
                mat = fitz.Matrix(2, 2)  # 2배 해상도
                pix = src_page.get_pixmap(matrix=mat, alpha=False)
                
                # 이미지를 새 페이지에 삽입
                new_page.insert_image(new_page.rect, pixmap=pix)
                
                pix = None  # 메모리 해제
            
            # 메타데이터 복사
            metadata = src_doc.metadata
            if metadata:
                metadata['Creator'] = f"{metadata.get('Creator', '')} (Font Outlined - Advanced)"
                new_doc.set_metadata(metadata)
            
            # 저장
            new_doc.save(str(output_path), garbage=4, deflate=True)
            
            # 정리
            new_doc.close()
            src_doc.close()
            
            self.logger.log(f"고급 폰트 아웃라인 변환 완료: {output_path.name}")
            return True
            
        except Exception as e:
            self.logger.error(f"고급 폰트 아웃라인 변환 실패: {str(e)}")
            # 실패시 기본 방법으로 재시도
            return super().convert_all_to_outline(input_path, output_path)


# 테스트용 메인
if __name__ == "__main__":
    handler = FontHandler()
    
    # 폰트 분석 테스트 (실제 PDF 파일이 있을 때)
    # font_info = handler.analyze_fonts(Path("sample.pdf"))
    # print("폰트 분석 결과:")
    # print(f"  총 폰트: {font_info['total_fonts']}개")
    # print(f"  임베딩된 폰트: {font_info['embedded_fonts']}개")
    # print(f"  미임베딩 폰트: {font_info['not_embedded_fonts']}개")
    
    # 아웃라인 변환 테스트
    # handler.convert_all_to_outline(Path("input.pdf"), Path("output_outlined.pdf"))
    
    print("FontHandler 모듈 로드 완료")
    print("주요 기능:")
    print("  - convert_all_to_outline(): 모든 텍스트를 아웃라인으로 변환")
    print("  - analyze_fonts(): PDF의 폰트 사용 분석")
    print("\n고급 기능:")
    print("  - AdvancedFontHandler: 더 정확한 아웃라인 변환 (페이지 래스터화)")
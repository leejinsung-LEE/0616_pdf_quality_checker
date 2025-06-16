# thumbnail_generator.py - PDF 썸네일 생성
# PDF 파일의 첫 페이지를 이미지로 변환하여 HTML 보고서에 포함

"""
thumbnail_generator.py - PDF 썸네일 생성기
PyMuPDF를 사용하여 PDF 첫 페이지의 미리보기 이미지 생성
"""

import fitz  # PyMuPDF
import base64
from pathlib import Path
from io import BytesIO
import os

class ThumbnailGenerator:
    """PDF 썸네일 생성 클래스"""
    
    def __init__(self, cache_dir="cache/thumbnails"):
        """
        썸네일 생성기 초기화
        
        Args:
            cache_dir: 썸네일 캐시 디렉토리
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # 기본 설정
        self.max_width = 300  # 최대 너비 (픽셀)
        self.max_height = 400  # 최대 높이 (픽셀)
        self.quality = 85  # JPEG 품질 (1-100)
        
    def generate_thumbnail(self, pdf_path, page_num=0, use_cache=True):
        """
        PDF 파일의 썸네일 생성
        
        Args:
            pdf_path: PDF 파일 경로
            page_num: 페이지 번호 (0부터 시작)
            use_cache: 캐시 사용 여부
            
        Returns:
            dict: 썸네일 정보 {
                'data_url': base64 인코딩된 이미지 데이터 URL,
                'width': 썸네일 너비,
                'height': 썸네일 높이,
                'page_count': 전체 페이지 수
            }
        """
        pdf_path = Path(pdf_path)
        
        # 캐시 확인
        if use_cache:
            cached = self._get_cached_thumbnail(pdf_path)
            if cached:
                return cached
        
        try:
            # PDF 열기
            doc = fitz.open(pdf_path)
            
            # 전체 페이지 수
            page_count = len(doc)
            
            # 페이지 번호 검증
            if page_num >= page_count:
                page_num = 0
            
            # 페이지 가져오기
            page = doc[page_num]
            
            # 썸네일 크기 계산
            rect = page.rect
            page_width = rect.width
            page_height = rect.height
            
            # 비율 유지하면서 크기 조정
            scale_x = self.max_width / page_width
            scale_y = self.max_height / page_height
            scale = min(scale_x, scale_y)
            
            # 매트릭스 생성 (크기 조정용)
            mat = fitz.Matrix(scale, scale)
            
            # 페이지를 이미지로 렌더링
            pix = page.get_pixmap(matrix=mat, alpha=False)
            
            # PNG 바이트 데이터로 변환
            img_data = pix.tobytes("png")
            
            # Base64 인코딩
            img_base64 = base64.b64encode(img_data).decode('utf-8')
            data_url = f"data:image/png;base64,{img_base64}"
            
            # 썸네일 정보
            thumbnail_info = {
                'data_url': data_url,
                'width': pix.width,
                'height': pix.height,
                'page_count': page_count,
                'page_num': page_num + 1  # 사용자에게는 1부터 시작
            }
            
            # 캐시 저장
            if use_cache:
                self._save_to_cache(pdf_path, thumbnail_info)
            
            # 정리
            doc.close()
            
            return thumbnail_info
            
        except Exception as e:
            # 오류 발생 시 기본 썸네일 반환
            return self._get_error_thumbnail(str(e))
    
    def generate_multi_page_preview(self, pdf_path, max_pages=4):
        """
        여러 페이지 미리보기 생성
        
        Args:
            pdf_path: PDF 파일 경로
            max_pages: 최대 미리보기 페이지 수
            
        Returns:
            list: 각 페이지의 썸네일 정보 리스트
        """
        previews = []
        
        try:
            doc = fitz.open(pdf_path)
            page_count = min(len(doc), max_pages)
            
            for i in range(page_count):
                thumbnail = self.generate_thumbnail(pdf_path, i, use_cache=False)
                previews.append(thumbnail)
            
            doc.close()
            
        except Exception as e:
            # 오류 시 단일 오류 썸네일
            previews.append(self._get_error_thumbnail(str(e)))
        
        return previews
    
    def generate_contact_sheet(self, pdf_path, cols=3, rows=3, page_size=(800, 1000)):
        """
        컨택트 시트 생성 (여러 페이지를 하나의 이미지로)
        
        Args:
            pdf_path: PDF 파일 경로
            cols: 열 수
            rows: 행 수
            page_size: 출력 이미지 크기
            
        Returns:
            str: base64 인코딩된 컨택트 시트 이미지
        """
        try:
            doc = fitz.open(pdf_path)
            total_pages = min(len(doc), cols * rows)
            
            # 각 썸네일 크기
            thumb_width = page_size[0] // cols
            thumb_height = page_size[1] // rows
            
            # 새 페이지 생성 (컨택트 시트)
            contact_doc = fitz.open()
            contact_page = contact_doc.new_page(width=page_size[0], height=page_size[1])
            
            # 각 페이지를 썸네일로 추가
            for i in range(total_pages):
                page = doc[i]
                
                # 위치 계산
                col = i % cols
                row = i // cols
                x = col * thumb_width
                y = row * thumb_height
                
                # 썸네일 영역
                thumb_rect = fitz.Rect(x, y, x + thumb_width, y + thumb_height)
                
                # 페이지 삽입
                contact_page.show_pdf_page(thumb_rect, doc, i)
                
                # 페이지 번호 추가
                text_point = fitz.Point(x + 5, y + thumb_height - 5)
                contact_page.insert_text(
                    text_point,
                    f"Page {i + 1}",
                    fontsize=10,
                    color=(0, 0, 0)
                )
            
            # 컨택트 시트를 이미지로 변환
            pix = contact_page.get_pixmap(alpha=False)
            img_data = pix.tobytes("png")
            img_base64 = base64.b64encode(img_data).decode('utf-8')
            
            # 정리
            doc.close()
            contact_doc.close()
            
            return f"data:image/png;base64,{img_base64}"
            
        except Exception as e:
            return self._get_error_thumbnail(str(e))['data_url']
    
    def _get_cached_thumbnail(self, pdf_path):
        """캐시된 썸네일 가져오기"""
        # 캐시 파일명 생성 (파일명 + 수정시간)
        cache_key = f"{pdf_path.stem}_{int(pdf_path.stat().st_mtime)}"
        cache_file = self.cache_dir / f"{cache_key}.cache"
        
        if cache_file.exists():
            try:
                import json
                with open(cache_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                pass
        
        return None
    
    def _save_to_cache(self, pdf_path, thumbnail_info):
        """썸네일 캐시 저장"""
        try:
            cache_key = f"{pdf_path.stem}_{int(pdf_path.stat().st_mtime)}"
            cache_file = self.cache_dir / f"{cache_key}.cache"
            
            import json
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(thumbnail_info, f)
            
            # 오래된 캐시 정리
            self._clean_old_cache()
            
        except:
            pass  # 캐시 저장 실패는 무시
    
    def _clean_old_cache(self, max_files=100):
        """오래된 캐시 파일 정리"""
        try:
            cache_files = list(self.cache_dir.glob("*.cache"))
            
            if len(cache_files) > max_files:
                # 수정 시간 기준 정렬
                cache_files.sort(key=lambda p: p.stat().st_mtime)
                
                # 오래된 파일 삭제
                for cache_file in cache_files[:-max_files]:
                    cache_file.unlink()
        except:
            pass
    
    def _get_error_thumbnail(self, error_msg=""):
        """오류 발생 시 기본 썸네일"""
        # 간단한 SVG로 오류 썸네일 생성
        svg_content = f"""
        <svg width="200" height="280" xmlns="http://www.w3.org/2000/svg">
            <rect width="200" height="280" fill="#f0f0f0" stroke="#ccc"/>
            <text x="100" y="120" text-anchor="middle" font-family="Arial" font-size="60" fill="#999">📄</text>
            <text x="100" y="180" text-anchor="middle" font-family="Arial" font-size="14" fill="#666">미리보기</text>
            <text x="100" y="200" text-anchor="middle" font-family="Arial" font-size="14" fill="#666">생성 실패</text>
        </svg>
        """
        
        # SVG를 base64로 인코딩
        svg_base64 = base64.b64encode(svg_content.encode('utf-8')).decode('utf-8')
        
        return {
            'data_url': f"data:image/svg+xml;base64,{svg_base64}",
            'width': 200,
            'height': 280,
            'page_count': 0,
            'error': error_msg
        }
    
    def clear_cache(self):
        """모든 캐시 삭제"""
        try:
            for cache_file in self.cache_dir.glob("*.cache"):
                cache_file.unlink()
            return True
        except Exception as e:
            return False


# HTML 보고서에 포함할 썸네일 스타일
THUMBNAIL_STYLE = """
<style>
.pdf-thumbnail {
    position: relative;
    display: inline-block;
    margin: 20px;
    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    border-radius: 8px;
    overflow: hidden;
    background: #f5f5f5;
}

.pdf-thumbnail img {
    display: block;
    max-width: 100%;
    height: auto;
    border-radius: 8px;
}

.pdf-thumbnail .page-indicator {
    position: absolute;
    bottom: 0;
    left: 0;
    right: 0;
    background: rgba(0, 0, 0, 0.7);
    color: white;
    padding: 8px;
    text-align: center;
    font-size: 14px;
}

.pdf-thumbnail .error-message {
    color: #ff4444;
    padding: 20px;
    text-align: center;
}

/* 여러 페이지 미리보기 */
.pdf-preview-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
    gap: 15px;
    margin: 20px 0;
}

.pdf-preview-item {
    position: relative;
    background: #f5f5f5;
    border-radius: 4px;
    overflow: hidden;
    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
    transition: transform 0.2s;
}

.pdf-preview-item:hover {
    transform: scale(1.05);
    box-shadow: 0 4px 8px rgba(0, 0, 0, 0.15);
}

.pdf-preview-item img {
    width: 100%;
    height: auto;
    display: block;
}

.pdf-preview-item .page-num {
    position: absolute;
    bottom: 5px;
    right: 5px;
    background: rgba(0, 0, 0, 0.7);
    color: white;
    padding: 2px 8px;
    border-radius: 3px;
    font-size: 12px;
}
</style>
"""


# 사용 예시
if __name__ == "__main__":
    # 썸네일 생성기 생성
    generator = ThumbnailGenerator()
    
    # 테스트 PDF 파일 경로
    test_pdf = Path("sample.pdf")
    
    if test_pdf.exists():
        # 단일 썸네일 생성
        print("단일 썸네일 생성 중...")
        thumbnail = generator.generate_thumbnail(test_pdf)
        print(f"썸네일 크기: {thumbnail['width']}x{thumbnail['height']}")
        print(f"전체 페이지: {thumbnail['page_count']}")
        
        # HTML 예시
        html_output = f"""
        <html>
        <head>
            {THUMBNAIL_STYLE}
        </head>
        <body>
            <h1>PDF 썸네일 테스트</h1>
            <div class="pdf-thumbnail">
                <img src="{thumbnail['data_url']}" alt="PDF 미리보기">
                <div class="page-indicator">
                    1 / {thumbnail['page_count']} 페이지
                </div>
            </div>
        </body>
        </html>
        """
        
        # HTML 파일로 저장
        with open("thumbnail_test.html", "w", encoding='utf-8') as f:
            f.write(html_output)
        
        print("thumbnail_test.html 파일이 생성되었습니다.")
    else:
        print(f"{test_pdf} 파일을 찾을 수 없습니다.")
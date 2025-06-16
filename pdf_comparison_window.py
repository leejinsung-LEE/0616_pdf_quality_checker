# pdf_comparison_window.py - PDF 비교 검사를 위한 GUI 창
# 두 PDF 파일을 선택하고 비교하는 사용자 인터페이스

"""
pdf_comparison_window.py - PDF 비교 검사 GUI
원본과 수정본을 비교하여 변경사항을 찾는 도구
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
import threading
import webbrowser
from datetime import datetime

# 프로젝트 모듈
from pdf_comparator import PDFComparator
from config import Config
from simple_logger import SimpleLogger


class PDFComparisonWindow:
    """PDF 비교 검사 창"""
    
    def __init__(self, parent=None):
        """
        비교 창 초기화
        
        Args:
            parent: 부모 윈도우
        """
        # 창 생성
        if parent:
            self.window = tk.Toplevel(parent)
        else:
            self.window = tk.Tk()
        
        self.window.title("PDF 비교 검사")
        self.window.geometry("800x600")
        self.window.resizable(True, True)
        
        # 변수들
        self.original_path = tk.StringVar()
        self.modified_path = tk.StringVar()
        self.is_comparing = False
        self.comparison_result = None
        
        # 로거
        self.logger = SimpleLogger()
        
        # UI 생성
        self._create_ui()
        
        # 창 중앙 배치
        self._center_window()
    
    def _center_window(self):
        """창을 화면 중앙에 배치"""
        self.window.update_idletasks()
        width = self.window.winfo_width()
        height = self.window.winfo_height()
        x = (self.window.winfo_screenwidth() // 2) - (width // 2)
        y = (self.window.winfo_screenheight() // 2) - (height // 2)
        self.window.geometry(f'{width}x{height}+{x}+{y}')
    
    def _create_ui(self):
        """UI 구성"""
        # 메인 프레임
        main_frame = ttk.Frame(self.window, padding="20")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 윈도우 크기 조절 설정
        self.window.columnconfigure(0, weight=1)
        self.window.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(3, weight=1)
        
        # 제목
        title_label = ttk.Label(
            main_frame, 
            text="PDF 비교 검사", 
            font=('맑은 고딕', 16, 'bold')
        )
        title_label.grid(row=0, column=0, pady=(0, 20))
        
        # 설명
        desc_label = ttk.Label(
            main_frame,
            text="두 PDF 파일을 비교하여 변경사항을 찾습니다.\n원본 파일과 수정된 파일을 선택해주세요.",
            justify='center'
        )
        desc_label.grid(row=1, column=0, pady=(0, 20))
        
        # 파일 선택 영역
        file_frame = ttk.LabelFrame(main_frame, text="파일 선택", padding="20")
        file_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=(0, 20))
        file_frame.columnconfigure(1, weight=1)
        
        # 원본 파일
        ttk.Label(file_frame, text="원본 PDF:").grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
        ttk.Entry(
            file_frame, 
            textvariable=self.original_path,
            state='readonly'
        ).grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(0, 10))
        ttk.Button(
            file_frame,
            text="찾아보기",
            command=lambda: self._browse_file('original')
        ).grid(row=0, column=2)
        
        # 수정본 파일
        ttk.Label(file_frame, text="수정본 PDF:").grid(row=1, column=0, sticky=tk.W, padx=(0, 10), pady=(10, 0))
        ttk.Entry(
            file_frame,
            textvariable=self.modified_path,
            state='readonly'
        ).grid(row=1, column=1, sticky=(tk.W, tk.E), padx=(0, 10), pady=(10, 0))
        ttk.Button(
            file_frame,
            text="찾아보기",
            command=lambda: self._browse_file('modified')
        ).grid(row=1, column=2, pady=(10, 0))
        
        # 비교 옵션
        option_frame = ttk.LabelFrame(main_frame, text="비교 옵션", padding="20")
        option_frame.grid(row=3, column=0, sticky=(tk.W, tk.E), pady=(0, 20))
        
        # 체크박스 옵션들
        self.text_compare = tk.BooleanVar(value=True)
        self.image_compare = tk.BooleanVar(value=True)
        self.visual_compare = tk.BooleanVar(value=True)
        
        ttk.Checkbutton(
            option_frame,
            text="텍스트 내용 비교",
            variable=self.text_compare
        ).grid(row=0, column=0, sticky=tk.W, padx=(0, 20))
        
        ttk.Checkbutton(
            option_frame,
            text="이미지 비교",
            variable=self.image_compare
        ).grid(row=0, column=1, sticky=tk.W, padx=(0, 20))
        
        ttk.Checkbutton(
            option_frame,
            text="시각적 비교 (픽셀 단위)",
            variable=self.visual_compare
        ).grid(row=0, column=2, sticky=tk.W)
        
        # DPI 설정
        ttk.Label(option_frame, text="비교 해상도:").grid(row=1, column=0, sticky=tk.W, pady=(10, 0))
        self.comparison_dpi = tk.IntVar(value=150)
        dpi_combo = ttk.Combobox(
            option_frame,
            textvariable=self.comparison_dpi,
            values=[100, 150, 200, 300],
            state='readonly',
            width=10
        )
        dpi_combo.grid(row=1, column=1, sticky=tk.W, pady=(10, 0))
        ttk.Label(option_frame, text="DPI").grid(row=1, column=2, sticky=tk.W, pady=(10, 0))
        
        # 진행률 표시
        self.progress_frame = ttk.Frame(main_frame)
        self.progress_frame.grid(row=4, column=0, sticky=(tk.W, tk.E), pady=(0, 20))
        self.progress_frame.columnconfigure(0, weight=1)
        
        self.progress_label = ttk.Label(self.progress_frame, text="")
        self.progress_bar = ttk.Progressbar(self.progress_frame, mode='indeterminate')
        
        # 버튼들
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=5, column=0)
        
        self.compare_button = ttk.Button(
            button_frame,
            text="🔍 비교 시작",
            command=self._start_comparison,
            width=20
        )
        self.compare_button.pack(side=tk.LEFT, padx=5)
        
        self.report_button = ttk.Button(
            button_frame,
            text="📊 리포트 보기",
            command=self._view_report,
            state='disabled',
            width=20
        )
        self.report_button.pack(side=tk.LEFT, padx=5)
        
        ttk.Button(
            button_frame,
            text="❌ 닫기",
            command=self.window.destroy,
            width=20
        ).pack(side=tk.LEFT, padx=5)
    
    def _browse_file(self, file_type):
        """파일 선택 대화상자"""
        filename = filedialog.askopenfilename(
            title=f"{'원본' if file_type == 'original' else '수정본'} PDF 선택",
            filetypes=[("PDF 파일", "*.pdf"), ("모든 파일", "*.*")]
        )
        
        if filename:
            if file_type == 'original':
                self.original_path.set(filename)
            else:
                self.modified_path.set(filename)
    
    def _start_comparison(self):
        """비교 시작"""
        # 파일 확인
        if not self.original_path.get() or not self.modified_path.get():
            messagebox.showwarning("경고", "원본과 수정본 PDF를 모두 선택해주세요.")
            return
        
        if self.original_path.get() == self.modified_path.get():
            messagebox.showwarning("경고", "서로 다른 파일을 선택해주세요.")
            return
        
        # UI 업데이트
        self.is_comparing = True
        self.compare_button.config(state='disabled')
        self.report_button.config(state='disabled')
        
        # 진행률 표시
        self.progress_label.grid(row=0, column=0, pady=(0, 5))
        self.progress_bar.grid(row=1, column=0, sticky=(tk.W, tk.E))
        self.progress_label.config(text="비교 분석 중...")
        self.progress_bar.start()
        
        # 별도 스레드에서 비교 실행
        compare_thread = threading.Thread(target=self._run_comparison)
        compare_thread.daemon = True
        compare_thread.start()
    
    def _run_comparison(self):
        """실제 비교 작업 (스레드)"""
        try:
            # 비교기 생성
            comparator = PDFComparator()
            
            # 설정 적용
            comparator.settings['text_compare'] = self.text_compare.get()
            comparator.settings['image_compare'] = self.image_compare.get()
            comparator.settings['visual_compare'] = self.visual_compare.get()
            comparator.settings['comparison_dpi'] = self.comparison_dpi.get()
            
            # 출력 디렉토리 생성
            output_dir = Config.REPORTS_PATH / f"compare_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            # 비교 실행
            self.logger.log(f"PDF 비교 시작: {Path(self.original_path.get()).name} vs {Path(self.modified_path.get()).name}")
            
            result = comparator.compare(
                Path(self.original_path.get()),
                Path(self.modified_path.get()),
                output_dir
            )
            
            if 'error' in result:
                raise Exception(result['error'])
            
            self.comparison_result = result
            
            # UI 업데이트
            self.window.after(0, self._comparison_complete)
            
        except Exception as e:
            self.logger.error(f"비교 중 오류: {str(e)}")
            self.window.after(0, lambda: self._comparison_error(str(e)))
    
    def _comparison_complete(self):
        """비교 완료 처리"""
        self.is_comparing = False
        self.progress_bar.stop()
        self.progress_bar.grid_remove()
        self.progress_label.grid_remove()
        
        self.compare_button.config(state='normal')
        self.report_button.config(state='normal')
        
        # 결과 요약 표시
        summary = self.comparison_result['summary']
        
        result_text = f"""비교 완료!

전체 일치율: {summary['similarity_percentage']:.1f}%
총 페이지: {summary['total_pages']}
변경된 페이지: {summary['modified_pages']}
총 차이점: {summary['total_differences']}개

리포트가 생성되었습니다."""
        
        # 결과 창 표시
        self._show_result_dialog(result_text)
    
    def _comparison_error(self, error_msg):
        """비교 오류 처리"""
        self.is_comparing = False
        self.progress_bar.stop()
        self.progress_bar.grid_remove()
        self.progress_label.grid_remove()
        
        self.compare_button.config(state='normal')
        
        messagebox.showerror("오류", f"비교 중 오류가 발생했습니다:\n{error_msg}")
    
    def _show_result_dialog(self, message):
        """결과 대화상자"""
        result_window = tk.Toplevel(self.window)
        result_window.title("비교 결과")
        result_window.geometry("400x300")
        
        # 중앙 배치
        result_window.update_idletasks()
        x = (result_window.winfo_screenwidth() // 2) - 200
        y = (result_window.winfo_screenheight() // 2) - 150
        result_window.geometry(f'+{x}+{y}')
        
        # 내용
        frame = ttk.Frame(result_window, padding="20")
        frame.pack(fill='both', expand=True)
        
        # 아이콘과 메시지
        icon_label = ttk.Label(frame, text="✅", font=('Arial', 48))
        icon_label.pack(pady=(0, 20))
        
        msg_label = ttk.Label(frame, text=message, justify='center')
        msg_label.pack(pady=(0, 20))
        
        # 버튼
        button_frame = ttk.Frame(frame)
        button_frame.pack()
        
        ttk.Button(
            button_frame,
            text="리포트 보기",
            command=lambda: [result_window.destroy(), self._view_report()]
        ).pack(side='left', padx=5)
        
        ttk.Button(
            button_frame,
            text="확인",
            command=result_window.destroy
        ).pack(side='left', padx=5)
    
    def _view_report(self):
        """비교 리포트 보기"""
        if not self.comparison_result:
            messagebox.showinfo("정보", "먼저 비교를 실행해주세요.")
            return
        
        # HTML 리포트 경로
        report_path = Path(self.comparison_result['output_dir']) / "comparison_report.html"
        
        if report_path.exists():
            webbrowser.open(str(report_path))
        else:
            messagebox.showerror("오류", "리포트 파일을 찾을 수 없습니다.")


# 빠른 비교를 위한 간단한 다이얼로그
class QuickCompareDialog:
    """빠른 비교 다이얼로그"""
    
    def __init__(self, parent, file1=None, file2=None):
        """
        빠른 비교 다이얼로그
        
        Args:
            parent: 부모 윈도우
            file1: 첫 번째 파일 경로 (선택사항)
            file2: 두 번째 파일 경로 (선택사항)
        """
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("빠른 PDF 비교")
        self.dialog.geometry("500x200")
        self.dialog.resizable(False, False)
        
        # 변수
        self.file1_path = tk.StringVar(value=file1 or "")
        self.file2_path = tk.StringVar(value=file2 or "")
        self.result = None
        
        # UI 생성
        self._create_ui()
        
        # 중앙 배치
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - 250
        y = (self.dialog.winfo_screenheight() // 2) - 100
        self.dialog.geometry(f'+{x}+{y}')
        
        # 모달 다이얼로그로 설정
        self.dialog.transient(parent)
        self.dialog.grab_set()
    
    def _create_ui(self):
        """UI 생성"""
        frame = ttk.Frame(self.dialog, padding="20")
        frame.pack(fill='both', expand=True)
        
        # 설명
        ttk.Label(
            frame,
            text="비교할 두 PDF 파일을 선택하세요:",
            font=('맑은 고딕', 10)
        ).grid(row=0, column=0, columnspan=3, pady=(0, 20))
        
        # 파일 1
        ttk.Label(frame, text="파일 1:").grid(row=1, column=0, sticky=tk.W)
        ttk.Entry(
            frame,
            textvariable=self.file1_path,
            width=40
        ).grid(row=1, column=1, padx=10)
        ttk.Button(
            frame,
            text="...",
            width=3,
            command=lambda: self._browse_file(1)
        ).grid(row=1, column=2)
        
        # 파일 2
        ttk.Label(frame, text="파일 2:").grid(row=2, column=0, sticky=tk.W, pady=(10, 0))
        ttk.Entry(
            frame,
            textvariable=self.file2_path,
            width=40
        ).grid(row=2, column=1, padx=10, pady=(10, 0))
        ttk.Button(
            frame,
            text="...",
            width=3,
            command=lambda: self._browse_file(2)
        ).grid(row=2, column=2, pady=(10, 0))
        
        # 버튼
        button_frame = ttk.Frame(frame)
        button_frame.grid(row=3, column=0, columnspan=3, pady=(20, 0))
        
        ttk.Button(
            button_frame,
            text="비교",
            command=self._compare
        ).pack(side='left', padx=5)
        
        ttk.Button(
            button_frame,
            text="취소",
            command=self.dialog.destroy
        ).pack(side='left', padx=5)
    
    def _browse_file(self, file_num):
        """파일 선택"""
        filename = filedialog.askopenfilename(
            parent=self.dialog,
            title=f"PDF 파일 {file_num} 선택",
            filetypes=[("PDF 파일", "*.pdf")]
        )
        
        if filename:
            if file_num == 1:
                self.file1_path.set(filename)
            else:
                self.file2_path.set(filename)
    
    def _compare(self):
        """비교 실행"""
        if not self.file1_path.get() or not self.file2_path.get():
            messagebox.showwarning("경고", "두 파일을 모두 선택해주세요.")
            return
        
        self.result = (self.file1_path.get(), self.file2_path.get())
        self.dialog.destroy()


# 테스트용
if __name__ == "__main__":
    # 비교 창 테스트
    window = PDFComparisonWindow()
    window.window.mainloop()
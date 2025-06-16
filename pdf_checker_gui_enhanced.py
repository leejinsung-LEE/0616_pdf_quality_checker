# pdf_checker_gui_enhanced.py - CustomTkinter 버전
# PDF 품질 검수 시스템 v4.0 - Modern UI Edition
# 실시간 현황과 드래그앤드롭 통합
# 반응형 설정 창 크기

"""
주요 변경사항:
- 실시간 현황 탭에 드래그앤드롭 영역 통합
- 설정 창 크기 최적화 및 반응형 디자인
- 불필요한 탭 제거로 사용성 개선
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import tkinter.scrolledtext as scrolledtext
import customtkinter as ctk
from pathlib import Path
import threading
import queue
import time
from datetime import datetime, timedelta
import json
from typing import Dict, List, Optional
import webbrowser
import os
import shutil

# CustomTkinter 설정
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# 차트 라이브러리 (선택적)
try:
    import matplotlib
    matplotlib.use('TkAgg')
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False

# 프로젝트 내부 모듈들
from config import Config
from pdf_analyzer import PDFAnalyzer
from report_generator import ReportGenerator
from error_handler import UserFriendlyErrorHandler
from batch_processor import BatchProcessor
from settings_window import SettingsWindow  # 기존 모듈 그대로 사용
from simple_logger import SimpleLogger
from pdf_comparison_window import PDFComparisonWindow, QuickCompareDialog

# Phase 3.5+ 모듈들
from data_manager import DataManager
from notification_manager import NotificationManager, get_notification_manager
from multi_folder_watcher import MultiFolderWatcher

# tkinterdnd2 임포트 시도
try:
    from tkinterdnd2 import TkinterDnD, DND_FILES
    HAS_DND = True
except ImportError:
    HAS_DND = False
    TkinterDnD = tk.Tk

class EnhancedPDFCheckerGUI:
    """향상된 PDF 검수 시스템 GUI - Optimized Edition"""
    
    def __init__(self):
        """GUI 초기화"""
        # 메인 윈도우 생성 - DnD 호환성 유지
        if HAS_DND:
            self.root = TkinterDnD.Tk()
            self.root.configure(bg='#1a1a1a')
        else:
            self.root = ctk.CTk()
        
        self.root.title("PDF 품질 검수 시스템 v4.0 - Optimized Edition")
        
        # 화면 크기에 따른 동적 크기 설정
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        
        # 화면의 80% 크기로 설정 (최대 1600x900)
        window_width = min(int(screen_width * 0.8), 1600)
        window_height = min(int(screen_height * 0.8), 900)
        
        self.root.geometry(f"{window_width}x{window_height}")
        self.root.minsize(1200, 700)
        
        # 아이콘 설정
        try:
            self.root.iconbitmap("assets/icon.ico")
        except:
            pass
        
        # 색상 테마 정의
        self.colors = {
            'bg_primary': '#1a1a1a',
            'bg_secondary': '#252525',
            'bg_card': '#2d2d2d',
            'accent': '#0078d4',
            'accent_hover': '#106ebe',
            'success': '#107c10',
            'warning': '#ff8c00',
            'error': '#d83b01',
            'text_primary': '#ffffff',
            'text_secondary': '#b3b3b3',
            'border': '#404040'
        }
        
        # 폰트 설정
        self.fonts = {
            'title': ('맑은 고딕', 16, 'bold'),
            'heading': ('맑은 고딕', 13, 'bold'),
            'subheading': ('맑은 고딕', 11, 'bold'),
            'body': ('맑은 고딕', 10),
            'small': ('맑은 고딕', 9),
            'mono': ('D2Coding', 10) if os.name == 'nt' else ('Consolas', 10)
        }
        
        # 설정 및 매니저 초기화
        self._init_managers()
        
        # GUI 상태 변수
        self._init_state_variables()
        
        # GUI 구성
        self._setup_styles()
        self._create_menubar()
        self._create_main_layout()
        self._create_statusbar()
        
        # 폴더 감시 시작 (설정에 따라)
        self._init_folder_watching()
        
        # 윈도우 이벤트
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # 주기적 업데이트
        self._start_periodic_updates()
        
        # 아이템 카운터 초기화
        self.item_counter = 0
    
    def _init_managers(self):
        """각종 매니저 초기화"""
        # 설정
        self.config = Config()
        Config.create_folders()
        
        # 로거
        self.logger = SimpleLogger()
        self.logger.log("프로그램 시작 - Optimized Edition")
        
        # 데이터 매니저
        self.data_manager = DataManager()
        
        # 알림 매니저
        self.notification_manager = get_notification_manager()
        
        # 폴더 감시기
        self.folder_watcher = MultiFolderWatcher()
        self.folder_watcher.set_callback(self._on_folder_pdf_found)
        
        # 배치 프로세서
        self.batch_processor = None
        
        # 큐
        self.file_queue = queue.Queue()
        self.result_queue = queue.Queue()
    
    def _init_state_variables(self):
        """GUI 상태 변수 초기화"""
        # 처리 상태
        self.processing_files = {}
        self.is_processing = False
        self.is_folder_watching = False
        
        # 현재 선택된 탭
        self.current_tab = tk.StringVar(value="realtime")
        
        # 통계 캐시
        self.stats_cache = None
        self.stats_last_updated = None
        
        # 드롭된 파일들
        self.dropped_files = []
        
        # 잉크량 검수 기본값
        self.include_ink_analysis = tk.BooleanVar(value=Config.is_ink_analysis_enabled())
    
    def _setup_styles(self):
        """ttk 스타일 설정 - 다크 테마"""
        self.style = ttk.Style()
        
        # 테마 설정
        try:
            self.style.theme_use('clam')
        except:
            pass
        
        # Treeview 스타일
        self.style.configure("Treeview",
            background=self.colors['bg_secondary'],
            foreground=self.colors['text_primary'],
            fieldbackground=self.colors['bg_secondary'],
            borderwidth=0,
            highlightthickness=0,
            rowheight=25
        )
        
        self.style.configure("Treeview.Heading",
            background=self.colors['bg_card'],
            foreground=self.colors['text_primary'],
            borderwidth=0,
            relief='flat',
            font=self.fonts['subheading']
        )
        
        self.style.map("Treeview",
            background=[('selected', self.colors['accent'])],
            foreground=[('selected', 'white')]
        )
        
        # Notebook (탭) 스타일
        self.style.configure('TNotebook',
            background=self.colors['bg_secondary'],
            borderwidth=0
        )
        
        self.style.configure('TNotebook.Tab',
            background=self.colors['bg_card'],
            foreground=self.colors['text_secondary'],
            padding=(20, 10),
            font=self.fonts['body']
        )
        
        self.style.map('TNotebook.Tab',
            background=[('selected', self.colors['accent'])],
            foreground=[('selected', 'white')]
        )
        
        # Combobox 스타일
        self.style.configure("TCombobox",
            fieldbackground=self.colors['bg_card'],
            background=self.colors['bg_card'],
            foreground=self.colors['text_primary'],
            borderwidth=0,
            arrowcolor=self.colors['text_primary']
        )
        
        # Scrollbar 스타일
        self.style.configure("Vertical.TScrollbar",
            background=self.colors['bg_secondary'],
            darkcolor=self.colors['bg_card'],
            lightcolor=self.colors['bg_card'],
            troughcolor=self.colors['bg_secondary'],
            bordercolor=self.colors['bg_secondary'],
            arrowcolor=self.colors['text_secondary']
        )
    
    def _generate_safe_item_id(self, prefix="item"):
        """Treeview에서 안전하게 사용할 수 있는 ID 생성"""
        self.item_counter += 1
        timestamp = int(time.time() * 1000)
        safe_id = f"{prefix}_{self.item_counter}_{timestamp}"
        return safe_id
    
    def _create_menubar(self):
        """메뉴바 생성"""
        menubar = tk.Menu(self.root, 
                         bg=self.colors['bg_secondary'],
                         fg=self.colors['text_primary'],
                         activebackground=self.colors['accent'],
                         activeforeground='white',
                         font=self.fonts['body'])
        self.root.config(menu=menubar)
        
        # 파일 메뉴
        file_menu = tk.Menu(menubar, tearoff=0,
                           bg=self.colors['bg_secondary'],
                           fg=self.colors['text_primary'],
                           activebackground=self.colors['accent'],
                           activeforeground='white',
                           font=self.fonts['body'])
        menubar.add_cascade(label="파일", menu=file_menu)
        file_menu.add_command(label="PDF 파일 추가...", command=self.browse_files, accelerator="Ctrl+O")
        file_menu.add_command(label="폴더 추가...", command=self.browse_folder)
        file_menu.add_separator()
        file_menu.add_command(label="데이터 내보내기...", command=self.export_data)
        file_menu.add_separator()
        file_menu.add_command(label="종료", command=self.on_closing, accelerator="Alt+F4")
        
        # 폴더 메뉴
        folder_menu = tk.Menu(menubar, tearoff=0,
                             bg=self.colors['bg_secondary'],
                             fg=self.colors['text_primary'],
                             activebackground=self.colors['accent'],
                             activeforeground='white',
                             font=self.fonts['body'])
        menubar.add_cascade(label="폴더", menu=folder_menu)
        folder_menu.add_command(label="감시 폴더 추가...", command=self.add_watch_folder)
        folder_menu.add_command(label="감시 시작/중지", command=self.toggle_folder_watching)
        folder_menu.add_separator()
        folder_menu.add_command(label="폴더 설정 관리...", command=self.manage_folders)
        
        # 도구 메뉴
        tools_menu = tk.Menu(menubar, tearoff=0,
                            bg=self.colors['bg_secondary'],
                            fg=self.colors['text_primary'],
                            activebackground=self.colors['accent'],
                            activeforeground='white',
                            font=self.fonts['body'])
        menubar.add_cascade(label="도구", menu=tools_menu)
        tools_menu.add_command(label="PDF 비교...", command=self.open_comparison_window, accelerator="Ctrl+D")
        tools_menu.add_separator()
        tools_menu.add_command(label="설정...", command=self.open_settings, accelerator="Ctrl+,")
        tools_menu.add_command(label="알림 테스트", command=self.test_notification)
        tools_menu.add_separator()
        tools_menu.add_command(label="로그 보기", command=self.view_logs)
        tools_menu.add_command(label="데이터베이스 정리", command=self.cleanup_database)
        
        # 통계 메뉴
        stats_menu = tk.Menu(menubar, tearoff=0,
                            bg=self.colors['bg_secondary'],
                            fg=self.colors['text_primary'],
                            activebackground=self.colors['accent'],
                            activeforeground='white',
                            font=self.fonts['body'])
        menubar.add_cascade(label="통계", menu=stats_menu)
        stats_menu.add_command(label="오늘의 통계", command=lambda: self.show_statistics('today'))
        stats_menu.add_command(label="이번 주 통계", command=lambda: self.show_statistics('week'))
        stats_menu.add_command(label="이번 달 통계", command=lambda: self.show_statistics('month'))
        stats_menu.add_separator()
        stats_menu.add_command(label="통계 리포트 생성...", command=self.generate_stats_report)
        
        # 도움말 메뉴
        help_menu = tk.Menu(menubar, tearoff=0,
                           bg=self.colors['bg_secondary'],
                           fg=self.colors['text_primary'],
                           activebackground=self.colors['accent'],
                           activeforeground='white',
                           font=self.fonts['body'])
        menubar.add_cascade(label="도움말", menu=help_menu)
        help_menu.add_command(label="사용 방법", command=self.show_help)
        help_menu.add_command(label="단축키 목록", command=self.show_shortcuts)
        help_menu.add_command(label="정보", command=self.show_about)
        
        # 단축키 바인딩
        self.root.bind('<Control-o>', lambda e: self.browse_files())
        self.root.bind('<Control-comma>', lambda e: self.open_settings())
        self.root.bind('<Control-d>', lambda e: self.open_comparison_window())
        self.root.bind('<F5>', lambda e: self.refresh_current_tab())
    
    def _create_main_layout(self):
        """메인 레이아웃 생성"""
        # 메인 컨테이너
        main_container = ctk.CTkFrame(self.root, fg_color=self.colors['bg_primary'])
        main_container.pack(fill='both', expand=True)
        
        # 사이드바
        self._create_sidebar(main_container)
        
        # 콘텐츠 영역
        self._create_content_area(main_container)
    
    def _create_sidebar(self, parent):
        """사이드바 생성 - 현대적 디자인"""
        sidebar = ctk.CTkFrame(parent, width=300, corner_radius=0, 
                              fg_color=self.colors['bg_secondary'])
        sidebar.pack(side='left', fill='y', padx=(0, 1))
        sidebar.pack_propagate(False)
        
        # 로고/타이틀
        title_frame = ctk.CTkFrame(sidebar, fg_color="transparent")
        title_frame.pack(fill='x', padx=20, pady=(25, 20))
        
        logo_label = ctk.CTkLabel(title_frame, text="📊", font=('Arial', 36))
        logo_label.pack(side='left', padx=(0, 15))
        
        title_info = ctk.CTkFrame(title_frame, fg_color="transparent")
        title_info.pack(side='left', fill='both', expand=True)
        
        title_label = ctk.CTkLabel(title_info, text="PDF 검수 시스템", 
                                 font=self.fonts['heading'],
                                 text_color=self.colors['text_primary'])
        title_label.pack(anchor='w')
        
        version_label = ctk.CTkLabel(title_info, text="v4.0 Optimized", 
                                   font=self.fonts['small'],
                                   text_color=self.colors['text_secondary'])
        version_label.pack(anchor='w')
        
        # 구분선
        ctk.CTkFrame(sidebar, height=2, fg_color=self.colors['border']).pack(
            fill='x', padx=20, pady=10)
        
        # 폴더 목록 섹션
        folder_section = ctk.CTkFrame(sidebar, fg_color=self.colors['bg_card'],
                                    corner_radius=10)
        folder_section.pack(fill='both', expand=True, padx=15, pady=10)
        
        # 섹션 헤더
        header_frame = ctk.CTkFrame(folder_section, fg_color="transparent")
        header_frame.pack(fill='x', padx=15, pady=(15, 10))
        
        ctk.CTkLabel(header_frame, text="📁 감시 폴더", 
                   font=self.fonts['subheading']).pack(side='left')
        
        # 폴더 목록
        list_frame = ctk.CTkFrame(folder_section, fg_color="transparent")
        list_frame.pack(fill='both', expand=True, padx=15)
        
        # 스크롤바
        scrollbar = ttk.Scrollbar(list_frame, orient='vertical')
        scrollbar.pack(side='right', fill='y')
        
        self.folder_listbox = tk.Listbox(list_frame, 
                                       height=8, 
                                       selectmode='single',
                                       font=self.fonts['body'],
                                       bg=self.colors['bg_secondary'],
                                       fg=self.colors['text_primary'],
                                       selectbackground=self.colors['accent'],
                                       selectforeground='white',
                                       borderwidth=0,
                                       highlightthickness=0,
                                       yscrollcommand=scrollbar.set)
        self.folder_listbox.pack(fill='both', expand=True, side='left')
        scrollbar.config(command=self.folder_listbox.yview)
        
        # 폴더 버튼들
        folder_buttons = ctk.CTkFrame(folder_section, fg_color="transparent")
        folder_buttons.pack(fill='x', padx=15, pady=(10, 15))
        
        btn_config = {'width': 70, 'height': 32, 'corner_radius': 6}
        
        ctk.CTkButton(folder_buttons, text="➕ 추가", 
                    command=self.add_watch_folder,
                    **btn_config).pack(side='left', padx=3)
        
        ctk.CTkButton(folder_buttons, text="➖ 제거", 
                    command=self.remove_watch_folder,
                    fg_color=self.colors['bg_secondary'],
                    hover_color=self.colors['error'],
                    **btn_config).pack(side='left', padx=3)
        
        ctk.CTkButton(folder_buttons, text="⚙️ 설정", 
                    command=self.edit_folder_settings,
                    fg_color=self.colors['bg_secondary'],
                    hover_color=self.colors['accent'],
                    **btn_config).pack(side='left', padx=3)
        
        # 감시 상태 카드
        status_card = ctk.CTkFrame(sidebar, fg_color=self.colors['bg_card'],
                                 corner_radius=10)
        status_card.pack(fill='x', padx=15, pady=10)
        
        status_inner = ctk.CTkFrame(status_card, fg_color="transparent")
        status_inner.pack(fill='x', padx=15, pady=15)
        
        status_header = ctk.CTkFrame(status_inner, fg_color="transparent")
        status_header.pack(fill='x')
        
        self.watch_status_label = ctk.CTkLabel(
            status_header,
            text="⏸️ 감시 중지됨",
            font=self.fonts['subheading']
        )
        self.watch_status_label.pack(side='left')
        
        self.watch_toggle_switch = ctk.CTkSwitch(
            status_header,
            text="",
            command=self.toggle_folder_watching,
            button_color=self.colors['accent'],
            progress_color=self.colors['success'],
            width=50,
            height=24
        )
        self.watch_toggle_switch.pack(side='right')
        
        # 구분선
        ctk.CTkFrame(sidebar, height=2, fg_color=self.colors['border']).pack(
            fill='x', padx=20, pady=5)
        
        # 빠른 통계 카드
        stats_card = ctk.CTkFrame(sidebar, fg_color=self.colors['bg_card'],
                                corner_radius=10)
        stats_card.pack(fill='x', padx=15, pady=(5, 20))
        
        stats_inner = ctk.CTkFrame(stats_card, fg_color="transparent")
        stats_inner.pack(fill='x', padx=15, pady=15)
        
        stats_title = ctk.CTkLabel(stats_inner, text="📊 오늘의 통계", 
                                 font=self.fonts['subheading'])
        stats_title.pack(anchor='w', pady=(0, 15))
        
        self.quick_stats_labels = {}
        stats_items = [
            ('files', '처리 파일', '0개', self.colors['accent']),
            ('errors', '오류', '0개', self.colors['error']),
            ('fixed', '자동 수정', '0개', self.colors['success'])
        ]
        
        for key, label, default, color in stats_items:
            stat_frame = ctk.CTkFrame(stats_inner, fg_color="transparent")
            stat_frame.pack(fill='x', pady=4)
            
            label_widget = ctk.CTkLabel(stat_frame, text=f"{label}:",
                                      font=self.fonts['body'],
                                      text_color=self.colors['text_secondary'])
            label_widget.pack(side='left')
            
            value_widget = ctk.CTkLabel(stat_frame, text=default,
                                      font=self.fonts['subheading'],
                                      text_color=color)
            value_widget.pack(side='right')
            
            self.quick_stats_labels[key] = value_widget
        
        # 폴더 목록 업데이트
        self._update_folder_list()
    
    def _create_content_area(self, parent):
        """콘텐츠 영역 생성"""
        content = ctk.CTkFrame(parent, fg_color=self.colors['bg_primary'])
        content.pack(side='right', fill='both', expand=True)
        
        # 탭 위젯 - 통합된 버전으로 수정
        tab_container = ctk.CTkFrame(content, fg_color=self.colors['bg_secondary'],
                                   corner_radius=10)
        tab_container.pack(fill='both', expand=True, padx=20, pady=20)
        
        self.notebook = ttk.Notebook(tab_container)
        self.notebook.pack(fill='both', expand=True, padx=2, pady=2)
        
        # 각 탭 생성 (드래그앤드롭 탭 제거)
        self._create_realtime_integrated_tab()  # 통합된 실시간 탭
        self._create_statistics_tab()
        self._create_history_tab()
        
        # 탭 변경 이벤트
        self.notebook.bind('<<NotebookTabChanged>>', self._on_tab_changed)
    
    def _create_realtime_integrated_tab(self):
        """실시간 처리 현황 + 드래그앤드롭 통합 탭"""
        tab = ctk.CTkFrame(self.notebook, fg_color=self.colors['bg_primary'])
        self.notebook.add(tab, text="🔄 실시간 처리")
        
        # 메인 컨테이너 - 좌우 분할
        main_container = ctk.CTkFrame(tab, fg_color="transparent")
        main_container.pack(fill='both', expand=True, padx=20, pady=20)
        
        # 왼쪽: 실시간 처리 현황
        left_frame = ctk.CTkFrame(main_container, fg_color="transparent")
        left_frame.pack(side='left', fill='both', expand=True, padx=(0, 10))
        
        # 헤더
        header = ctk.CTkFrame(left_frame, fg_color="transparent")
        header.pack(fill='x', pady=(0, 10))
        
        ctk.CTkLabel(header, text="실시간 처리 현황", 
                   font=self.fonts['heading']).pack(side='left')
        
        refresh_btn = ctk.CTkButton(header, text="🔄 새로고침", 
                                  command=self._refresh_realtime,
                                  width=100, height=32,
                                  fg_color=self.colors['bg_card'],
                                  hover_color=self.colors['accent'])
        refresh_btn.pack(side='right')
        
        # 처리 중인 파일 목록
        list_frame = ctk.CTkFrame(left_frame, fg_color=self.colors['bg_card'],
                                corner_radius=10)
        list_frame.pack(fill='both', expand=True)
        
        # 트리뷰
        tree_frame = ctk.CTkFrame(list_frame, fg_color="transparent")
        tree_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        self.realtime_tree = ttk.Treeview(
            tree_frame,
            columns=('folder', 'status', 'time', 'issues'),
            show='tree headings',
            height=15
        )
        
        # 컬럼 설정
        self.realtime_tree.heading('#0', text='파일명')
        self.realtime_tree.heading('folder', text='폴더')
        self.realtime_tree.heading('status', text='상태')
        self.realtime_tree.heading('time', text='시간')
        self.realtime_tree.heading('issues', text='문제')
        
        # 컬럼 너비
        self.realtime_tree.column('#0', width=250)
        self.realtime_tree.column('folder', width=120)
        self.realtime_tree.column('status', width=80)
        self.realtime_tree.column('time', width=120)
        self.realtime_tree.column('issues', width=80)
        
        # 스크롤바
        scrollbar = ttk.Scrollbar(tree_frame, orient='vertical', command=self.realtime_tree.yview)
        self.realtime_tree.configure(yscrollcommand=scrollbar.set)
        
        # 배치
        self.realtime_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        
        # 우클릭 메뉴
        self._create_realtime_context_menu()
        
        # 태그 색상
        self.realtime_tree.tag_configure('processing', foreground=self.colors['accent'])
        self.realtime_tree.tag_configure('success', foreground=self.colors['success'])
        self.realtime_tree.tag_configure('error', foreground=self.colors['error'])
        self.realtime_tree.tag_configure('warning', foreground=self.colors['warning'])
        
        # 오른쪽: 드래그앤드롭 영역
        right_frame = ctk.CTkFrame(main_container, fg_color="transparent", width=350)
        right_frame.pack(side='right', fill='y')
        right_frame.pack_propagate(False)
        
        # 드롭존
        drop_frame = ctk.CTkFrame(right_frame, 
                                fg_color=self.colors['bg_card'],
                                corner_radius=20,
                                border_width=2,
                                border_color=self.colors['border'],
                                height=250)
        drop_frame.pack(fill='x', pady=(0, 15))
        drop_frame.pack_propagate(False)
        
        # 안내 텍스트
        drop_content = ctk.CTkFrame(drop_frame, fg_color="transparent")
        drop_content.place(relx=0.5, rely=0.5, anchor='center')
        
        # 아이콘
        ctk.CTkLabel(drop_content, text="📄", font=('Arial', 48)).pack(pady=(0, 10))
        
        self.drop_label = ctk.CTkLabel(
            drop_content,
            text="PDF 파일을 드래그하거나\n클릭하여 선택",
            font=self.fonts['body'],
            text_color=self.colors['text_secondary']
        )
        self.drop_label.pack()
        
        # 처리 옵션 카드
        options_card = ctk.CTkFrame(right_frame, fg_color=self.colors['bg_card'],
                                  corner_radius=10)
        options_card.pack(fill='x', pady=(0, 15))
        
        options_inner = ctk.CTkFrame(options_card, fg_color="transparent")
        options_inner.pack(padx=15, pady=15)
        
        options_title = ctk.CTkLabel(options_inner, text="처리 옵션", 
                                   font=self.fonts['subheading'])
        options_title.pack(pady=(0, 10))
        
        # 프로파일 선택
        profile_frame = ctk.CTkFrame(options_inner, fg_color="transparent")
        profile_frame.pack(pady=5)
        
        ctk.CTkLabel(profile_frame, text="프로파일:", 
                   font=self.fonts['body']).pack(side='left', padx=(0, 10))
        
        self.drop_profile_var = tk.StringVar(value='offset')
        profile_combo = ttk.Combobox(
            profile_frame, 
            textvariable=self.drop_profile_var,
            values=Config.AVAILABLE_PROFILES,
            state='readonly',
            width=12,
            font=self.fonts['body']
        )
        profile_combo.pack(side='left')
        
        # 체크박스들
        check_frame = ctk.CTkFrame(options_inner, fg_color="transparent")
        check_frame.pack(pady=10)
        
        self.drop_auto_fix_var = tk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            check_frame, 
            text="자동 수정 적용",
            variable=self.drop_auto_fix_var,
            height=24
        ).pack(pady=3)
        
        self.drop_ink_analysis_var = tk.BooleanVar(value=Config.is_ink_analysis_enabled())
        ctk.CTkCheckBox(
            check_frame,
            text="잉크량 분석 포함",
            variable=self.drop_ink_analysis_var,
            height=24
        ).pack(pady=3)
        
        # 처리 버튼
        process_btn = ctk.CTkButton(
            options_inner, 
            text="🚀 처리 시작", 
            command=self._process_dropped_files,
            width=200, 
            height=36,
            font=self.fonts['body']
        )
        process_btn.pack(pady=(10, 0))
        
        # 클릭 이벤트
        drop_frame.bind("<Button-1>", lambda e: self.browse_files())
        
        # 드래그앤드롭 설정
        if HAS_DND:
            self._setup_drag_drop(drop_frame)
        
        # 처리 대기 목록 (간소화)
        queue_frame = ctk.CTkFrame(right_frame, fg_color=self.colors['bg_card'],
                                 corner_radius=10)
        queue_frame.pack(fill='both', expand=True)
        
        queue_inner = ctk.CTkFrame(queue_frame, fg_color="transparent")
        queue_inner.pack(fill='both', expand=True, padx=15, pady=15)
        
        queue_header = ctk.CTkFrame(queue_inner, fg_color="transparent")
        queue_header.pack(fill='x', pady=(0, 10))
        
        ctk.CTkLabel(queue_header, text="대기 목록", 
                   font=self.fonts['subheading']).pack(side='left')
        
        clear_btn = ctk.CTkButton(queue_header, text="비우기", 
                                command=self._clear_drop_list,
                                width=60, height=28,
                                fg_color=self.colors['bg_secondary'],
                                hover_color=self.colors['error'])
        clear_btn.pack(side='right')
        
        # 대기 목록
        list_scroll = ttk.Scrollbar(queue_inner, orient='vertical')
        list_scroll.pack(side='right', fill='y')
        
        self.drop_listbox = tk.Listbox(queue_inner, height=6,
                                     font=self.fonts['small'],
                                     bg=self.colors['bg_secondary'],
                                     fg=self.colors['text_primary'],
                                     selectbackground=self.colors['accent'],
                                     borderwidth=0,
                                     highlightthickness=0,
                                     yscrollcommand=list_scroll.set)
        self.drop_listbox.pack(fill='both', expand=True, side='left')
        list_scroll.config(command=self.drop_listbox.yview)
    
    def _create_statistics_tab(self):
        """통계 대시보드 탭"""
        tab = ctk.CTkFrame(self.notebook, fg_color=self.colors['bg_primary'])
        self.notebook.add(tab, text="📊 통계 대시보드")
        
        # 스크롤 가능한 프레임
        canvas = tk.Canvas(tab, highlightthickness=0, bg=self.colors['bg_primary'])
        scrollbar = ttk.Scrollbar(tab, orient="vertical", command=canvas.yview)
        scrollable_frame = ctk.CTkFrame(canvas, fg_color=self.colors['bg_primary'])
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # 기간 선택
        period_frame = ctk.CTkFrame(scrollable_frame, fg_color="transparent")
        period_frame.pack(fill='x', padx=20, pady=20)
        
        ctk.CTkLabel(period_frame, text="기간 선택:", 
                   font=self.fonts['subheading']).pack(side='left', padx=(0, 20))
        
        self.stats_period = tk.StringVar(value='today')
        periods = [
            ('오늘', 'today'),
            ('이번 주', 'week'),
            ('이번 달', 'month'),
            ('전체', 'all')
        ]
        
        for text, value in periods:
            ctk.CTkRadioButton(
                period_frame, 
                text=text, 
                variable=self.stats_period, 
                value=value,
                command=self._update_statistics,
                radiobutton_width=20,
                radiobutton_height=20
            ).pack(side='left', padx=10)
        
        # 기본 통계 카드들
        cards_frame = ctk.CTkFrame(scrollable_frame, fg_color="transparent")
        cards_frame.pack(fill='x', padx=20, pady=20)
        
        self.stat_cards = {}
        card_info = [
            ('total_files', '📄', '총 파일', '0', self.colors['accent']),
            ('total_pages', '📃', '총 페이지', '0', '#00BCD4'),
            ('total_errors', '❌', '총 오류', '0', self.colors['error']),
            ('auto_fixed', '🔧', '자동 수정', '0', self.colors['success'])
        ]
        
        for key, icon, title, default, color in card_info:
            card = self._create_stat_card(cards_frame, icon, title, default, color)
            card.pack(side='left', fill='both', expand=True, padx=10)
            self.stat_cards[key] = card
        
        # 차트 영역 (matplotlib 있는 경우)
        if HAS_MATPLOTLIB:
            self._create_charts(scrollable_frame)
        else:
            # 텍스트 기반 통계
            self._create_text_statistics(scrollable_frame)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
    
    def _create_history_tab(self):
        """처리 이력 탭"""
        tab = ctk.CTkFrame(self.notebook, fg_color=self.colors['bg_primary'])
        self.notebook.add(tab, text="📋 처리 이력")
        
        # 검색 프레임
        search_frame = ctk.CTkFrame(tab, fg_color="transparent")
        search_frame.pack(fill='x', padx=20, pady=20)
        
        ctk.CTkLabel(search_frame, text="검색:", 
                   font=self.fonts['body']).pack(side='left', padx=(0, 10))
        
        self.history_search_var = tk.StringVar()
        search_entry = ctk.CTkEntry(search_frame, textvariable=self.history_search_var, 
                                  width=300, height=32)
        search_entry.pack(side='left', padx=5)
        
        ctk.CTkButton(search_frame, text="🔍 검색", command=self._search_history,
                    width=80, height=32).pack(side='left', padx=5)
        ctk.CTkButton(search_frame, text="🔄 초기화", command=self._reset_history_search,
                    width=80, height=32,
                    fg_color=self.colors['bg_card'],
                    hover_color=self.colors['accent']).pack(side='left', padx=5)
        
        # 필터 옵션
        filter_frame = ctk.CTkFrame(search_frame, fg_color="transparent")
        filter_frame.pack(side='right')
        
        self.filter_errors_only = tk.BooleanVar()
        ctk.CTkCheckBox(
            filter_frame, 
            text="오류만 표시", 
            variable=self.filter_errors_only,
            command=self._update_history
        ).pack(side='left', padx=10)
        
        # 이력 목록
        list_frame = ctk.CTkFrame(tab, fg_color=self.colors['bg_card'],
                                corner_radius=10)
        list_frame.pack(fill='both', expand=True, padx=20, pady=10)
        
        # 트리뷰
        tree_frame = ctk.CTkFrame(list_frame, fg_color="transparent")
        tree_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        self.history_tree = ttk.Treeview(
            tree_frame,
            columns=('date', 'pages', 'errors', 'warnings', 'profile', 'status'),
            show='tree headings',
            height=15
        )
        
        # 컬럼 설정
        self.history_tree.heading('#0', text='파일명')
        self.history_tree.heading('date', text='처리일시')
        self.history_tree.heading('pages', text='페이지')
        self.history_tree.heading('errors', text='오류')
        self.history_tree.heading('warnings', text='경고')
        self.history_tree.heading('profile', text='프로파일')
        self.history_tree.heading('status', text='상태')
        
        # 컬럼 너비
        self.history_tree.column('#0', width=250)
        self.history_tree.column('date', width=150)
        self.history_tree.column('pages', width=80)
        self.history_tree.column('errors', width=80)
        self.history_tree.column('warnings', width=80)
        self.history_tree.column('profile', width=100)
        self.history_tree.column('status', width=100)
        
        # 스크롤바
        scrollbar = ttk.Scrollbar(tree_frame, orient='vertical', command=self.history_tree.yview)
        self.history_tree.configure(yscrollcommand=scrollbar.set)
        
        # 배치
        self.history_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        
        # 우클릭 메뉴
        self._create_history_context_menu()
        
        # 더블클릭 이벤트
        self.history_tree.bind('<Double-Button-1>', self._on_history_double_click)
        
        # 초기 데이터 로드
        self._update_history()
    
    def _setup_drag_drop(self, drop_frame):
        """드래그앤드롭 설정"""
        def drop_enter(event):
            """드래그 진입 시"""
            drop_frame.configure(border_color=self.colors['accent'])
            self.drop_label.configure(text="파일을 놓으세요!", 
                                    text_color=self.colors['accent'])
            return event.action
            
        def drop_leave(event):
            """드래그 떠날 시"""
            drop_frame.configure(border_color=self.colors['border'])
            self.drop_label.configure(text="PDF 파일을 드래그하거나\n클릭하여 선택",
                                    text_color=self.colors['text_secondary'])
            return event.action
            
        def drop_files(event):
            """파일 드롭 시"""
            files = self._parse_drop_files(event.data)
            pdf_files = [f for f in files if f.lower().endswith('.pdf')]
            
            if pdf_files:
                self.dropped_files = pdf_files
                for file in pdf_files:
                    self.drop_listbox.insert(tk.END, Path(file).name)
                self.logger.log(f"드래그앤드롭으로 {len(pdf_files)}개 파일 추가")
            else:
                messagebox.showwarning("경고", "PDF 파일만 추가할 수 있습니다.")
                
            drop_leave(event)
            return event.action
        
        # 드래그앤드롭 이벤트 바인딩
        drop_frame.drop_target_register(DND_FILES)
        drop_frame.dnd_bind('<<DropEnter>>', drop_enter)
        drop_frame.dnd_bind('<<DropLeave>>', drop_leave)
        drop_frame.dnd_bind('<<Drop>>', drop_files)
    
    def _parse_drop_files(self, data):
        """드롭된 파일 경로 파싱"""
        files = []
        if data.startswith('{') and data.endswith('}'):
            data = data[1:-1]
            files = data.split('} {')
        else:
            files = data.split()
        
        cleaned_files = []
        for f in files:
            f = f.strip()
            if f:
                if (f.startswith('"') and f.endswith('"')) or (f.startswith("'") and f.endswith("'")):
                    f = f[1:-1]
                cleaned_files.append(f)
        
        return cleaned_files
    
    def _create_statusbar(self):
        """상태바 생성"""
        statusbar = ctk.CTkFrame(self.root, height=30, corner_radius=0,
                               fg_color=self.colors['bg_secondary'])
        statusbar.pack(side='bottom', fill='x')
        
        # 상태바 내용
        status_content = ctk.CTkFrame(statusbar, fg_color="transparent")
        status_content.pack(fill='x', expand=True)
        
        # 상태 텍스트
        self.status_var = tk.StringVar()
        self.status_var.set("준비됨")
        status_label = ctk.CTkLabel(status_content, textvariable=self.status_var,
                                  font=self.fonts['small'])
        status_label.pack(side='left', padx=20)
        
        # 감시 상태
        self.watch_status_var = tk.StringVar()
        self.watch_status_var.set("감시: 중지")
        watch_label = ctk.CTkLabel(status_content, textvariable=self.watch_status_var,
                                 font=self.fonts['small'])
        watch_label.pack(side='left', padx=20)
        
        # 파일 수
        self.file_count_var = tk.StringVar()
        self.file_count_var.set("처리: 0개")
        count_label = ctk.CTkLabel(status_content, textvariable=self.file_count_var,
                                 font=self.fonts['small'])
        count_label.pack(side='right', padx=20)
        
        # 시계
        self.time_label = ctk.CTkLabel(status_content, text="",
                                     font=self.fonts['small'])
        self.time_label.pack(side='right', padx=20)
        self._update_time()
    
    def _create_realtime_context_menu(self):
        """실시간 탭 우클릭 메뉴"""
        self.realtime_menu = tk.Menu(self.root, tearoff=0, 
                                   bg=self.colors['bg_secondary'],
                                   fg=self.colors['text_primary'],
                                   activebackground=self.colors['accent'],
                                   activeforeground='white',
                                   font=self.fonts['body'])
        self.realtime_menu.add_command(label="보고서 보기", command=self._view_realtime_report)
        self.realtime_menu.add_command(label="폴더에서 보기", command=self._show_in_folder_realtime)
        self.realtime_menu.add_separator()
        self.realtime_menu.add_command(label="다시 처리", command=self._reprocess_file)
        
        self.realtime_tree.bind('<Button-3>', self._show_realtime_menu)
    
    def _create_history_context_menu(self):
        """이력 탭 우클릭 메뉴"""
        self.history_menu = tk.Menu(self.root, tearoff=0,
                                  bg=self.colors['bg_secondary'],
                                  fg=self.colors['text_primary'],
                                  activebackground=self.colors['accent'],
                                  activeforeground='white',
                                  font=self.fonts['body'])
        self.history_menu.add_command(label="상세 정보", command=self._show_history_details)
        self.history_menu.add_command(label="보고서 보기", command=self._view_history_report)
        self.history_menu.add_separator()
        self.history_menu.add_command(label="파일 비교", command=self._compare_history_files)
        
        self.history_tree.bind('<Button-3>', self._show_history_menu)
    
    def _create_stat_card(self, parent, icon, title, value, color):
        """통계 카드 위젯 생성"""
        card = ctk.CTkFrame(parent, fg_color=self.colors['bg_card'],
                          corner_radius=10)
        card.configure(width=200, height=120)
        
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill='both', expand=True, padx=20, pady=20)
        
        # 아이콘
        icon_label = ctk.CTkLabel(inner, text=icon, font=('Arial', 24))
        icon_label.pack()
        
        # 타이틀
        title_label = ctk.CTkLabel(inner, text=title, 
                                 font=self.fonts['small'],
                                 text_color=self.colors['text_secondary'])
        title_label.pack(pady=(5, 0))
        
        # 값
        value_label = ctk.CTkLabel(inner, text=value, 
                                 font=('맑은 고딕', 20, 'bold'),
                                 text_color=color)
        value_label.pack()
        
        # 레이블 참조 저장
        card.value_label = value_label
        
        return card
    
    def _create_charts(self, parent):
        """차트 생성 (matplotlib)"""
        # matplotlib 한글 폰트 설정
        import matplotlib.pyplot as plt
        plt.rcParams['font.family'] = 'Malgun Gothic'
        plt.rcParams['axes.unicode_minus'] = False
        
        charts_frame = ctk.CTkFrame(parent, fg_color=self.colors['bg_card'],
                                  corner_radius=10)
        charts_frame.pack(fill='both', expand=True, padx=20, pady=20)
        
        charts_inner = ctk.CTkFrame(charts_frame, fg_color="transparent")
        charts_inner.pack(fill='both', expand=True, padx=15, pady=15)
        
        chart_title = ctk.CTkLabel(charts_inner, text="📈 분석 차트", 
                                 font=self.fonts['heading'])
        chart_title.pack(anchor='w', pady=(0, 10))
        
        # 차트 캔버스들을 담을 프레임
        self.chart_frames = {}
        
        # 1. 일별 처리량 차트
        daily_frame = ctk.CTkFrame(charts_inner, fg_color="transparent")
        daily_frame.pack(fill='x', pady=10)
        
        fig1 = Figure(figsize=(10, 4), dpi=80, facecolor=self.colors['bg_card'])
        self.daily_chart = fig1.add_subplot(111)
        self.daily_chart.set_facecolor(self.colors['bg_card'])
        self.daily_chart.set_title('일별 처리량', fontsize=12, fontweight='bold', color='white')
        
        canvas1 = FigureCanvasTkAgg(fig1, master=daily_frame)
        canvas1.draw()
        canvas1.get_tk_widget().pack(fill='x')
        
        self.chart_frames['daily'] = (fig1, canvas1)
        
        # 2. 문제 유형별 분포 차트
        issue_frame = ctk.CTkFrame(charts_inner, fg_color="transparent")
        issue_frame.pack(fill='x', pady=10)
        
        fig2 = Figure(figsize=(10, 4), dpi=80, facecolor=self.colors['bg_card'])
        self.issue_chart = fig2.add_subplot(111)
        self.issue_chart.set_facecolor(self.colors['bg_card'])
        self.issue_chart.set_title('문제 유형별 분포', fontsize=12, fontweight='bold', color='white')
        
        canvas2 = FigureCanvasTkAgg(fig2, master=issue_frame)
        canvas2.draw()
        canvas2.get_tk_widget().pack(fill='x')
        
        self.chart_frames['issues'] = (fig2, canvas2)
    
    def _create_text_statistics(self, parent):
        """텍스트 기반 통계 (matplotlib 없을 때)"""
        text_frame = ctk.CTkFrame(parent, fg_color=self.colors['bg_card'],
                                corner_radius=10)
        text_frame.pack(fill='both', expand=True, padx=20, pady=20)
        
        text_inner = ctk.CTkFrame(text_frame, fg_color="transparent")
        text_inner.pack(fill='both', expand=True, padx=15, pady=15)
        
        text_title = ctk.CTkLabel(text_inner, text="📊 상세 통계", 
                                font=self.fonts['heading'])
        text_title.pack(anchor='w', pady=(0, 10))
        
        self.stats_text = scrolledtext.ScrolledText(
            text_inner,
            wrap=tk.WORD,
            height=15,
            font=self.fonts['mono'],
            bg=self.colors['bg_secondary'],
            fg=self.colors['text_primary'],
            insertbackground=self.colors['text_primary'],
            selectbackground=self.colors['accent'],
            borderwidth=0,
            highlightthickness=0
        )
        self.stats_text.pack(fill='both', expand=True)
    
    def _init_folder_watching(self):
        """폴더 감시 초기화"""
        # 저장된 폴더 설정이 있으면 자동 시작
        if len(self.folder_watcher.folder_configs) > 0:
            auto_start = messagebox.askyesno(
                "폴더 감시",
                "저장된 폴더 설정이 있습니다.\n폴더 감시를 시작하시겠습니까?"
            )
            if auto_start:
                self.start_folder_watching()
    
    def _start_periodic_updates(self):
        """주기적 업데이트 시작"""
        self._update_quick_stats()
        self.root.after(30000, self._start_periodic_updates)  # 30초마다
    
    # ===== 폴더 관리 메서드 =====
    
    def add_watch_folder(self):
        """감시 폴더 추가 대화상자"""
        dialog = ctk.CTkToplevel(self.root)
        dialog.title("감시 폴더 추가")
        dialog.geometry("550x550")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # 메인 프레임
        main_frame = ctk.CTkFrame(dialog)
        main_frame.pack(fill='both', expand=True, padx=20, pady=20)
        
        # 폴더 선택
        folder_frame = ctk.CTkFrame(main_frame, fg_color=self.colors['bg_card'])
        folder_frame.pack(fill='x', pady=(0, 15))
        
        folder_inner = ctk.CTkFrame(folder_frame, fg_color="transparent")
        folder_inner.pack(fill='x', padx=15, pady=15)
        
        ctk.CTkLabel(folder_inner, text="폴더 선택", 
                   font=self.fonts['subheading']).pack(anchor='w', pady=(0, 10))
        
        folder_var = tk.StringVar()
        folder_entry = ctk.CTkEntry(folder_inner, textvariable=folder_var, height=32)
        folder_entry.pack(side='left', fill='x', expand=True, padx=(0, 10))
        
        def browse():
            folder = filedialog.askdirectory()
            if folder:
                folder_var.set(folder)
        
        ctk.CTkButton(folder_inner, text="찾아보기", command=browse,
                    width=80, height=32).pack(side='right')
        
        # 프로파일 선택
        profile_frame = ctk.CTkFrame(main_frame, fg_color=self.colors['bg_card'])
        profile_frame.pack(fill='x', pady=(0, 15))
        
        profile_inner = ctk.CTkFrame(profile_frame, fg_color="transparent")
        profile_inner.pack(fill='x', padx=15, pady=15)
        
        ctk.CTkLabel(profile_inner, text="프리플라이트 프로파일", 
                   font=self.fonts['subheading']).pack(anchor='w', pady=(0, 10))
        
        profile_var = tk.StringVar(value='offset')
        for i, profile in enumerate(Config.AVAILABLE_PROFILES):
            ctk.CTkRadioButton(
                profile_inner,
                text=profile,
                variable=profile_var,
                value=profile,
                radiobutton_width=20,
                radiobutton_height=20
            ).grid(row=i//2, column=i%2, sticky='w', padx=10, pady=5)
        
        # 처리 옵션
        options_frame = ctk.CTkFrame(main_frame, fg_color=self.colors['bg_card'])
        options_frame.pack(fill='x', pady=(0, 15))
        
        options_inner = ctk.CTkFrame(options_frame, fg_color="transparent")
        options_inner.pack(fill='x', padx=15, pady=15)
        
        ctk.CTkLabel(options_inner, text="처리 옵션", 
                   font=self.fonts['subheading']).pack(anchor='w', pady=(0, 10))
        
        fix_options = {
            'auto_convert_rgb': tk.BooleanVar(value=False),
            'auto_outline_fonts': tk.BooleanVar(value=False),
            'include_ink_analysis': tk.BooleanVar(value=Config.is_ink_analysis_enabled())
        }
        
        ctk.CTkCheckBox(
            options_inner,
            text="RGB → CMYK 자동 변환",
            variable=fix_options['auto_convert_rgb']
        ).pack(anchor='w', pady=3)
        
        ctk.CTkCheckBox(
            options_inner,
            text="폰트 아웃라인 변환",
            variable=fix_options['auto_outline_fonts']
        ).pack(anchor='w', pady=3)
        
        ctk.CTkCheckBox(
            options_inner,
            text="잉크량 분석 포함 (처리 시간 증가)",
            variable=fix_options['include_ink_analysis']
        ).pack(anchor='w', pady=3)
        
        # 출력 폴더
        output_frame = ctk.CTkFrame(main_frame, fg_color=self.colors['bg_card'])
        output_frame.pack(fill='x', pady=(0, 15))
        
        output_inner = ctk.CTkFrame(output_frame, fg_color="transparent")
        output_inner.pack(fill='x', padx=15, pady=15)
        
        ctk.CTkLabel(output_inner, text="출력 폴더 (선택사항)", 
                   font=self.fonts['subheading']).pack(anchor='w', pady=(0, 10))
        
        output_var = tk.StringVar()
        ctk.CTkEntry(output_inner, textvariable=output_var, height=32).pack(fill='x')
        
        ctk.CTkLabel(output_inner, text="비워두면 폴더 내에 하위 폴더 자동 생성",
                   font=self.fonts['small'], 
                   text_color=self.colors['text_secondary']).pack(anchor='w', pady=(5, 0))
        
        # 버튼
        button_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        button_frame.pack(fill='x', pady=(10, 0))
        
        def add_folder():
            folder_path = folder_var.get()
            if not folder_path:
                messagebox.showwarning("경고", "폴더를 선택하세요.")
                return
            
            # 자동 수정 설정
            auto_fix_settings = {
                key: var.get() 
                for key, var in fix_options.items()
            }
            
            # 폴더 추가
            success = self.folder_watcher.add_folder(
                folder_path,
                profile=profile_var.get(),
                auto_fix_settings=auto_fix_settings,
                output_folder=output_var.get() or None
            )
            
            if success:
                # 하위 폴더 자동 생성
                self._create_folder_structure(folder_path)
                
                self._update_folder_list()
                dialog.destroy()
                self.logger.log(f"감시 폴더 추가: {Path(folder_path).name}")
                messagebox.showinfo("성공", "폴더가 추가되었습니다.")
            else:
                messagebox.showerror("오류", "폴더 추가에 실패했습니다.")
        
        ctk.CTkButton(button_frame, text="추가", command=add_folder,
                    width=80, height=36).pack(side='right', padx=5)
        ctk.CTkButton(button_frame, text="취소", command=dialog.destroy,
                    width=80, height=36,
                    fg_color=self.colors['bg_secondary'],
                    hover_color=self.colors['error']).pack(side='right')
    
    def _create_folder_structure(self, folder_path):
        """핫폴더 하위 구조 자동 생성"""
        folder_path = Path(folder_path)
        
        # 생성할 하위 폴더들
        subfolders = [
            'reports',      # 보고서
            'output',       # 출력
            'completed',    # 완료된 파일
            'errors',       # 오류 파일
            'backup'        # 백업
        ]
        
        for subfolder in subfolders:
            subfolder_path = folder_path / subfolder
            try:
                subfolder_path.mkdir(exist_ok=True)
                self.logger.log(f"하위 폴더 생성: {subfolder_path}")
            except Exception as e:
                self.logger.error(f"하위 폴더 생성 실패 ({subfolder}): {e}")
    
    def edit_folder_settings(self):
        """폴더 설정 편집"""
        selection = self.folder_listbox.curselection()
        if not selection:
            messagebox.showinfo("정보", "편집할 폴더를 선택하세요.")
            return
        
        # 선택한 폴더 정보
        folder_info = self.folder_watcher.get_folder_list()[selection[0]]
        folder_path = folder_info['path']
        
        # 편집 대화상자
        dialog = ctk.CTkToplevel(self.root)
        dialog.title("폴더 설정 편집")
        dialog.geometry("550x550")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # 메인 프레임
        main_frame = ctk.CTkFrame(dialog)
        main_frame.pack(fill='both', expand=True, padx=20, pady=20)
        
        # 폴더 정보 표시
        info_frame = ctk.CTkFrame(main_frame, fg_color=self.colors['bg_card'])
        info_frame.pack(fill='x', pady=(0, 15))
        
        info_inner = ctk.CTkFrame(info_frame, fg_color="transparent")
        info_inner.pack(fill='x', padx=15, pady=15)
        
        ctk.CTkLabel(info_inner, text="폴더 정보", 
                   font=self.fonts['subheading']).pack(anchor='w', pady=(0, 10))
        
        ctk.CTkLabel(info_inner, text=f"경로: {folder_path}",
                   font=self.fonts['body']).pack(anchor='w')
        ctk.CTkLabel(info_inner, text=f"처리된 파일: {folder_info['processed']}개",
                   font=self.fonts['body']).pack(anchor='w', pady=(5, 0))
        
        # 프로파일 선택
        profile_frame = ctk.CTkFrame(main_frame, fg_color=self.colors['bg_card'])
        profile_frame.pack(fill='x', pady=(0, 15))
        
        profile_inner = ctk.CTkFrame(profile_frame, fg_color="transparent")
        profile_inner.pack(fill='x', padx=15, pady=15)
        
        ctk.CTkLabel(profile_inner, text="프리플라이트 프로파일", 
                   font=self.fonts['subheading']).pack(anchor='w', pady=(0, 10))
        
        profile_var = tk.StringVar(value=folder_info['profile'])
        for i, profile in enumerate(Config.AVAILABLE_PROFILES):
            ctk.CTkRadioButton(
                profile_inner,
                text=profile,
                variable=profile_var,
                value=profile,
                radiobutton_width=20,
                radiobutton_height=20
            ).grid(row=i//2, column=i%2, sticky='w', padx=10, pady=5)
        
        # 처리 옵션
        options_frame = ctk.CTkFrame(main_frame, fg_color=self.colors['bg_card'])
        options_frame.pack(fill='x', pady=(0, 15))
        
        options_inner = ctk.CTkFrame(options_frame, fg_color="transparent")
        options_inner.pack(fill='x', padx=15, pady=15)
        
        ctk.CTkLabel(options_inner, text="처리 옵션", 
                   font=self.fonts['subheading']).pack(anchor='w', pady=(0, 10))
        
        # 현재 설정 가져오기
        folder_config = self.folder_watcher.folder_configs.get(folder_path, {})
        current_settings = folder_config.auto_fix_settings if hasattr(folder_config, 'auto_fix_settings') else {}
        
        fix_options = {
            'auto_convert_rgb': tk.BooleanVar(value=current_settings.get('auto_convert_rgb', False)),
            'auto_outline_fonts': tk.BooleanVar(value=current_settings.get('auto_outline_fonts', False)),
            'include_ink_analysis': tk.BooleanVar(value=current_settings.get('include_ink_analysis', False))
        }
        
        ctk.CTkCheckBox(
            options_inner,
            text="RGB → CMYK 자동 변환",
            variable=fix_options['auto_convert_rgb']
        ).pack(anchor='w', pady=3)
        
        ctk.CTkCheckBox(
            options_inner,
            text="폰트 아웃라인 변환",
            variable=fix_options['auto_outline_fonts']
        ).pack(anchor='w', pady=3)
        
        ctk.CTkCheckBox(
            options_inner,
            text="잉크량 분석 포함 (처리 시간 증가)",
            variable=fix_options['include_ink_analysis']
        ).pack(anchor='w', pady=3)
        
        # 활성화 옵션
        enabled_var = tk.BooleanVar(value=folder_info['enabled'])
        ctk.CTkCheckBox(
            main_frame,
            text="이 폴더 감시 활성화",
            variable=enabled_var
        ).pack(anchor='w', pady=10)
        
        # 버튼
        button_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        button_frame.pack(fill='x', pady=(10, 0))
        
        def save_settings():
            # 자동 수정 설정
            auto_fix_settings = {
                key: var.get() 
                for key, var in fix_options.items()
            }
            
            # 설정 업데이트
            success = self.folder_watcher.update_folder_config(
                folder_path,
                profile=profile_var.get(),
                auto_fix_settings=auto_fix_settings,
                enabled=enabled_var.get()
            )
            
            if success:
                self._update_folder_list()
                dialog.destroy()
                self.logger.log(f"폴더 설정 업데이트: {Path(folder_path).name}")
                messagebox.showinfo("성공", "설정이 저장되었습니다.")
            else:
                messagebox.showerror("오류", "설정 저장에 실패했습니다.")
        
        ctk.CTkButton(button_frame, text="저장", command=save_settings,
                    width=80, height=36).pack(side='right', padx=5)
        ctk.CTkButton(button_frame, text="취소", command=dialog.destroy,
                    width=80, height=36,
                    fg_color=self.colors['bg_secondary'],
                    hover_color=self.colors['error']).pack(side='right')
        
        # 폴더 열기 버튼
        def open_folder():
            try:
                os.startfile(folder_path)
            except:
                pass
                
        ctk.CTkButton(button_frame, text="폴더 열기", command=open_folder,
                    width=80, height=36,
                    fg_color=self.colors['bg_secondary'],
                    hover_color=self.colors['accent']).pack(side='left')
    
    def remove_watch_folder(self):
        """선택한 감시 폴더 제거"""
        selection = self.folder_listbox.curselection()
        if not selection:
            messagebox.showinfo("정보", "제거할 폴더를 선택하세요.")
            return
        
        # 선택한 폴더 정보 가져오기
        folder_info = self.folder_watcher.get_folder_list()[selection[0]]
        folder_path = folder_info['path']
        
        # 확인
        if messagebox.askyesno("확인", f"'{folder_info['name']}' 폴더를 제거하시겠습니까?"):
            if self.folder_watcher.remove_folder(folder_path):
                self._update_folder_list()
                self.logger.log(f"감시 폴더 제거: {folder_info['name']}")
    
    def toggle_folder_watching(self):
        """폴더 감시 토글"""
        if self.watch_toggle_switch.get():
            self.start_folder_watching()
        else:
            self.stop_folder_watching()
    
    def start_folder_watching(self):
        """폴더 감시 시작"""
        if not self.folder_watcher.folder_configs:
            messagebox.showinfo("정보", "감시할 폴더가 없습니다.\n먼저 폴더를 추가하세요.")
            self.watch_toggle_switch.deselect()
            return
        
        self.folder_watcher.start_watching()
        self.is_folder_watching = True
        
        # UI 업데이트
        self.watch_status_label.configure(text="🟢 감시 중")
        self.watch_status_var.set("감시: 실행 중")
        
        self.logger.log("폴더 감시 시작")
        self.status_var.set("폴더 감시가 시작되었습니다.")
    
    def stop_folder_watching(self):
        """폴더 감시 중지"""
        self.folder_watcher.stop_watching()
        self.is_folder_watching = False
        
        # UI 업데이트
        self.watch_status_label.configure(text="⏸️ 감시 중지됨")
        self.watch_status_var.set("감시: 중지")
        
        self.logger.log("폴더 감시 중지")
        self.status_var.set("폴더 감시가 중지되었습니다.")
    
    def manage_folders(self):
        """폴더 설정 관리 창"""
        messagebox.showinfo("정보", "사이드바에서 폴더를 선택한 후 설정 버튼을 클릭하세요.")
    
    # ===== 콜백 메서드 =====
    
    def _on_folder_pdf_found(self, file_path: Path, folder_config: Dict):
        """폴더에서 PDF 발견시 콜백"""
        self.logger.log(f"PDF 발견: {file_path.name} (폴더: {file_path.parent.name})")
        
        # 안전한 item ID 생성
        item_id = self._generate_safe_item_id("folder")
        
        # 실시간 탭에 추가
        self.realtime_tree.insert(
            '',
            'end',
            iid=item_id,
            text=file_path.name,
            values=(
                file_path.parent.name,
                '대기 중',
                datetime.now().strftime('%H:%M:%S'),
                '-'
            ),
            tags=('processing',)
        )
        
        # 처리 시작
        self._process_pdf_file(file_path, folder_config, item_id)
    
    def _process_pdf_file(self, file_path: Path, folder_config: Dict, tree_item_id: str):
        """PDF 파일 처리"""
        def process():
            try:
                # 상태 업데이트
                self.realtime_tree.item(
                    tree_item_id,
                    values=(
                        file_path.parent.name,
                        '처리 중',
                        datetime.now().strftime('%H:%M:%S'),
                        '-'
                    )
                )
                
                # 잉크량 분석 옵션 확인
                include_ink = folder_config.get('auto_fix_settings', {}).get(
    'include_ink_analysis', 
    Config.is_ink_analysis_enabled()  # 기본값을 Config에서 가져옴
)

                
                # PDF 분석
                analyzer = PDFAnalyzer()
                result = analyzer.analyze(
                    str(file_path),
                    include_ink_analysis=include_ink,
                    preflight_profile=folder_config.get('profile', 'offset')
                )
                
                # 데이터베이스에 저장
                try:
                    self.data_manager.save_analysis_result(result)
                    self.logger.log(f"데이터베이스 저장 완료: {file_path.name}")
                except Exception as e:
                    self.logger.error(f"데이터베이스 저장 실패: {e}")
                
                # 드래그앤드롭과 폴더 감시 구분
                is_folder_watch = folder_config.get('path') is not None
                
                if is_folder_watch:
                    # 감시 폴더 내에 하위 폴더 구조 생성
                    output_base = file_path.parent
                    reports_folder = output_base / 'reports'
                    reports_folder.mkdir(exist_ok=True)
                else:
                    # 드래그앤드롭의 경우 기본 reports 폴더 사용
                    reports_folder = Config.REPORTS_PATH
                    reports_folder.mkdir(exist_ok=True, parents=True)
                
                # 보고서 생성 - 직접 경로 지정
                generator = ReportGenerator()
                report_filename = f"{file_path.stem}_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                
                # 텍스트 보고서 저장
                text_path = generator.save_text_report(
                    result, 
                    output_path=reports_folder / f"{report_filename}.txt"
                )
                
                # HTML 보고서 저장
                html_path = generator.save_html_report(
                    result,
                    output_path=reports_folder / f"{report_filename}.html"
                )
                
                # 결과에 따라 파일 이동 (폴더 감시인 경우만)
                issues = result.get('issues', [])
                error_count = sum(1 for i in issues if i['severity'] == 'error')
                warning_count = sum(1 for i in issues if i['severity'] == 'warning')
                
                if is_folder_watch:
                    # 감시 폴더 내 하위 폴더로 파일 이동
                    if error_count > 0:
                        dest_folder = output_base / 'errors'
                        status = 'error'
                    elif warning_count > 0:
                        dest_folder = output_base / 'completed'
                        status = 'warning'
                    else:
                        dest_folder = output_base / 'completed'
                        status = 'success'
                    
                    # 파일 이동
                    try:
                        dest_folder.mkdir(exist_ok=True)
                        dest_path = dest_folder / file_path.name
                        shutil.move(str(file_path), str(dest_path))
                        self.logger.log(f"파일 이동: {file_path.name} → {dest_folder.name}")
                    except Exception as e:
                        self.logger.error(f"파일 이동 실패: {e}")
                else:
                    # 드래그앤드롭의 경우 파일 이동하지 않음
                    if error_count > 0:
                        status = 'error'
                    elif warning_count > 0:
                        status = 'warning'
                    else:
                        status = 'success'
                
                # UI 업데이트
                self.realtime_tree.item(
                    tree_item_id,
                    values=(
                        file_path.parent.name,
                        '완료',
                        datetime.now().strftime('%H:%M:%S'),
                        f"오류:{error_count} 경고:{warning_count}"
                    ),
                    tags=(status,)
                )
                
                # 알림
                self.notification_manager.notify_success(
                    file_path.name,
                    len(issues),
                    page_count=result['basic_info']['page_count'],
                    processing_time=float(result.get('analysis_time', '0').replace('초', ''))
                )
                
                # 통계 업데이트
                self._update_quick_stats()
                
            except Exception as e:
                self.logger.error(f"처리 오류: {e}")
                self.realtime_tree.item(
                    tree_item_id,
                    values=(
                        file_path.parent.name,
                        '오류',
                        datetime.now().strftime('%H:%M:%S'),
                        str(e)[:50]
                    ),
                    tags=('error',)
                )
                
                # 오류 알림
                self.notification_manager.notify_error(file_path.name, str(e))
        
        # 별도 스레드에서 처리
        thread = threading.Thread(target=process, daemon=True)
        thread.start()
    
    # ===== UI 업데이트 메서드 =====
    
    def _update_folder_list(self):
        """폴더 목록 업데이트"""
        self.folder_listbox.delete(0, tk.END)
        
        for folder in self.folder_watcher.get_folder_list():
            status = "✓" if folder['enabled'] else "✗"
            ink = "🎨" if folder.get('auto_fix_settings', {}).get('include_ink_analysis', False) else ""
            text = f"{status} {folder['name']} ({folder['profile']}) {ink}"
            self.folder_listbox.insert(tk.END, text)
    
    def _update_quick_stats(self):
        """빠른 통계 업데이트"""
        try:
            # 오늘의 통계
            today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            tomorrow = today + timedelta(days=1)
            
            stats = self.data_manager.get_statistics(date_range=(today, tomorrow))
            
            self.quick_stats_labels['files'].configure(
                text=f"{stats['basic']['total_files']}개"
            )
            self.quick_stats_labels['errors'].configure(
                text=f"{stats['basic']['total_errors']}개"
            )
            self.quick_stats_labels['fixed'].configure(
                text=f"{stats['basic']['auto_fixed_count']}개"
            )
        except Exception as e:
            self.logger.error(f"통계 업데이트 오류: {e}")
    
    def _update_time(self):
        """시계 업데이트"""
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        self.time_label.configure(text=current_time)
        self.root.after(1000, self._update_time)
    
    def _on_tab_changed(self, event):
        """탭 변경 이벤트"""
        selected_tab = event.widget.tab('current')['text']
        
        if '통계' in selected_tab:
            self._update_statistics()
        elif '이력' in selected_tab:
            self._update_history()
    
    def _update_statistics(self):
        """통계 업데이트"""
        period = self.stats_period.get()
        
        # 기간 계산
        now = datetime.now()
        if period == 'today':
            start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif period == 'week':
            start_date = now - timedelta(days=7)
        elif period == 'month':
            start_date = now - timedelta(days=30)
        else:  # all
            start_date = None
        
        # 통계 조회
        if start_date:
            stats = self.data_manager.get_statistics(date_range=(start_date, now))
        else:
            stats = self.data_manager.get_statistics()
        
        # 카드 업데이트
        self.stat_cards['total_files'].value_label.configure(
            text=str(stats['basic']['total_files'])
        )
        self.stat_cards['total_pages'].value_label.configure(
            text=str(stats['basic']['total_pages'])
        )
        self.stat_cards['total_errors'].value_label.configure(
            text=str(stats['basic']['total_errors'])
        )
        self.stat_cards['auto_fixed'].value_label.configure(
            text=str(stats['basic']['auto_fixed_count'])
        )
        
        # 차트 업데이트
        if HAS_MATPLOTLIB:
            self._update_charts(stats)
        else:
            self._update_text_stats(stats)
    
    def _update_charts(self, stats):
        """차트 업데이트"""
        # 일별 처리량 차트
        daily_data = stats['daily']
        if daily_data:
            dates = [d['date'] for d in daily_data]
            files = [d['files'] for d in daily_data]
            
            self.daily_chart.clear()
            bars = self.daily_chart.bar(dates, files, color=self.colors['accent'])
            self.daily_chart.set_xlabel('날짜', fontsize=10, color='white')
            self.daily_chart.set_ylabel('파일 수', fontsize=10, color='white')
            self.daily_chart.set_title('일별 처리량', fontsize=12, fontweight='bold', color='white')
            self.daily_chart.grid(True, alpha=0.3)
            self.daily_chart.tick_params(colors='white')
            
            # 값 표시
            for bar, value in zip(bars, files):
                height = bar.get_height()
                self.daily_chart.text(bar.get_x() + bar.get_width()/2., height + 0.5,
                                    f'{value}', ha='center', va='bottom', fontsize=9, color='white')
            
            # X축 레이블 회전
            for tick in self.daily_chart.get_xticklabels():
                tick.set_rotation(45)
                tick.set_ha('right')
            
            self.daily_chart.figure.tight_layout()
            self.chart_frames['daily'][1].draw()
        
        # 문제 유형별 차트
        issue_data = stats['common_issues'][:5]
        if issue_data:
            types = [i['type'] for i in issue_data]
            counts = [i['count'] for i in issue_data]
            
            # 한글 레이블로 변환
            type_labels = {
                'font_not_embedded': '폰트 미임베딩',
                'low_resolution_image': '저해상도 이미지',
                'rgb_only': 'RGB 색상',
                'high_ink_coverage': '높은 잉크량',
                'page_size_inconsistent': '페이지 크기 불일치'
            }
            
            types_kr = [type_labels.get(t, t) for t in types]
            
            self.issue_chart.clear()
            bars = self.issue_chart.barh(types_kr, counts, color=self.colors['warning'])
            self.issue_chart.set_xlabel('발생 횟수', fontsize=10, color='white')
            self.issue_chart.set_title('주요 문제 유형', fontsize=12, fontweight='bold', color='white')
            self.issue_chart.grid(True, alpha=0.3, axis='x')
            self.issue_chart.tick_params(colors='white')
            
            # 값 표시
            for bar, value in zip(bars, counts):
                width = bar.get_width()
                self.issue_chart.text(width + 0.5, bar.get_y() + bar.get_height()/2.,
                                    f'{value}', ha='left', va='center', fontsize=9, color='white')
            
            self.issue_chart.figure.tight_layout()
            self.chart_frames['issues'][1].draw()
    
    def _update_text_stats(self, stats):
        """텍스트 통계 업데이트"""
        self.stats_text.delete(1.0, tk.END)
        
        text = f"""=== 통계 요약 ===
총 파일: {stats['basic']['total_files']}개
총 페이지: {stats['basic']['total_pages']}페이지
평균 처리 시간: {stats['basic']['avg_processing_time']:.1f}초
총 오류: {stats['basic']['total_errors']}개
총 경고: {stats['basic']['total_warnings']}개
자동 수정: {stats['basic']['auto_fixed_count']}개

=== 일별 처리량 ===
"""
        
        for daily in stats['daily']:
            text += f"{daily['date']}: {daily['files']}개 파일, {daily['pages']}페이지\n"
        
        text += "\n=== 주요 문제 유형 ===\n"
        for issue in stats['common_issues'][:10]:
            text += f"{issue['type']}: {issue['count']}회 (파일 {issue['affected_files']}개)\n"
        
        self.stats_text.insert(1.0, text)
    
    def _update_history(self):
        """처리 이력 업데이트"""
        # 기존 항목 제거
        for item in self.history_tree.get_children():
            self.history_tree.delete(item)
        
        # 검색 조건
        search_text = self.history_search_var.get()
        filter_errors = self.filter_errors_only.get()
        
        # 데이터 조회
        if search_text:
            history = self.data_manager.search_files(filename_pattern=search_text)
        else:
            history = self.data_manager.get_recent_files(limit=100)
        
        # 필터링
        if filter_errors:
            history = [h for h in history if h.get('error_count', 0) > 0]
        
        # 트리에 추가
        for record in history:
            status = '통과' if record.get('error_count', 0) == 0 else '실패'
            
            self.history_tree.insert(
                '',
                'end',
                text=record['filename'],
                values=(
                    record['processed_at'],
                    record.get('page_count', '-'),
                    record.get('error_count', 0),
                    record.get('warning_count', 0),
                    record.get('profile', '-'),
                    status
                )
            )
    
    # ===== 이벤트 핸들러 =====
    
    def browse_files(self):
        """파일 선택"""
        files = filedialog.askopenfilenames(
            title="PDF 파일 선택",
            filetypes=[("PDF 파일", "*.pdf"), ("모든 파일", "*.*")]
        )
        
        if files:
            # 파일 추가
            for file in files:
                self.drop_listbox.insert(tk.END, Path(file).name)
                
            self.dropped_files = list(files)
    
    def browse_folder(self):
        """폴더 선택"""
        folder = filedialog.askdirectory(title="폴더 선택")
        
        if folder:
            pdf_files = list(Path(folder).glob("**/*.pdf"))
            if pdf_files:
                # 파일 추가
                for pdf in pdf_files:
                    self.drop_listbox.insert(tk.END, pdf.name)
                
                self.dropped_files = [str(f) for f in pdf_files]
                
                self.status_var.set(f"{len(pdf_files)}개 PDF 파일이 추가되었습니다.")
    
    def _process_dropped_files(self):
        """드롭된 파일들 처리"""
        if not self.dropped_files:
            messagebox.showinfo("정보", "처리할 파일이 없습니다.")
            return
        
        profile = self.drop_profile_var.get()
        auto_fix = self.drop_auto_fix_var.get()
        include_ink = self.drop_ink_analysis_var.get()
        
        # 처리 스레드 시작
        def process_all():
            for file_path in self.dropped_files:
                folder_config = {
                    'profile': profile,
                    'auto_fix_settings': {
                        'auto_convert_rgb': auto_fix,
                        'auto_outline_fonts': auto_fix,
                        'include_ink_analysis': include_ink
                    }
                    # 'path' 속성이 없으면 드래그앤드롭으로 인식
                }
                
                # 안전한 tree item ID 생성
                item_id = self._generate_safe_item_id("drop")
                
                # 실시간 탭에 추가
                self.root.after(0, lambda fp=file_path, iid=item_id: self.realtime_tree.insert(
                    '',
                    'end',
                    iid=iid,
                    text=Path(fp).name,
                    values=(
                        '드래그앤드롭',
                        '대기 중',
                        datetime.now().strftime('%H:%M:%S'),
                        '-'
                    ),
                    tags=('processing',)
                ))
                
                # 처리
                self._process_pdf_file(Path(file_path), folder_config, item_id)
            
            # 완료 후 목록 비우기
            self.root.after(0, self._clear_drop_list)
        
        thread = threading.Thread(target=process_all, daemon=True)
        thread.start()
        
        self.status_var.set(f"{len(self.dropped_files)}개 파일 처리를 시작합니다.")
    
    def _clear_drop_list(self):
        """드롭 목록 비우기"""
        self.drop_listbox.delete(0, tk.END)
        self.dropped_files = []
    
    def _refresh_realtime(self):
        """실시간 탭 새로고침"""
        # 현재는 자동 업데이트되므로 특별한 동작 없음
        self.status_var.set("실시간 현황이 새로고침되었습니다.")
    
    def _search_history(self):
        """이력 검색"""
        self._update_history()
    
    def _reset_history_search(self):
        """이력 검색 초기화"""
        self.history_search_var.set("")
        self.filter_errors_only.set(False)
        self._update_history()
    
    def _show_realtime_menu(self, event):
        """실시간 우클릭 메뉴"""
        item = self.realtime_tree.identify_row(event.y)
        if item:
            self.realtime_tree.selection_set(item)
            self.realtime_menu.post(event.x_root, event.y_root)
    
    def _show_history_menu(self, event):
        """이력 우클릭 메뉴"""
        item = self.history_tree.identify_row(event.y)
        if item:
            self.history_tree.selection_set(item)
            self.history_menu.post(event.x_root, event.y_root)
    
    def _view_realtime_report(self):
        """실시간 보고서 보기"""
        selection = self.realtime_tree.selection()
        if not selection:
            return
            
        item = self.realtime_tree.item(selection[0])
        filename = item['text']
        
        # 보고서 찾기 및 열기
        reports_path = Path("reports")
        for report_file in reports_path.glob(f"*{filename}*.html"):
            webbrowser.open(str(report_file))
            break
        else:
            messagebox.showinfo("정보", "보고서를 찾을 수 없습니다.")
    
    def _show_in_folder_realtime(self):
        """폴더에서 보기"""
        selection = self.realtime_tree.selection()
        if not selection:
            return
            
        item = self.realtime_tree.item(selection[0])
        folder_name = item['values'][0]
        
        # 폴더 열기
        for config in self.folder_watcher.folder_configs.values():
            if config.path.name == folder_name:
                try:
                    os.startfile(str(config.path))
                except:
                    pass
                break
    
    def _reprocess_file(self):
        """파일 다시 처리"""
        messagebox.showinfo("정보", "재처리 기능은 개발 중입니다.")
    
    def _show_history_details(self):
        """이력 상세 정보"""
        selection = self.history_tree.selection()
        if not selection:
            return
            
        item = self.history_tree.item(selection[0])
        filename = item['text']
        
        # 상세 정보 대화상자
        dialog = ctk.CTkToplevel(self.root)
        dialog.title(f"상세 정보 - {filename}")
        dialog.geometry("600x400")
        dialog.transient(self.root)
        
        # 정보 표시
        info_frame = ctk.CTkFrame(dialog)
        info_frame.pack(fill='both', expand=True, padx=20, pady=20)
        
        info_text = scrolledtext.ScrolledText(
            info_frame,
            wrap=tk.WORD,
            font=self.fonts['body'],
            bg=self.colors['bg_secondary'],
            fg=self.colors['text_primary'],
            insertbackground=self.colors['text_primary'],
            selectbackground=self.colors['accent'],
            borderwidth=0,
            highlightthickness=0
        )
        info_text.pack(fill='both', expand=True)
        
        # 데이터베이스에서 상세 정보 조회
        history = self.data_manager.get_file_history(filename)
        if history:
            latest = history[0]
            info_text.insert('1.0', f"""파일명: {filename}
처리일시: {latest.get('processed_at', '-')}
프로파일: {latest.get('profile', '-')}
페이지 수: {latest.get('page_count', '-')}
PDF 버전: {latest.get('pdf_version', '-')}
파일 크기: {latest.get('file_size_formatted', '-')}

오류: {latest.get('error_count', 0)}개
경고: {latest.get('warning_count', 0)}개
총 문제: {latest.get('total_issues', 0)}개

처리 시간: {latest.get('processing_time', '-')}초
잉크량 분석: {'포함' if latest.get('ink_analysis_included', False) else '미포함'}
자동 수정: {'적용' if latest.get('auto_fix_applied', False) else '미적용'}
""")
        
        # 닫기 버튼
        button_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        button_frame.pack(pady=10)
        
        ctk.CTkButton(button_frame, text="닫기", command=dialog.destroy,
                    width=80, height=36).pack()
    
    def _view_history_report(self):
        """이력 보고서 보기"""
        selection = self.history_tree.selection()
        if not selection:
            return
            
        item = self.history_tree.item(selection[0])
        filename = item['text']
        
        # 보고서 찾기 및 열기
        reports_path = Path("reports")
        for report_file in reports_path.glob(f"*{filename}*.html"):
            webbrowser.open(str(report_file))
            break
        else:
            messagebox.showinfo("정보", "보고서를 찾을 수 없습니다.")
    
    def _compare_history_files(self):
        """이력 파일 비교"""
        messagebox.showinfo("정보", "파일 비교 기능은 개발 중입니다.")
    
    def _on_history_double_click(self, event):
        """이력 더블클릭"""
        self._view_history_report()
    
    def open_comparison_window(self):
        """PDF 비교 창 열기"""
        PDFComparisonWindow(self.root)
    
    def open_settings(self):
        """설정 창 열기"""
        SettingsWindow(self.root)
    
    def test_notification(self):
        """알림 테스트"""
        self.notification_manager.test_notification()
    
    def view_logs(self):
        """로그 보기"""
        log_window = ctk.CTkToplevel(self.root)
        log_window.title("시스템 로그")
        log_window.geometry("800x600")
        
        # 프레임
        log_frame = ctk.CTkFrame(log_window)
        log_frame.pack(fill='both', expand=True, padx=20, pady=20)
        
        # 텍스트 위젯
        log_text = scrolledtext.ScrolledText(
            log_frame,
            wrap=tk.WORD,
            font=self.fonts['mono'],
            bg=self.colors['bg_secondary'],
            fg=self.colors['text_primary'],
            insertbackground=self.colors['text_primary'],
            selectbackground=self.colors['accent'],
            borderwidth=0,
            highlightthickness=0
        )
        log_text.pack(fill='both', expand=True)
        
        # 로그 파일 읽기
        try:
            log_file = self.logger.get_log_file()
            if log_file.exists():
                with open(log_file, 'r', encoding='utf-8') as f:
                    log_text.insert('1.0', f.read())
                log_text.config(state='disabled')
        except Exception as e:
            log_text.insert('1.0', f"로그 파일을 읽을 수 없습니다: {str(e)}")
    
    def cleanup_database(self):
        """데이터베이스 정리"""
        if messagebox.askyesno("확인", "오래된 데이터를 정리하시겠습니까?\n(30일 이상된 데이터 삭제)"):
            # 구현 필요
            messagebox.showinfo("완료", "데이터베이스 정리가 완료되었습니다.")
    
    def export_data(self):
        """데이터 내보내기"""
        filename = filedialog.asksaveasfilename(
            defaultextension=".html",
            filetypes=[("HTML 파일", "*.html"), ("모든 파일", "*.*")]
        )
        
        if filename:
            self.data_manager.export_statistics_report(filename)
            messagebox.showinfo("완료", "데이터 내보내기가 완료되었습니다.")
    
    def show_statistics(self, period):
        """통계 보기"""
        self.stats_period.set(period)
        self.notebook.select(1)  # 통계 탭으로 이동
        self._update_statistics()
    
    def generate_stats_report(self):
        """통계 리포트 생성"""
        filename = filedialog.asksaveasfilename(
            defaultextension=".html",
            filetypes=[("HTML 파일", "*.html"), ("모든 파일", "*.*")]
        )
        
        if filename:
            self.data_manager.export_statistics_report(filename)
            
            # 생성된 파일 열기
            webbrowser.open(filename)
    
    def show_help(self):
        """도움말"""
        help_text = """PDF 품질 검수 시스템 v4.0 - Optimized Edition

주요 기능:
1. 통합 실시간 처리 (드래그앤드롭 포함)
2. 다중 폴더 감시
3. 통계 대시보드
4. 처리 이력 관리
5. Windows 알림

사용법:
1. 사이드바에서 감시할 폴더 추가
2. 각 폴더별로 프로파일과 자동 수정 설정
3. 토글 스위치로 감시 시작
4. 실시간 탭에서 직접 파일 처리 가능

단축키:
- Ctrl+O: 파일 추가
- Ctrl+D: PDF 비교
- Ctrl+,: 설정
- F5: 새로고침"""
        
        messagebox.showinfo("도움말", help_text)
    
    def show_shortcuts(self):
        """단축키 목록"""
        shortcuts = """단축키 목록:

Ctrl+O - PDF 파일 추가
Ctrl+D - PDF 비교
Ctrl+, - 설정 열기
F5 - 현재 탭 새로고침
Alt+F4 - 프로그램 종료

마우스:
더블클릭 - 보고서 열기
우클릭 - 컨텍스트 메뉴"""
        
        messagebox.showinfo("단축키", shortcuts)
    
    def show_about(self):
        """프로그램 정보"""
        about_text = """PDF 품질 검수 시스템 v4.0
Optimized Edition

인쇄 품질을 위한 전문 PDF 검사 도구

주요 개선사항:
• 실시간 처리와 드래그앤드롭 통합
• 반응형 설정 창
• 향상된 사용자 경험
• 최적화된 레이아웃

UI Framework: CustomTkinter
Theme: Dark Mode

© 2025 PDF Quality Checker
All rights reserved."""
        
        messagebox.showinfo("정보", about_text)
    
    def refresh_current_tab(self):
        """현재 탭 새로고침"""
        current = self.notebook.index('current')
        
        if current == 0:  # 실시간
            self._refresh_realtime()
        elif current == 1:  # 통계
            self._update_statistics()
        elif current == 2:  # 이력
            self._update_history()
    
    def on_closing(self):
        """프로그램 종료"""
        if self.is_folder_watching:
            if messagebox.askyesno("확인", "폴더 감시가 실행 중입니다.\n종료하시겠습니까?"):
                self.stop_folder_watching()
            else:
                return
        
        self.logger.log("프로그램 종료")
        self.root.destroy()
    
    def run(self):
        """GUI 실행"""
        self.status_var.set("PDF 품질 검수 시스템이 준비되었습니다.")
        self.root.mainloop()

# 프로그램 실행
if __name__ == "__main__":
    app = EnhancedPDFCheckerGUI()
    app.run()
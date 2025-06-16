# 0616_pdf_quality_checker

# PDF 자동검수 시스템 Phase 4.0 - 기술 명세서 (Claude 최적화) Complete

## 📌 Quick Reference for Claude

**시스템 버전**: Phase 4.0 Modern UI Edition (2025.06.16 최종 수정)  
**UI Framework**: CustomTkinter (다크 모드) - Phase 3.5에서 마이그레이션  
**주요 진입점**: `pdf_checker_gui_enhanced.py` (통합 GUI)  
**데이터베이스**: `pdf_checker_history.db` (SQLite)  
**설정 파일**: `user_settings.json`, `folder_watch_config.json`

### 🆕 2025.06.16 주요 변경사항
- **오버프린트 감지 개선**: 인쇄상 문제되는 경우만 감지
- **블리드 검사 통합**: 중복 제거, pdf_analyzer에서만 수행
- **잉크량 검사 옵션화**: 기본 OFF, 사용자 선택 가능
- **Config 모듈 개선**: 잉크량/오버프린트 세부 설정 추가

## 1. System Architecture (Phase 4.0 + CustomTkinter)

```python
# 🎯 PRIMARY ENTRY POINT
MAIN_ENTRY = 'pdf_checker_gui_enhanced.py'  # 모든 기능 통합

# Core Dependencies Graph
MODULE_DEPENDENCIES = {
    'pdf_checker_gui_enhanced.py': {
        'ui_framework': 'customtkinter',  # 🆕 Phase 4.0 변경
        'core_modules': [
            'pdf_analyzer.PDFAnalyzer',           # PDF 분석
            'report_generator.ReportGenerator',    # 보고서 생성
            'batch_processor.BatchProcessor',      # 배치 처리
            'config.Config',                       # 설정 관리
        ],
        'phase4_modules': [
            'data_manager.DataManager',            # SQLite DB 관리
            'notification_manager.NotificationManager',  # Windows 알림
            'multi_folder_watcher.MultiFolderWatcher',  # 다중 폴더 감시
        ],
        'ui_modules': [
            'settings_window.SettingsWindow',
            'pdf_comparison_window.PDFComparisonWindow',
        ],
        'optional': [
            'tkinterdnd2',    # 드래그앤드롭
            'matplotlib',     # 차트 (한글 설정 필요)
            'watchdog',       # 폴더 감시 (없으면 폴링)
        ]
    }
}

# 🆕 CustomTkinter 설정
CUSTOMTKINTER_CONFIG = {
    'appearance_mode': 'dark',
    'default_color_theme': 'blue',
    'colors': {
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
}
```

## 2. Key Issues Fixed in Phase 4.0

### 2.1 드래그앤드롭 버그 수정 ✅
```python
# 문제: 파일명의 특수문자(대괄호 등)로 TclError 발생
# 해결: 안전한 ID 생성 메서드 활용

def _generate_safe_item_id(self, prefix="item"):
    """Treeview에서 안전하게 사용할 수 있는 ID 생성"""
    self.item_counter += 1
    timestamp = int(time.time() * 1000)
    return f"{prefix}_{self.item_counter}_{timestamp}"

# 사용 예시
item_id = self._generate_safe_item_id("drop")  # "drop_1_1736825000000"
```

### 2.2 잉크량 검수 옵션화 ✅ (2025.06.16 개선)
```python
# 🆕 Config.py 추가사항
DEFAULT_INK_ANALYSIS = False  # 기본 OFF로 변경
CHECK_OPTIONS = {
    'ink_coverage': False  # 잉크량 검사 옵션 추가
}

# 🆕 잉크량 검사 제어 메서드
@classmethod
def set_ink_analysis(cls, enabled: bool):
    """잉크량 분석 ON/OFF 설정"""
    cls.DEFAULT_INK_ANALYSIS = enabled
    cls.CHECK_OPTIONS['ink_coverage'] = enabled

@classmethod
def is_ink_analysis_enabled(cls) -> bool:
    """잉크량 분석 활성화 여부 확인"""
    return cls.CHECK_OPTIONS.get('ink_coverage', False)

# 폴더별 개별 설정 가능
folder_config = {
    'auto_fix_settings': {
        'auto_convert_rgb': True,
        'auto_outline_fonts': False,
        'include_ink_analysis': False  # 🎨 잉크량 분석 옵션
    }
}

# GUI 표시
if folder.get('auto_fix_settings', {}).get('include_ink_analysis', False):
    display_icon = "🎨"  # 폴더 목록에 표시
```

### 2.3 보고서 생성 경로 수정 ✅
```python
# 문제: ReportGenerator가 항상 기본 reports/ 폴더 사용
# 해결: save_text_report/save_html_report 직접 호출

# 폴더 감시의 경우
reports_folder = file_path.parent / 'reports'  # 감시 폴더 내
reports_folder.mkdir(exist_ok=True)

# 직접 경로 지정하여 저장
text_path = generator.save_text_report(result, output_path=reports_folder / f"{report_filename}.txt")
html_path = generator.save_html_report(result, output_path=reports_folder / f"{report_filename}.html")
```

### 2.4 matplotlib 한글 문제 해결 ✅
```python
def _create_charts(self, parent):
    """차트 생성 (matplotlib)"""
    # 한글 폰트 설정 필수!
    import matplotlib.pyplot as plt
    plt.rcParams['font.family'] = 'Malgun Gothic'  # 맑은 고딕
    plt.rcParams['axes.unicode_minus'] = False     # 마이너스 기호 깨짐 방지
```

### 2.5 날짜 형식 문제 (data_manager.py 수정 필요) ⚠️
```python
# 문제: SQLite와 Python datetime 형식 불일치
# SQLite: '2025-06-14 08:26:16'
# Python: '2025-06-14T00:00:00' (isoformat)

# 해결: data_manager.py의 get_statistics 메서드 수정
if date_range:
    params = [
        date_range[0].strftime('%Y-%m-%d %H:%M:%S'),  # isoformat 대신
        date_range[1].strftime('%Y-%m-%d %H:%M:%S')
    ]
```

### 2.6 CustomTkinter place() 제약 해결 ✅
```python
# 문제: CustomTkinter에서 place()에 width, height 사용 불가
# 해결: 생성자에서 크기 지정

# ❌ 잘못된 방법
options_card.place(relx=0.5, rely=0.75, width=400)  # ValueError

# ✅ 올바른 방법
options_card = ctk.CTkFrame(drop_frame, width=400, height=200)
options_card.place(relx=0.5, rely=0.75)
```

### 🆕 2.7 오버프린트 감지 개선 (2025.06.16)
```python
# print_quality_checker.py 개선사항

def check_overprint(self, pdf_path):
    """
    중복인쇄(Overprint) 설정 검사
    2025.06 수정: 인쇄상 문제가 되는 경우만 감지하도록 개선
    """
    overprint_info = {
        'has_overprint': False,
        'has_problematic_overprint': False,  # 문제가 되는 오버프린트
        'white_overprint_pages': [],         # 흰색 오버프린트 (위험)
        'k_only_overprint_pages': [],        # K100% 오버프린트 (정상)
        'light_color_overprint_pages': [],   # 라이트 컬러 오버프린트 (경고)
    }
    
    # 감지 로직:
    # 1. 흰색(CMYK 0,0,0,0) 오버프린트 → 오류 (객체가 사라짐)
    # 2. K100% 텍스트 오버프린트 → 정보 (정상적인 녹아웃 방지)
    # 3. 기타 오버프린트 → 경고 (확인 필요)
```

### 🆕 2.8 블리드 검사 통합 (2025.06.16)
```python
# 중복 제거: pdf_analyzer.py에서만 실제 검사 수행

# pdf_analyzer.py
def _analyze_pages(self, pdf_obj):
    """블리드 정보를 여기서만 계산"""
    page_info['has_bleed'] = True
    page_info['bleed_info'] = {...}
    page_info['min_bleed'] = min_bleed

# print_quality_checker.py
def check_all(self, pdf_path, pages_info=None):
    """pages_info를 받아서 블리드 정보 활용"""
    results['bleed'] = self.process_bleed_info(pages_info)

def process_bleed_info(self, pages_info):
    """pdf_analyzer의 결과를 처리만 함"""
    # 중복 계산 없이 전달받은 정보 활용

# preflight_profiles.py
def _check_rule(self, rule: PreflightRule, analysis_result: Dict):
    if rule.check_type == 'bleed_margin':
        # print_quality의 결과 사용 (중복 계산 방지)
        bleed_info = analysis_result.get('print_quality', {}).get('bleed', {})
```

## 3. Folder Structure (Phase 4.0)

```
감시폴더/
├── sample.pdf              # 원본 파일 (처리 후 이동)
├── reports/               # 보고서 (자동 생성)
│   ├── sample_report_20250114_150230.txt
│   └── sample_report_20250114_150230.html
├── completed/             # 정상 처리된 파일
├── errors/               # 오류 파일
└── backup/               # 백업 (선택사항)

프로젝트폴더/
├── reports/              # 드래그앤드롭 보고서
├── logs/                 # 시스템 로그
└── pdf_checker_history.db  # 처리 이력 DB
```

## 4. Critical Method Signatures (Phase 4.0 Updated)

### 4.1 폴더 감시 vs 드래그앤드롭 구분
```python
def _process_pdf_file(self, file_path: Path, folder_config: Dict, tree_item_id: str):
    # 드래그앤드롭과 폴더 감시 구분
    is_folder_watch = folder_config.get('path') is not None
    
    # 🆕 잉크량 분석 옵션 확인 (2025.06.16)
    if folder_config:
        include_ink = folder_config.get('auto_fix_settings', {}).get(
            'include_ink_analysis', Config.is_ink_analysis_enabled()
        )
    else:
        include_ink = Config.is_ink_analysis_enabled()
    
    if is_folder_watch:
        # 감시 폴더 내 하위 폴더 사용
        output_base = file_path.parent
        reports_folder = output_base / 'reports'
    else:
        # 드래그앤드롭은 기본 reports 폴더
        reports_folder = Config.REPORTS_PATH
```

### 🆕 4.2 PDFAnalyzer 수정 (2025.06.16)
```python
def analyze(self, pdf_path, include_ink_analysis=None, preflight_profile='offset'):
    """
    include_ink_analysis가 None이면 Config 설정 사용
    """
    if include_ink_analysis is None:
        include_ink_analysis = Config.is_ink_analysis_enabled()
    
    # ... 분석 수행 ...
    
    # 블리드 검사는 _analyze_pages에서만 수행
    # print_quality_checker에 페이지 정보 전달
    print_quality_result = self.print_quality_checker.check_all(
        pdf_path, 
        pages_info=local_analysis_result['pages']  # 블리드 정보 포함
    )
```

### 4.3 폴더 설정 편집 (CustomTkinter)
```python
def edit_folder_settings(self):
    """폴더 설정 편집 - CTkToplevel 사용"""
    dialog = ctk.CTkToplevel(self.root)  # 🆕 CustomTkinter 대화상자
    dialog.title("폴더 설정 편집")
    dialog.geometry("550x550")
    
    # 프로파일, 자동 수정, 잉크량 분석 옵션 수정 가능
    # 폴더 활성화/비활성화 기능
    # 설정 즉시 저장 (folder_watch_config.json)
```

### 4.4 폴더 감시 토글 (CTkSwitch)
```python
# 🆕 CTkSwitch 사용
self.watch_toggle_switch = ctk.CTkSwitch(
    status_header,
    text="",
    command=self.toggle_folder_watching,
    button_color=self.colors['accent'],
    progress_color=self.colors['success'],
    width=50,
    height=24
)

def toggle_folder_watching(self):
    """스위치 상태에 따라 감시 시작/중지"""
    if self.watch_toggle_switch.get():  # 1 or 0
        self.start_folder_watching()
    else:
        self.stop_folder_watching()
```

### 4.5 하위 폴더 자동 생성
```python
def _create_folder_structure(self, folder_path):
    """핫폴더 하위 구조 자동 생성"""
    subfolders = ['reports', 'output', 'completed', 'errors', 'backup']
    for subfolder in subfolders:
        (Path(folder_path) / subfolder).mkdir(exist_ok=True)
```

### 🆕 4.6 설정 창 잉크량 섹션 (2025.06.16)
```python
# settings_window.py에 추가된 섹션
def _create_processing_tab(self):
    # 잉크량 분석 섹션
    ink_analysis_frame = ttk.LabelFrame(scrollable_frame, text="🎨 잉크량 분석", padding="10")
    
    self._create_checkbox_setting(
        ink_analysis_frame, "ink_coverage", "잉크량 분석 활성화",
        "PDF 파일의 잉크 커버리지를 분석합니다 (처리 시간이 크게 증가합니다)", 
        Config.CHECK_OPTIONS.get('ink_coverage', False)
    )
    
    # 경고 메시지 표시
    warning_label = ttk.Label(
        warning_frame,
        text="⚠️ 잉크량 분석은 파일당 10-30초의 추가 시간이 소요됩니다.",
        foreground="red"
    )
```

## 5. GUI Layout Updates (Phase 4.0 CustomTkinter)

### 5.1 현대적 디자인 적용
```python
# CustomTkinter 초기화
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# 색상 팔레트 (실제 사용중)
self.colors = {
    'bg_primary': '#1a1a1a',      # 메인 배경
    'bg_secondary': '#252525',     # 사이드바 배경
    'bg_card': '#2d2d2d',         # 카드 배경
    'accent': '#0078d4',          # 강조색 (파란색)
    'accent_hover': '#106ebe',    # 호버 색상
    'success': '#107c10',         # 성공 (초록색)
    'warning': '#ff8c00',         # 경고 (주황색)
    'error': '#d83b01',           # 오류 (빨간색)
    'text_primary': '#ffffff',    # 주 텍스트
    'text_secondary': '#b3b3b3',  # 보조 텍스트
    'border': '#404040'           # 테두리
}

# 한글 폰트 설정
self.fonts = {
    'title': ('맑은 고딕', 16, 'bold'),
    'heading': ('맑은 고딕', 13, 'bold'),
    'subheading': ('맑은 고딕', 11, 'bold'),
    'body': ('맑은 고딕', 10),
    'small': ('맑은 고딕', 9),
    'mono': ('D2Coding', 10)  # 코드용
}
```

### 5.2 위젯 변경 매핑
```python
# tkinter/ttk → customtkinter 변환
WIDGET_MAPPING = {
    # 변경된 위젯
    'tk.Tk()': 'ctk.CTk()',
    'tk.Toplevel()': 'ctk.CTkToplevel()',
    'ttk.Frame': 'ctk.CTkFrame',
    'ttk.Button': 'ctk.CTkButton',
    'ttk.Label': 'ctk.CTkLabel',
    'ttk.Entry': 'ctk.CTkEntry',
    'ttk.Checkbutton': 'ctk.CTkCheckBox',
    'ttk.Radiobutton': 'ctk.CTkRadioButton',
    '폴더 감시 토글': 'ctk.CTkSwitch',  # 🆕 새로운 위젯
    
    # 유지되는 위젯 (안정성)
    'tk.Listbox': 'tk.Listbox',  # 폴더 목록
    'ttk.Treeview': 'ttk.Treeview',  # 파일 목록
    'ttk.Notebook': 'ttk.Notebook',  # 탭
    'tk.Menu': 'tk.Menu',  # 메뉴바
}
```

### 5.3 사이드바 개선
```python
# 폴더 목록 표시 형식
"✓ 폴더명 (프로파일) 🎨"  # 🎨는 잉크량 분석 ON일 때만

# 폴더 감시 상태 (CTkSwitch)
self.watch_toggle_switch = ctk.CTkSwitch(
    status_header,
    text="",
    command=self.toggle_folder_watching
)
self.watch_status_label = ctk.CTkLabel(text="⏸️ 감시 중지됨")

# 빠른 통계 카드
stats_card = ctk.CTkFrame(sidebar, 
                         fg_color=self.colors['bg_card'],
                         corner_radius=10)
- 처리 파일: N개 (accent color)
- 오류: N개 (error color)  
- 자동 수정: N개 (success color)
```

## 6. Configuration Files

### 🆕 6.1 Config.py 주요 설정 (2025.06.16 업데이트)
```python
# 잉크량 검사 설정
DEFAULT_INK_ANALYSIS = False  # 기본 OFF
INK_CALCULATION_DPI = 150    # 계산 해상도
INK_ANALYSIS_OPTIONS = {
    'enabled': False,         # 기본값: OFF
    'dpi': 150,              # 계산 해상도
    'timeout': 60,           # 최대 처리 시간(초)
}

# 검사 옵션
CHECK_OPTIONS = {
    'transparency': False,    # 투명도 검사
    'overprint': True,       # 중복인쇄 검사
    'bleed': True,          # 재단선 검사
    'spot_colors': True,    # 별색 상세 검사
    'ink_coverage': False   # 🆕 잉크량 검사 (기본 OFF)
}

# 🆕 오버프린트 세부 설정
OVERPRINT_SETTINGS = {
    'check_white_overprint': True,      # 흰색 오버프린트 검사 (위험)
    'k_only_as_normal': True,           # K100%는 정상으로 처리
    'warn_light_colors': True,          # 라이트 컬러 경고
    'light_color_threshold': 20,        # CMYK 합계 20% 이하를 라이트로 정의
    'detailed_reporting': True          # 상세 보고 (타입별 분류)
}
```

### 6.2 folder_watch_config.json
```json
{
  "folders": [
    {
      "path": "C:\\감시폴더",
      "profile": "offset",
      "auto_fix_settings": {
        "auto_convert_rgb": true,
        "auto_outline_fonts": false,
        "include_ink_analysis": false  // 잉크량 분석 옵션
      },
      "output_folder": null,  // null이면 감시 폴더 사용
      "enabled": true,
      "files_processed": 42,
      "last_processed": "2025-01-14T15:30:00"
    }
  ],
  "last_saved": "2025-01-14T15:35:00"
}
```

### 🆕 6.3 user_settings.json (2025.06.16 구조 개선)
```json
{
  "check_options": {
    "transparency": false,
    "overprint": true,
    "bleed": true,
    "spot_colors": true,
    "ink_coverage": false  // 전역 잉크량 검사 설정
  },
  "ink_calculation_dpi": "150",
  "max_ink_coverage": 300,
  "warning_ink_coverage": 280,
  "enable_notifications": true,
  "notify_on_success": true,
  "default_preflight_profile": "offset"
}
```

## 7. Event Flow Examples

### 7.1 폴더 감시 이벤트
```python
EVENT_FLOW = {
    'trigger': 'PDF 파일 추가됨',
    'flow': [
        'PDFEventHandler.on_created()',
        'callback: GUI._on_folder_pdf_found()',
        'item_id = _generate_safe_item_id("folder")',  # 안전한 ID
        'GUI._process_pdf_file() in thread',
        '🆕 include_ink = folder_config["include_ink_analysis"]',  # 폴더 설정 확인
        'PDFAnalyzer.analyze(include_ink_analysis=include_ink)',
        'DataManager.save_analysis_result()',
        'ReportGenerator.save_text_report(output_path=감시폴더/reports/)',
        'ReportGenerator.save_html_report(output_path=감시폴더/reports/)',
        'shutil.move(파일 → completed/ or errors/)',
        'NotificationManager.notify_success()'
    ]
}
```

### 7.2 드래그앤드롭 이벤트
```python
DRAGDROP_FLOW = {
    'trigger': '파일 드롭',
    'flow': [
        '_parse_drop_files() - 경로 파싱',
        'dropped_files 리스트에 추가',
        '_process_dropped_files() 호출',
        'folder_config = {profile, auto_fix_settings} (path 없음)',
        'item_id = _generate_safe_item_id("drop")',
        '🆕 include_ink = self.drop_ink_analysis_var.get()',  # UI 체크박스 확인
        '_process_pdf_file() - 기본 reports/ 폴더 사용',
        '파일 이동 없음 (원본 위치 유지)'
    ]
}
```

## 8. Common Issues & Solutions

### 8.1 트리뷰 ID 문제
```python
# ❌ 잘못된 방법
item_id = f"drop_{filename}"  # 특수문자 있으면 TclError

# ✅ 올바른 방법  
item_id = self._generate_safe_item_id("drop")
```

### 8.2 보고서 경로 문제
```python
# ❌ 작동 안함
generator.output_folder = str(reports_folder)

# ✅ 올바른 방법
text_path = generator.save_text_report(result, output_path=reports_folder / "report.txt")
```

### 8.3 날짜 비교 문제
```python
# ❌ 형식 불일치
params = [date_range[0].isoformat()]  # 2025-01-14T00:00:00

# ✅ SQLite 형식 맞춤
params = [date_range[0].strftime('%Y-%m-%d %H:%M:%S')]  # 2025-01-14 00:00:00
```

### 8.4 CustomTkinter 제약사항
```python
# ❌ place()에서 크기 지정
frame.place(relx=0.5, rely=0.5, width=400)  # ValueError

# ✅ 생성자에서 크기 지정
frame = ctk.CTkFrame(parent, width=400, height=200)
frame.place(relx=0.5, rely=0.5)
```

### 8.5 다크 모드 Treeview 스타일
```python
# ttk 위젯은 수동으로 다크 테마 적용 필요
self.style.configure("Treeview",
    background=self.colors['bg_secondary'],
    foreground=self.colors['text_primary'],
    fieldbackground=self.colors['bg_secondary']
)
```

### 🆕 8.6 오버프린트 감지 이슈 (2025.06.16)
```python
# ❌ 모든 오버프린트를 문제로 처리
if overprint.get('has_overprint'):
    issues.append({'severity': 'error', ...})

# ✅ 타입별로 구분 처리
if overprint.get('white_overprint_pages'):  # 흰색 오버프린트만 오류
    issues.append({'severity': 'error', ...})
elif overprint.get('k_only_overprint_pages'):  # K100%는 정보
    warnings.append({'severity': 'info', ...})
```

### 🆕 8.7 블리드 중복 검사 (2025.06.16)
```python
# ❌ 여러 곳에서 중복 검사
# pdf_analyzer.py, print_quality_checker.py, preflight_profiles.py

# ✅ pdf_analyzer.py에서만 검사, 나머지는 결과 활용
# pdf_analyzer.py
pages_info = self._analyze_pages(pdf_obj)  # 블리드 계산 포함

# print_quality_checker.py  
results['bleed'] = self.process_bleed_info(pages_info)  # 결과만 활용
```

## 9. Quick Debug Commands

```python
# 시스템 상태 확인
status = self.folder_watcher.get_status()
print(f"감시 중: {status['is_watching']}")
print(f"폴더 수: {status['total_folders']}")

# 🆕 잉크량 검사 설정 확인
print(f"잉크량 검사 전역 설정: {Config.is_ink_analysis_enabled()}")
print(f"CHECK_OPTIONS: {Config.CHECK_OPTIONS}")

# 오늘 통계 확인
today = datetime.now().replace(hour=0, minute=0, second=0)
tomorrow = today + timedelta(days=1)
stats = self.data_manager.get_statistics(date_range=(today, tomorrow))

# 로그 확인
log_file = self.logger.get_log_file()
print(log_file.read_text(encoding='utf-8')[-1000:])  # 마지막 1000자

# 폴더 설정 확인
import json
config = json.load(open("folder_watch_config.json"))
print(json.dumps(config, indent=2, ensure_ascii=False))

# CustomTkinter 테마 확인
print(ctk.get_appearance_mode())  # "Dark" or "Light"

# 위젯 타입 확인
print(type(self.watch_toggle_switch))  # <class 'customtkinter.windows.widgets.ctk_switch.CTkSwitch'>

# 🆕 user_settings.json 확인
settings = json.load(open("user_settings.json"))
print(f"잉크량 검사: {settings.get('check_options', {}).get('ink_coverage', False)}")
```

## 10. Phase 4.0 Key Improvements Summary

| 기능 | Phase 3.5 | Phase 4.0 | 🆕 2025.06.16 |
|------|-----------|-----------|----------------|
| 진입점 | main.py + GUI | 통합 GUI만 | - |
| UI 프레임워크 | tkinter + ttk | **CustomTkinter (다크 모드)** | - |
| 드래그앤드롭 | 특수문자 버그 | 안전한 ID 생성 | - |
| 잉크량 검수 | 항상 ON | 폴더별 옵션 | **기본 OFF, Config 메서드 추가** |
| 오버프린트 감지 | 모든 경우 경고 | - | **타입별 구분 (흰색/K100%/기타)** |
| 블리드 검사 | 3곳에서 중복 | - | **pdf_analyzer에서만 수행** |
| 폴더 설정 | 추가만 가능 | 완전한 편집 가능 | - |
| 폴더 감시 토글 | 일반 버튼 | **CTkSwitch** | - |
| 보고서 위치 | 고정 (reports/) | 감시 폴더 내 | - |
| 통계 차트 | 한글 깨짐 | matplotlib 한글 설정 | - |
| 데이터 저장 | 날짜 형식 문제 | strftime 사용 | - |
| UI 디자인 | 기본 tkinter | **현대적 다크 테마** | - |
| 대화상자 | tk.Toplevel | **ctk.CTkToplevel** | - |
| 설정 창 | 기본 구성 | - | **잉크량 검사 섹션 추가** |

## 🚨 Critical Notes for Claude

1. **항상 `_generate_safe_item_id()` 사용** - 트리뷰 아이템 추가 시
2. **보고서 생성은 직접 경로 지정** - `save_text_report(output_path=...)`
3. **matplotlib 사용 시 한글 설정 필수** - `plt.rcParams['font.family'] = 'Malgun Gothic'`
4. **날짜는 strftime 형식 사용** - SQLite 호환성
5. **폴더 감시와 드래그앤드롭 구분** - `folder_config.get('path')` 확인
6. **CustomTkinter 제약사항** - `place(width=X)` 불가, 생성자에서 크기 지정
7. **다크 모드 색상은 self.colors 사용** - 하드코딩 대신 딕셔너리 참조
8. **유지되는 위젯 주의** - Treeview, Listbox는 tk/ttk 그대로 사용
9. **CTkSwitch로 토글** - 폴더 감시는 스위치 위젯 사용
10. **대화상자는 CTkToplevel** - tk.Toplevel 대신 사용
11. 🆕 **잉크량 검사는 Config.is_ink_analysis_enabled()** - 전역 설정 확인
12. 🆕 **오버프린트는 타입별 처리** - 흰색/K100%/기타 구분
13. 🆕 **블리드는 pdf_analyzer 결과 활용** - 중복 계산 방지
14. 🆕 **print_quality_checker.check_all()에 pages_info 전달** - 블리드 정보 포함

---

*이 문서는 Claude가 PDF 검수 시스템을 이해하고 수정하기 위한 핵심 정보만 포함합니다.*  
*최종 업데이트: 2025.06.16 - 오버프린트 개선, 블리드 통합, 잉크량 옵션화*

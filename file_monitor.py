# file_monitor.py - 폴더를 감시하고 새 PDF를 자동으로 처리합니다
# Phase 2.5: 프리플라이트 프로파일 지원 추가

"""
file_monitor.py - 실시간 파일 모니터링 시스템
Phase 2.5: 프리플라이트 프로파일 적용 가능
"""

import time
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from config import Config
from pdf_analyzer import PDFAnalyzer
from report_generator import ReportGenerator
from preflight_profiles import PreflightProfiles
from utils import format_datetime
import shutil
import threading

class PDFHandler(FileSystemEventHandler):
    """PDF 파일 이벤트를 처리하는 핸들러"""
    
    def __init__(self, preflight_profile='offset'):
        self.config = Config()
        self.analyzer = PDFAnalyzer()
        self.report_generator = ReportGenerator()
        self.processing_files = set()  # 현재 처리 중인 파일들
        self.lock = threading.Lock()   # 스레드 안전성을 위한 락
        self.preflight_profile = preflight_profile  # Phase 2.5: 프리플라이트 프로파일
        
    def on_created(self, event):
        """파일이 생성되었을 때 호출"""
        if not event.is_directory and event.src_path.lower().endswith('.pdf'):
            # 파일 복사가 완료될 때까지 잠시 대기
            time.sleep(Config.PROCESS_DELAY)
            self.process_pdf(event.src_path)
    
    def on_moved(self, event):
        """파일이 이동되었을 때 호출 (드래그 앤 드롭 등)"""
        if not event.is_directory and event.dest_path.lower().endswith('.pdf'):
            time.sleep(Config.PROCESS_DELAY)
            self.process_pdf(event.dest_path)
    
    def process_pdf(self, file_path):
        """PDF 파일 처리"""
        file_path = Path(file_path)
        
        # 이미 처리 중인 파일인지 확인
        with self.lock:
            if file_path.name in self.processing_files:
                return
            self.processing_files.add(file_path.name)
        
        try:
            print(f"\n{'='*70}")
            print(f"🆕 새 파일 감지: {file_path.name}")
            print(f"시간: {format_datetime()}")
            print(f"프리플라이트: {self.preflight_profile}")
            print(f"{'='*70}")
            
            # 파일이 완전히 복사되었는지 확인 (크기 체크)
            size1 = file_path.stat().st_size
            time.sleep(0.5)
            size2 = file_path.stat().st_size
            
            if size1 != size2:
                print("  ⏳ 파일이 아직 복사 중입니다. 잠시 대기...")
                time.sleep(2)
            
            # PDF 분석 시작
            print("\n📊 PDF 분석을 시작합니다...")
            result = self.analyzer.analyze(
                file_path, 
                include_ink_analysis=True,
                preflight_profile=self.preflight_profile  # Phase 2.5
            )
            
            if 'error' in result:
                print(f"\n❌ 분석 실패: {result['error']}")
                self._move_to_error_folder(file_path, "분석 실패")
                return
            
            # 보고서 생성
            print("\n📝 보고서 생성 중...")
            report_paths = self.report_generator.generate_reports(
                result, 
                format_type=Config.DEFAULT_REPORT_FORMAT
            )
            
            # 프리플라이트 결과 확인 (Phase 2.5)
            preflight_result = result.get('preflight_result', {})
            preflight_status = preflight_result.get('overall_status', 'unknown')
            
            # 결과에 따라 파일 분류
            issues = result.get('issues', [])
            errors = [i for i in issues if i['severity'] == 'error']
            warnings = [i for i in issues if i['severity'] == 'warning']
            
            # 프리플라이트 결과를 우선 고려
            if preflight_status == 'fail' or errors:
                status = "오류"
                dest_folder = Config.OUTPUT_PATH / "오류"
                prefix = f"오류{len(errors)}_"
                emoji = "❌"
            elif preflight_status == 'warning' or warnings:
                status = "경고"
                dest_folder = Config.OUTPUT_PATH / "경고"
                prefix = f"경고{len(warnings)}_"
                emoji = "⚠️"
            else:
                status = "정상"
                dest_folder = Config.OUTPUT_PATH / "정상"
                prefix = "정상_"
                emoji = "✅"
            
            # 대상 폴더 생성
            dest_folder.mkdir(exist_ok=True, parents=True)
            
            # 파일 이동
            dest_path = dest_folder / (prefix + file_path.name)
            shutil.move(str(file_path), str(dest_path))
            
            # 결과 출력
            print(f"\n{emoji} 처리 완료!")
            print(f"  • 상태: {status}")
            print(f"  • 이동 위치: {dest_path.parent.name}/{dest_path.name}")
            
            if 'text' in report_paths:
                print(f"  • 텍스트 보고서: {report_paths['text'].name}")
            if 'html' in report_paths:
                print(f"  • HTML 보고서: {report_paths['html'].name}")
            
            # 프리플라이트 결과 요약 (Phase 2.5)
            if preflight_result:
                print(f"\n  프리플라이트 결과 ({preflight_result.get('profile', 'Unknown')}):")
                print(f"    - 상태: {preflight_status}")
                print(f"    - 통과: {len(preflight_result.get('passed', []))}개")
                print(f"    - 실패: {len(preflight_result.get('failed', []))}개")
                print(f"    - 경고: {len(preflight_result.get('warnings', []))}개")
                
                # 주요 실패 항목
                failed_items = preflight_result.get('failed', [])
                if failed_items:
                    print(f"\n  프리플라이트 실패 항목:")
                    for item in failed_items[:3]:
                        print(f"    ❌ {item['rule_name']}: {item['message']}")
                    if len(failed_items) > 3:
                        print(f"    ... 그 외 {len(failed_items)-3}개")
            
            # 주요 문제점 요약
            if errors:
                print(f"\n  주요 오류:")
                for err in errors[:3]:
                    print(f"    - {err['message']}")
                if len(errors) > 3:
                    print(f"    ... 그 외 {len(errors)-3}개")
            
            if warnings:
                print(f"\n  주요 경고:")
                for warn in warnings[:3]:
                    print(f"    - {warn['message']}")
                if len(warnings) > 3:
                    print(f"    ... 그 외 {len(warnings)-3}개")
            
            # 고급 검사 결과 (Phase 2.5)
            print_quality = result.get('print_quality', {})
            if print_quality:
                # 투명도
                if print_quality.get('transparency', {}).get('has_transparency'):
                    pages_count = len(print_quality['transparency'].get('pages_with_transparency', []))
                    print(f"\n  ⚠️  투명도: {pages_count}개 페이지에서 발견")
                
                # 재단선
                bleed = print_quality.get('bleed', {})
                if not bleed.get('has_proper_bleed', True):
                    pages_count = len(bleed.get('pages_without_bleed', []))
                    print(f"  ❌ 재단선: {pages_count}개 페이지 여백 부족")
                
                # 중복인쇄
                if print_quality.get('overprint', {}).get('has_overprint'):
                    pages_count = len(set(print_quality['overprint'].get('pages_with_overprint', [])))
                    print(f"  ⚠️  중복인쇄: {pages_count}개 페이지에서 설정됨")
            
            # 잉크량 정보 출력
            ink = result.get('ink_coverage', {})
            if 'summary' in ink:
                print(f"\n  잉크량 분석:")
                print(f"    - 평균: {ink['summary']['avg_coverage']:.1f}%")
                print(f"    - 최대: {ink['summary']['max_coverage']:.1f}%")
                if ink['summary']['problem_pages']:
                    print(f"    - 문제 페이지: {len(ink['summary']['problem_pages'])}개")
            
        except Exception as e:
            print(f"\n❌ 처리 중 오류 발생: {e}")
            import traceback
            traceback.print_exc()
            self._move_to_error_folder(file_path, str(e))
        
        finally:
            # 처리 완료 표시
            with self.lock:
                self.processing_files.discard(file_path.name)
            
            print(f"\n{'='*70}")
            print("대기 중... (새 파일을 input 폴더에 넣어주세요)")
    
    def _move_to_error_folder(self, file_path, error_msg):
        """오류 발생 시 파일을 오류 폴더로 이동"""
        try:
            error_folder = Config.OUTPUT_PATH / "오류"
            error_folder.mkdir(exist_ok=True, parents=True)
            
            # 오류 정보를 파일명에 포함
            error_prefix = f"오류_{error_msg[:20].replace(' ', '_')}_"
            dest_path = error_folder / (error_prefix + file_path.name)
            
            if file_path.exists():
                shutil.move(str(file_path), str(dest_path))
                print(f"  → 파일을 오류 폴더로 이동: {dest_path.name}")
        except Exception as e:
            print(f"  ⚠️  파일 이동 실패: {e}")

class PDFMonitor:
    """PDF 폴더 모니터링 관리 클래스"""
    
    def __init__(self, preflight_profile='offset'):
        self.config = Config()
        self.observer = Observer()
        self.handler = PDFHandler(preflight_profile=preflight_profile)  # Phase 2.5
        self.preflight_profile = preflight_profile
    
    def start(self):
        """모니터링 시작"""
        # 입력 폴더 확인
        if not self.config.INPUT_PATH.exists():
            print(f"❌ 입력 폴더가 없습니다: {self.config.INPUT_PATH}")
            return
        
        # 프로파일 확인
        profile = PreflightProfiles.get_profile_by_name(self.preflight_profile)
        if not profile:
            print(f"⚠️  '{self.preflight_profile}' 프로파일을 찾을 수 없습니다. 기본(offset) 사용")
            self.preflight_profile = 'offset'
            profile = PreflightProfiles.get_offset_printing()
        
        # 모니터링 설정
        self.observer.schedule(
            self.handler,
            str(self.config.INPUT_PATH),
            recursive=False  # 하위 폴더는 감시하지 않음
        )
        
        # 모니터링 시작
        self.observer.start()
        
        print(f"\n🔍 PDF 자동 검수 시스템 Phase 2.5")
        print(f"{'='*70}")
        print(f"📂 모니터링 폴더: {self.config.INPUT_PATH}")
        print(f"🎯 프리플라이트: {profile.name}")
        print(f"⚙️  설정:")
        print(f"   • 보고서 형식: {self.config.DEFAULT_REPORT_FORMAT}")
        print(f"   • 잉크량 기준: {self.config.MAX_INK_COVERAGE}%")
        print(f"   • 이미지 해상도 기준: {self.config.MIN_IMAGE_DPI} DPI")
        print(f"   • 재단 여백 기준: {self.config.STANDARD_BLEED_SIZE}mm")
        print(f"   • 투명도 검사: {'활성' if self.config.CHECK_OPTIONS['transparency'] else '비활성'}")
        print(f"   • 중복인쇄 검사: {'활성' if self.config.CHECK_OPTIONS['overprint'] else '비활성'}")
        print(f"{'='*70}")
        print(f"대기 중... (PDF 파일을 '{self.config.INPUT_FOLDER}' 폴더에 넣어주세요)")
        print(f"종료하려면 Ctrl+C를 누르세요\n")
        
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            self.observer.stop()
            print("\n\n👋 프로그램을 종료합니다.")
        
        self.observer.join()
    
    def stop(self):
        """모니터링 중지"""
        self.observer.stop()
        self.observer.join()

def check_existing_files(preflight_profile='offset'):
    """
    프로그램 시작 시 input 폴더에 이미 있는 파일들을 처리
    
    Args:
        preflight_profile: 적용할 프리플라이트 프로파일
    """
    input_path = Config.INPUT_PATH
    if not input_path.exists():
        return
    
    existing_pdfs = list(input_path.glob("*.pdf"))
    if existing_pdfs:
        print(f"\n📌 기존 파일 {len(existing_pdfs)}개 발견")
        response = input("처리하시겠습니까? (y/n): ")
        
        if response.lower() == 'y':
            # 프로파일 선택 옵션
            print(f"\n현재 프로파일: {preflight_profile}")
            change = input("다른 프로파일을 사용하시겠습니까? (y/n): ")
            
            if change.lower() == 'y':
                print("\n사용 가능한 프로파일:")
                for i, profile_name in enumerate(Config.AVAILABLE_PROFILES, 1):
                    print(f"  {i}. {profile_name}")
                
                try:
                    choice = int(input("\n선택 (번호): ")) - 1
                    if 0 <= choice < len(Config.AVAILABLE_PROFILES):
                        preflight_profile = Config.AVAILABLE_PROFILES[choice]
                        print(f"✓ {preflight_profile} 프로파일 선택됨")
                except:
                    print("잘못된 선택입니다. 기본 프로파일 사용")
            
            handler = PDFHandler(preflight_profile=preflight_profile)
            for pdf_file in existing_pdfs:
                print(f"\n처리 중: {pdf_file.name}")
                handler.process_pdf(pdf_file)
            print("\n✅ 기존 파일 처리 완료!")
            time.sleep(2)

if __name__ == "__main__":
    # 필요한 폴더 생성
    Config.create_folders()
    
    # 기본 프로파일 설정
    import sys
    profile = Config.DEFAULT_PREFLIGHT_PROFILE
    
    # 명령줄에서 프로파일 지정 가능
    if len(sys.argv) > 1:
        if sys.argv[1] in Config.AVAILABLE_PROFILES:
            profile = sys.argv[1]
            print(f"프로파일 설정: {profile}")
        else:
            print(f"알 수 없는 프로파일: {sys.argv[1]}")
            print(f"사용 가능: {', '.join(Config.AVAILABLE_PROFILES)}")
            sys.exit(1)
    
    # 기존 파일 처리 옵션
    check_existing_files(preflight_profile=profile)
    
    # 모니터링 시작
    monitor = PDFMonitor(preflight_profile=profile)
    monitor.start()
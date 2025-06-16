# batch_processor.py - 일괄 처리 엔진
# 여러 PDF 파일을 동시에 처리하는 멀티스레드 엔진
# 2025.01 추가: 자동 수정 기능 통합
# 2025.01 추가: 데이터 매니저와 알림 시스템 통합

"""
batch_processor.py - PDF 일괄 처리 엔진
멀티스레딩을 사용한 효율적인 다중 파일 처리
UserFriendlyErrorHandler 호출 방식 수정
자동 수정 기능 통합
데이터 매니저와 알림 시스템 통합
"""

import threading
import queue
import time
from pathlib import Path
from datetime import datetime, timedelta
import concurrent.futures
import json

# 프로젝트 모듈
from pdf_analyzer import PDFAnalyzer
from report_generator import ReportGenerator
from error_handler import UserFriendlyErrorHandler
from simple_logger import SimpleLogger
from config import Config

# 새로 추가된 모듈들 (선택적 import)
try:
    from data_manager import DataManager
    HAS_DATA_MANAGER = True
except ImportError:
    HAS_DATA_MANAGER = False
    print("참고: data_manager 모듈을 찾을 수 없습니다. 데이터 저장 기능이 비활성화됩니다.")

try:
    from notification_manager import get_notification_manager
    HAS_NOTIFICATION = True
except ImportError:
    HAS_NOTIFICATION = False
    print("참고: notification_manager 모듈을 찾을 수 없습니다. 알림 기능이 비활성화됩니다.")

# 자동 수정 모듈
try:
    from pdf_fixer import PDFFixer
    HAS_AUTO_FIX = True
except ImportError:
    HAS_AUTO_FIX = False
    print("경고: pdf_fixer 모듈을 찾을 수 없습니다. 자동 수정 기능이 비활성화됩니다.")

class BatchProcessor:
    """PDF 일괄 처리 클래스"""
    
    def __init__(self, file_dict, file_queue, result_queue, progress_callback=None):
        """
        일괄 처리기 초기화
        
        Args:
            file_dict: 파일 정보 딕셔너리 {file_id: {'path': ..., 'status': ...}}
            file_queue: 처리할 파일 큐
            result_queue: 결과 큐
            progress_callback: 진행률 업데이트 콜백 함수
        """
        self.file_dict = file_dict
        self.file_queue = file_queue
        self.result_queue = result_queue
        self.progress_callback = progress_callback
        
        # 처리 설정
        self.max_workers = 3  # 동시 처리 스레드 수
        self.is_running = False
        self.is_paused = False
        self.workers = []
        
        # 통계
        self.start_time = None
        self.processed_count = 0
        self.error_count = 0
        self.total_processing_time = 0
        
        # 로거와 오류 처리기
        self.logger = SimpleLogger()
        self.error_handler = UserFriendlyErrorHandler(self.logger)
        
        # 스레드 풀
        self.executor = None
        
        # 자동 수정 설정 로드
        self.auto_fix_settings = self._load_user_settings()
        
        # 데이터 매니저 (있는 경우)
        self.data_manager = DataManager() if HAS_DATA_MANAGER else None
        
        # 알림 매니저 (있는 경우)
        self.notification_manager = get_notification_manager() if HAS_NOTIFICATION else None
    
    def _load_user_settings(self):
        """
        사용자 설정 파일 로드
        
        Returns:
            dict: 사용자 설정 (없으면 기본값)
        """
        settings_file = Path("user_settings.json")
        
        if settings_file.exists():
            try:
                with open(settings_file, 'r', encoding='utf-8') as f:
                    settings = json.load(f)
                    self.logger.log("사용자 설정 파일 로드됨")
                    return settings
            except Exception as e:
                self.logger.error(f"설정 파일 로드 실패: {e}")
        
        # 기본 설정값 반환
        return {
            'auto_convert_rgb': False,
            'auto_outline_fonts': False,
            'warn_small_text': True,
            'always_backup': True,
            'create_comparison_report': True,
            'enable_notifications': False  # 알림 기본값
        }
    
    def _needs_auto_fix(self, analysis_result):
        """
        자동 수정이 필요한지 확인
        
        Args:
            analysis_result: PDF 분석 결과
            
        Returns:
            bool: 자동 수정 필요 여부
        """
        if not HAS_AUTO_FIX:
            return False
        
        # RGB→CMYK 변환 필요 확인
        if self.auto_fix_settings.get('auto_convert_rgb', False):
            colors = analysis_result.get('colors', {})
            if colors.get('has_rgb') and not colors.get('has_cmyk'):
                return True
        
        # 폰트 아웃라인 변환 필요 확인
        if self.auto_fix_settings.get('auto_outline_fonts', False):
            fonts = analysis_result.get('fonts', {})
            not_embedded = sum(1 for f in fonts.values() if not f.get('embedded', False))
            if not_embedded > 0:
                return True
        
        return False
    
    def process_all(self):
        """모든 파일 처리 시작"""
        self.is_running = True
        self.start_time = datetime.now()
        
        self.logger.log(f"일괄 처리 시작 - 총 {len(self.file_dict)}개 파일")
        
        # 자동 수정 설정 로그
        if any(self.auto_fix_settings.get(key, False) for key in ['auto_convert_rgb', 'auto_outline_fonts']):
            self.logger.log("자동 수정 기능 활성화됨")
            if self.auto_fix_settings.get('auto_convert_rgb'):
                self.logger.log("  - RGB→CMYK 자동 변환")
            if self.auto_fix_settings.get('auto_outline_fonts'):
                self.logger.log("  - 폰트 아웃라인 변환")
        
        # 알림 설정 확인
        if self.notification_manager and self.auto_fix_settings.get('enable_notifications'):
            self.logger.log("Windows 알림 활성화됨")
        
        # 파일 큐에 추가
        for file_id, file_info in self.file_dict.items():
            if file_info['status'] == 'waiting':
                self.file_queue.put((file_id, file_info))
        
        # 스레드 풀 생성
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            self.executor = executor
            
            # 워커 스레드 시작
            futures = []
            for i in range(self.max_workers):
                future = executor.submit(self._worker_thread, i)
                futures.append(future)
            
            # 모든 워커 완료 대기
            concurrent.futures.wait(futures)
        
        self.is_running = False
        self._complete_processing()
    
    def _worker_thread(self, worker_id):
        """워커 스레드"""
        self.logger.log(f"워커 {worker_id} 시작")
        
        while self.is_running:
            # 일시정지 확인
            while self.is_paused and self.is_running:
                time.sleep(0.1)
            
            try:
                # 큐에서 파일 가져오기
                file_id, file_info = self.file_queue.get(timeout=1)
                
                # 처리
                self._process_single_file(file_id, file_info, worker_id)
                
                # 큐 작업 완료 표시
                self.file_queue.task_done()
                
            except queue.Empty:
                # 큐가 비었으면 종료
                if self.file_queue.empty():
                    break
            except Exception as e:
                self.logger.log(f"워커 {worker_id} 오류: {str(e)}")
        
        self.logger.log(f"워커 {worker_id} 종료")
    
    def _process_single_file(self, file_id, file_info, worker_id):
        """단일 파일 처리 - 자동 수정 기능 포함"""
        file_path = Path(file_info['path'])
        
        try:
            # 처리 시작
            self.logger.log(f"[워커 {worker_id}] 처리 시작: {file_path.name}")
            start_time = time.time()
            
            # 진행률 업데이트: 처리 중
            if self.progress_callback:
                self.progress_callback(file_id, 'processing', 10, "분석 시작")
            
            # PDF 분석
            analyzer = PDFAnalyzer()
            
            # 단계별 진행률 업데이트를 위한 래퍼
            def update_progress(step, percent):
                if self.progress_callback:
                    self.progress_callback(file_id, 'processing', percent, step)
            
            # 기본 분석 (10% → 40%)
            update_progress("기본 정보 분석", 20)
            
            # 잉크량 분석 포함 여부 확인
            include_ink = getattr(Config, 'DEFAULT_INK_ANALYSIS', True)
            
            result = analyzer.analyze(
                file_path,
                include_ink_analysis=include_ink,
                preflight_profile=Config.DEFAULT_PREFLIGHT_PROFILE
            )
            
            if 'error' in result:
                raise Exception(result['error'])
            
            update_progress("분석 완료", 40)
            
            # 자동 수정 처리 (40% → 60%)
            fixed_file_path = None
            auto_fix_applied = []
            
            if self._needs_auto_fix(result):
                update_progress("자동 수정 확인", 45)
                
                if HAS_AUTO_FIX:
                    try:
                        self.logger.log(f"[워커 {worker_id}] 자동 수정 시작")
                        update_progress("문제 자동 수정 중", 50)
                        
                        # PDF 수정기 생성
                        fixer = PDFFixer(settings=self.auto_fix_settings)
                        
                        # 수정 수행
                        fix_result = fixer.fix_pdf(file_path, result)
                        
                        if fix_result['fixed']:
                            fixed_file_path = Path(fix_result['fixed'])
                            auto_fix_applied = fix_result['modifications']
                            
                            self.logger.log(f"[워커 {worker_id}] 자동 수정 완료: {', '.join(auto_fix_applied)}")
                            
                            # 수정된 파일 재분석 (선택사항)
                            if self.auto_fix_settings.get('create_comparison_report', True):
                                update_progress("수정 결과 확인", 55)
                                
                                # 수정된 파일 재분석
                                result_after = analyzer.analyze(
                                    fixed_file_path,
                                    include_ink_analysis=False,  # 빠른 검사
                                    preflight_profile=Config.DEFAULT_PREFLIGHT_PROFILE
                                )
                                
                                # 비교 데이터 추가
                                result['fix_comparison'] = {
                                    'before': {
                                        'fonts': result.get('fonts', {}),
                                        'colors': result.get('colors', {}),
                                        'issues': result.get('issues', [])
                                    },
                                    'after': {
                                        'fonts': result_after.get('fonts', {}),
                                        'colors': result_after.get('colors', {}),
                                        'issues': result_after.get('issues', [])
                                    },
                                    'modifications': auto_fix_applied
                                }
                            
                            # 결과에 수정 정보 추가
                            result['auto_fix_applied'] = auto_fix_applied
                            result['fixed_file_path'] = str(fixed_file_path)
                            
                            # 원본 파일 경로를 수정된 파일로 변경 (보고서 생성용)
                            # 주의: 원본 경로는 별도로 보존
                            result['original_file_path'] = str(file_path)
                            result['file_path'] = str(fixed_file_path)
                            
                    except Exception as e:
                        self.logger.error(f"[워커 {worker_id}] 자동 수정 실패: {str(e)}")
                        # 자동 수정 실패해도 계속 진행
            
            update_progress("보고서 생성 준비", 60)
            
            # 데이터베이스에 저장 (60% → 70%)
            if self.data_manager:
                try:
                    update_progress("데이터 저장", 65)
                    self.data_manager.save_analysis_result(result)
                except Exception as e:
                    self.logger.error(f"데이터 저장 실패: {e}")
            
            # 보고서 생성 (70% → 90%)
            update_progress("보고서 생성", 75)
            report_generator = ReportGenerator()
            
            # 보고서 생성 시 수정 정보 포함
            report_paths = report_generator.generate_reports(
                result,
                format_type=Config.DEFAULT_REPORT_FORMAT
            )
            
            update_progress("보고서 저장", 90)
            
            # 처리 시간 계산
            processing_time = time.time() - start_time
            self.total_processing_time += processing_time
            
            # 완료
            update_progress("완료", 100)
            
            # 알림 발송
            if self.notification_manager and self.auto_fix_settings.get('enable_notifications'):
                issues = result.get('issues', [])
                self.notification_manager.notify_success(
                    file_path.name,
                    len(issues),
                    page_count=result['basic_info']['page_count'],
                    processing_time=processing_time
                )
                
                # 자동 수정 알림
                if auto_fix_applied:
                    self.notification_manager.notify_auto_fix(file_path.name, auto_fix_applied)
            
            # 결과 저장
            complete_result = {
                'type': 'complete',
                'file_id': file_id,
                'file': file_path.name,
                'result': result,
                'reports': report_paths,
                'processing_time': processing_time,
                'worker_id': worker_id,
                'pages': result['basic_info']['page_count']
            }
            
            # 자동 수정 정보 추가
            if auto_fix_applied:
                complete_result['auto_fix_applied'] = auto_fix_applied
                complete_result['fixed_file'] = fixed_file_path.name if fixed_file_path else None
            
            self.result_queue.put(complete_result)
            
            # 통계 업데이트
            self.processed_count += 1
            
            # 상태 업데이트
            if self.progress_callback:
                self.progress_callback(
                    file_id, 
                    'complete', 
                    100, 
                    {'pages': result['basic_info']['page_count']}
                )
            
            log_message = f"[워커 {worker_id}] 처리 완료: {file_path.name} ({processing_time:.1f}초)"
            if auto_fix_applied:
                log_message += f" - 자동 수정: {', '.join(auto_fix_applied)}"
            self.logger.log(log_message)
            
        except Exception as e:
            # 오류 처리
            error_info = self.error_handler.handle_error(
                e,
                f"파일 처리 중: {file_path.name}"
            )
            
            # 사용자 친화적 메시지 가져오기
            error_message = self.error_handler.get_user_message(error_info)
            
            # 오류 카운트
            self.error_count += 1
            
            # 알림 발송
            if self.notification_manager and self.auto_fix_settings.get('enable_notifications'):
                self.notification_manager.notify_error(file_path.name, error_message)
            
            # 결과 큐에 오류 추가
            self.result_queue.put({
                'type': 'error',
                'file_id': file_id,
                'file': file_path.name,
                'error': error_message,
                'error_details': error_info,
                'worker_id': worker_id
            })
            
            # 상태 업데이트
            if self.progress_callback:
                self.progress_callback(file_id, 'error', 100, error_message)
            
            self.logger.error(
                f"[워커 {worker_id}] 처리 실패: {file_path.name} - {str(e)}",
                file_path.name,
                e
            )
    
    def pause(self):
        """일시정지"""
        self.is_paused = True
        self.logger.log("일괄 처리 일시정지")
    
    def resume(self):
        """재개"""
        self.is_paused = False
        self.logger.log("일괄 처리 재개")
    
    def stop(self):
        """중지"""
        self.is_running = False
        self.is_paused = False
        
        # 큐 비우기
        while not self.file_queue.empty():
            try:
                self.file_queue.get_nowait()
            except:
                break
        
        self.logger.log("일괄 처리 중지됨")
    
    def _complete_processing(self):
        """처리 완료"""
        # 처리 시간 계산
        if self.start_time:
            total_time = (datetime.now() - self.start_time).total_seconds()
        else:
            total_time = 0
        
        # 자동 수정 통계
        auto_fixed_count = sum(
            1 for f in self.file_dict.values() 
            if f.get('auto_fix_applied')
        )
        
        # 알림 발송
        if self.notification_manager and self.auto_fix_settings.get('enable_notifications'):
            self.notification_manager.notify_batch_complete(
                len(self.file_dict),
                self.processed_count,
                self.error_count,
                total_time,
                auto_fixed_count
            )
        
        # 완료 메시지
        self.result_queue.put({
            'type': 'batch_complete',
            'summary': {
                'total_files': len(self.file_dict),
                'processed': self.processed_count,
                'errors': self.error_count,
                'auto_fixed': auto_fixed_count,
                'total_time': total_time,
                'avg_time': self.total_processing_time / max(self.processed_count, 1)
            }
        })
        
        log_message = (
            f"일괄 처리 완료 - "
            f"성공: {self.processed_count}, "
            f"실패: {self.error_count}, "
        )
        if auto_fixed_count > 0:
            log_message += f"자동 수정: {auto_fixed_count}, "
        log_message += f"총 시간: {total_time:.1f}초"
        
        self.logger.log(log_message)
    
    def get_estimated_time(self):
        """예상 남은 시간 계산"""
        if self.processed_count == 0:
            return None
        
        # 평균 처리 시간
        avg_time = self.total_processing_time / self.processed_count
        
        # 남은 파일 수
        remaining = sum(
            1 for f in self.file_dict.values() 
            if f['status'] in ['waiting', 'processing']
        )
        
        # 예상 시간
        estimated_seconds = remaining * avg_time / self.max_workers
        
        return timedelta(seconds=int(estimated_seconds))
    
    def get_statistics(self):
        """처리 통계"""
        total = len(self.file_dict)
        completed = sum(1 for f in self.file_dict.values() if f['status'] == 'complete')
        errors = sum(1 for f in self.file_dict.values() if f['status'] == 'error')
        processing = sum(1 for f in self.file_dict.values() if f['status'] == 'processing')
        waiting = sum(1 for f in self.file_dict.values() if f['status'] == 'waiting')
        auto_fixed = sum(1 for f in self.file_dict.values() if f.get('auto_fix_applied'))
        
        return {
            'total': total,
            'completed': completed,
            'errors': errors,
            'processing': processing,
            'waiting': waiting,
            'auto_fixed': auto_fixed,
            'progress_percent': (completed / total * 100) if total > 0 else 0,
            'estimated_time': self.get_estimated_time()
        }


# 처리 우선순위 관리
class ProcessingPriority:
    """파일 처리 우선순위 관리"""
    
    @staticmethod
    def sort_by_size_asc(file_list):
        """파일 크기 오름차순 (작은 파일 먼저)"""
        return sorted(file_list, key=lambda x: Path(x[1]['path']).stat().st_size)
    
    @staticmethod
    def sort_by_size_desc(file_list):
        """파일 크기 내림차순 (큰 파일 먼저)"""
        return sorted(
            file_list, 
            key=lambda x: Path(x[1]['path']).stat().st_size, 
            reverse=True
        )
    
    @staticmethod
    def sort_by_name(file_list):
        """파일명 순"""
        return sorted(file_list, key=lambda x: Path(x[1]['path']).name)
    
    @staticmethod
    def sort_by_modified(file_list):
        """수정 시간 순"""
        return sorted(
            file_list, 
            key=lambda x: Path(x[1]['path']).stat().st_mtime
        )


# 사용 예시
if __name__ == "__main__":
    # 테스트용 파일 목록
    test_files = {
        'file1': {'path': 'sample1.pdf', 'status': 'waiting'},
        'file2': {'path': 'sample2.pdf', 'status': 'waiting'},
        'file3': {'path': 'sample3.pdf', 'status': 'waiting'},
    }
    
    # 큐 생성
    file_queue = queue.Queue()
    result_queue = queue.Queue()
    
    # 진행률 콜백
    def progress_callback(file_id, status, progress, message):
        print(f"{file_id}: {status} - {progress}% - {message}")
    
    # 배치 프로세서 생성
    processor = BatchProcessor(
        test_files,
        file_queue,
        result_queue,
        progress_callback
    )
    
    # 처리 시작 (실제로는 별도 스레드에서 실행)
    import threading
    process_thread = threading.Thread(target=processor.process_all)
    process_thread.start()
    
    # 결과 확인
    while True:
        try:
            result = result_queue.get(timeout=1)
            print(f"결과: {result}")
            
            if result['type'] == 'batch_complete':
                break
                
        except queue.Empty:
            # 통계 출력
            stats = processor.get_statistics()
            print(f"진행 상황: {stats}")
            time.sleep(1)
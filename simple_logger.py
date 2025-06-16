# simple_logger.py - 간단한 로그 시스템
# 초보자도 이해하기 쉬운 로그 기록 시스템

"""
simple_logger.py - 간단한 로그 시스템
PDF 검수 과정을 기록하고 오류를 추적합니다
"""

import os
import json
from datetime import datetime
from pathlib import Path
import traceback

class SimpleLogger:
    """간단한 로그 클래스"""
    
    def __init__(self):
        """로거 초기화"""
        # 로그 폴더 생성
        self.log_dir = Path("logs")
        self.log_dir.mkdir(exist_ok=True)
        
        # 오늘 날짜로 로그 파일 생성
        today = datetime.now().strftime("%Y%m%d")
        self.log_file = self.log_dir / f"pdf_checker_{today}.log"
        self.error_file = self.log_dir / f"errors_{today}.log"
        
        # 세션 정보
        self.session_start = datetime.now()
        self.session_id = self.session_start.strftime("%Y%m%d_%H%M%S")
        
        # 통계 정보
        self.stats = {
            'total_files': 0,
            'success_files': 0,
            'error_files': 0,
            'warnings_count': 0,
            'start_time': self.session_start.isoformat(),
            'errors': []
        }
        
        # 시작 로그
        self.info("="*70)
        self.info(f"PDF 검수 시스템 시작 - 세션 ID: {self.session_id}")
        self.info("="*70)
    
    def _write_log(self, level, message, file_path=None):
        """로그 파일에 기록"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # 로그 형식
        log_entry = f"{timestamp} | {level:8} | {message}"
        
        # 파일 경로가 있으면 추가
        if file_path:
            log_entry = f"{timestamp} | {level:8} | [{file_path}] {message}"
        
        # 콘솔 출력 (색상 있음)
        if level == "ERROR":
            print(f"❌ {log_entry}")
        elif level == "WARNING":
            print(f"⚠️  {log_entry}")
        elif level == "SUCCESS":
            print(f"✅ {log_entry}")
        elif level == "INFO":
            print(f"ℹ️  {log_entry}")
        else:
            print(f"   {log_entry}")
        
        # 파일에 기록
        try:
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(log_entry + '\n')
            
            # 에러는 별도 파일에도 기록
            if level == "ERROR":
                with open(self.error_file, 'a', encoding='utf-8') as f:
                    f.write(log_entry + '\n')
        except Exception as e:
            print(f"⚠️  로그 기록 실패: {e}")
    
    def log(self, message, file_path=None):
        """일반 로그 (info와 동일) - GUI 호환성을 위해 추가"""
        self.info(message, file_path)
    
    def info(self, message, file_path=None):
        """정보 로그"""
        self._write_log("INFO", message, file_path)
    
    def success(self, message, file_path=None):
        """성공 로그"""
        self._write_log("SUCCESS", message, file_path)
        self.stats['success_files'] += 1
    
    def warning(self, message, file_path=None):
        """경고 로그"""
        self._write_log("WARNING", message, file_path)
        self.stats['warnings_count'] += 1
    
    def error(self, message, file_path=None, exception=None):
        """에러 로그"""
        self._write_log("ERROR", message, file_path)
        self.stats['error_files'] += 1
        
        # 예외 정보가 있으면 추가
        if exception:
            error_detail = {
                'timestamp': datetime.now().isoformat(),
                'file': str(file_path) if file_path else None,
                'message': message,
                'error_type': type(exception).__name__,
                'error_message': str(exception),
                'traceback': traceback.format_exc()
            }
            self.stats['errors'].append(error_detail)
            
            # 상세 스택 트레이스도 로그에 기록
            self._write_log("ERROR", f"상세 오류: {type(exception).__name__}: {str(exception)}")
            for line in traceback.format_exc().split('\n'):
                if line.strip():
                    self._write_log("ERROR", f"  {line}")
    
    def debug(self, message, file_path=None):
        """디버그 로그 (상세 정보)"""
        self._write_log("DEBUG", message, file_path)
    
    def start_file(self, file_path, file_size=None):
        """파일 처리 시작 로그"""
        self.stats['total_files'] += 1
        self.info(f"파일 처리 시작: {Path(file_path).name}", file_path)
        if file_size:
            self.info(f"파일 크기: {self._format_size(file_size)}", file_path)
    
    def end_file(self, file_path, success=True, processing_time=None):
        """파일 처리 완료 로그"""
        if success:
            msg = "파일 처리 완료"
            if processing_time:
                msg += f" (소요시간: {processing_time:.1f}초)"
            self.success(msg, file_path)
        else:
            self.error("파일 처리 실패", file_path)
    
    def log_step(self, step_name, details=None):
        """처리 단계 로그"""
        msg = f"처리 단계: {step_name}"
        if details:
            msg += f" - {details}"
        self.debug(msg)
    
    def _format_size(self, size_bytes):
        """파일 크기를 읽기 쉬운 형식으로 변환"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f} TB"
    
    def create_summary(self):
        """세션 요약 생성"""
        end_time = datetime.now()
        duration = (end_time - self.session_start).total_seconds()
        
        summary = f"""
{'='*70}
PDF 검수 세션 요약
{'='*70}
세션 ID: {self.session_id}
시작 시간: {self.session_start.strftime('%Y-%m-%d %H:%M:%S')}
종료 시간: {end_time.strftime('%Y-%m-%d %H:%M:%S')}
소요 시간: {duration:.1f}초 ({duration/60:.1f}분)

처리 결과:
- 전체 파일: {self.stats['total_files']}개
- 성공: {self.stats['success_files']}개
- 실패: {self.stats['error_files']}개
- 경고: {self.stats['warnings_count']}건

성공률: {self._calculate_success_rate():.1f}%
{'='*70}
"""
        return summary
    
    def _calculate_success_rate(self):
        """성공률 계산"""
        if self.stats['total_files'] == 0:
            return 0
        return (self.stats['success_files'] / self.stats['total_files']) * 100
    
    def save_session_stats(self):
        """세션 통계를 JSON으로 저장"""
        stats_file = self.log_dir / f"session_{self.session_id}.json"
        
        # 종료 시간 추가
        self.stats['end_time'] = datetime.now().isoformat()
        self.stats['duration_seconds'] = (datetime.now() - self.session_start).total_seconds()
        
        try:
            with open(stats_file, 'w', encoding='utf-8') as f:
                json.dump(self.stats, f, ensure_ascii=False, indent=2)
            self.info(f"세션 통계 저장: {stats_file.name}")
        except Exception as e:
            self.error(f"통계 저장 실패: {e}")
    
    def cleanup_old_logs(self, days_to_keep=30):
        """오래된 로그 파일 정리"""
        try:
            cutoff_date = datetime.now().timestamp() - (days_to_keep * 24 * 60 * 60)
            
            cleaned = 0
            for log_file in self.log_dir.glob("*.log"):
                if log_file.stat().st_mtime < cutoff_date:
                    log_file.unlink()
                    cleaned += 1
            
            if cleaned > 0:
                self.info(f"{cleaned}개의 오래된 로그 파일을 삭제했습니다")
        except Exception as e:
            self.warning(f"로그 정리 중 오류: {e}")
    
    def get_recent_errors(self, count=10):
        """최근 에러 목록 반환"""
        return self.stats['errors'][-count:]
    
    def get_log_file(self):
        """현재 로그 파일 경로 반환"""
        return self.log_file
    
    def close(self):
        """로거 종료"""
        # 세션 요약 기록
        summary = self.create_summary()
        for line in summary.split('\n'):
            if line.strip():
                self.info(line)
        
        # 통계 저장
        self.save_session_stats()
        
        # 오래된 로그 정리
        self.cleanup_old_logs()
        
        self.info("PDF 검수 시스템 종료")
        self.info("="*70)

# 사용자 친화적 에러 핸들러와 통합
class UserFriendlyErrorHandler:
    """사용자 친화적인 오류 메시지 처리"""
    
    ERROR_MESSAGES = {
        'FileNotFoundError': {
            'message': '📁 PDF 파일을 찾을 수 없습니다.',
            'solution': '파일이 이동되었거나 삭제되었는지 확인해주세요.',
            'log_level': 'ERROR'
        },
        'PermissionError': {
            'message': '🔒 파일에 접근할 수 없습니다.',
            'solution': '다른 프로그램에서 파일을 사용 중인지 확인하고, 폴더 권한을 확인해주세요.',
            'log_level': 'ERROR'
        },
        'pikepdf._qpdf.PdfError': {
            'message': '📄 PDF 파일을 열 수 없습니다.',
            'solution': '파일이 손상되었거나 암호로 보호되어 있을 수 있습니다.',
            'log_level': 'ERROR'
        },
        'MemoryError': {
            'message': '💾 메모리가 부족합니다.',
            'solution': '다른 프로그램을 종료하거나, 더 작은 PDF 파일로 시도해주세요.',
            'log_level': 'ERROR'
        },
        'KeyError': {
            'message': '📊 PDF 구조 분석 중 문제가 발생했습니다.',
            'solution': 'PDF 파일이 표준 형식이 아닐 수 있습니다. 다시 저장 후 시도해주세요.',
            'log_level': 'WARNING'
        },
        'ValueError': {
            'message': '📐 데이터 처리 중 문제가 발생했습니다.',
            'solution': 'PDF 파일의 일부 정보가 올바르지 않을 수 있습니다.',
            'log_level': 'WARNING'
        }
    }
    
    @classmethod
    def handle_error(cls, error, logger, file_path=None):
        """에러를 사용자 친화적으로 처리"""
        error_type = type(error).__name__
        error_info = cls.ERROR_MESSAGES.get(error_type, {
            'message': '예상치 못한 오류가 발생했습니다.',
            'solution': '프로그램을 다시 시작하거나 개발자에게 문의해주세요.',
            'log_level': 'ERROR'
        })
        
        # 사용자 메시지 생성
        user_message = f"{error_info['message']}\n해결 방법: {error_info['solution']}"
        
        # 로그 기록
        if error_info['log_level'] == 'ERROR':
            logger.error(user_message, file_path, error)
        else:
            logger.warning(user_message, file_path)
        
        return user_message

# 전역 로거 인스턴스 (싱글톤 패턴)
_logger_instance = None

def get_logger():
    """로거 인스턴스 반환"""
    global _logger_instance
    if _logger_instance is None:
        _logger_instance = SimpleLogger()
    return _logger_instance

# 사용 예시
if __name__ == "__main__":
    # 로거 생성
    logger = get_logger()
    
    # 파일 처리 시뮬레이션
    test_file = "sample.pdf"
    
    try:
        logger.start_file(test_file, 1024*1024*50)  # 50MB
        
        logger.log_step("기본 정보 분석")
        logger.log_step("페이지 분석", "48페이지")
        logger.log_step("폰트 검사", "12개 폰트 발견")
        
        logger.warning("폰트 'Arial-Bold'가 임베딩되지 않았습니다", test_file)
        
        logger.log_step("잉크량 계산", "평균 245%")
        
        # 에러 시뮬레이션
        # raise FileNotFoundError("파일을 찾을 수 없습니다")
        
        logger.end_file(test_file, success=True, processing_time=45.3)
        
    except Exception as e:
        # 사용자 친화적 에러 처리
        UserFriendlyErrorHandler.handle_error(e, logger, test_file)
        logger.end_file(test_file, success=False)
    
    finally:
        # 로거 종료
        logger.close()
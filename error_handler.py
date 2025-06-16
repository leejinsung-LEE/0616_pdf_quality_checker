# error_handler.py - 사용자 친화적 오류 처리
# 기술적인 오류 메시지를 일반인이 이해할 수 있는 메시지로 변환

"""
error_handler.py - 사용자 친화적 오류 메시지 시스템
초보자도 이해할 수 있는 한글 오류 메시지 제공
"""

import traceback
from datetime import datetime
from pathlib import Path

class UserFriendlyErrorHandler:
    """사용자 친화적인 오류 메시지 처리"""
    
    # 오류 타입별 메시지 정의
    ERROR_MESSAGES = {
        # 파일 관련 오류
        'FileNotFoundError': {
            'message': '📁 PDF 파일을 찾을 수 없습니다.',
            'solution': '• 파일이 이동되었거나 삭제되었는지 확인해주세요.\n• 파일명에 특수문자가 있다면 제거해보세요.',
            'icon': '❓'
        },
        'PermissionError': {
            'message': '🔒 파일에 접근할 수 없습니다.',
            'solution': '• 다른 프로그램에서 파일을 사용 중인지 확인해주세요.\n• 파일이 읽기 전용인지 확인해주세요.\n• 관리자 권한으로 실행해보세요.',
            'icon': '🚫'
        },
        'OSError': {
            'message': '💾 시스템 오류가 발생했습니다.',
            'solution': '• 디스크 공간이 충분한지 확인해주세요.\n• 파일 경로가 너무 길지 않은지 확인해주세요.',
            'icon': '⚠️'
        },
        
        # PDF 관련 오류
        'PdfError': {
            'message': '📄 PDF 파일을 열 수 없습니다.',
            'solution': '• 파일이 손상되었을 수 있습니다.\n• 암호로 보호된 파일인지 확인해주세요.\n• 다른 PDF 뷰어로 열리는지 확인해주세요.',
            'icon': '⚠️'
        },
        'PdfReadError': {
            'message': '📖 PDF 파일을 읽을 수 없습니다.',
            'solution': '• PDF 파일이 완전히 다운로드되었는지 확인해주세요.\n• 파일이 손상되지 않았는지 확인해주세요.',
            'icon': '❌'
        },
        
        # 메모리 관련 오류
        'MemoryError': {
            'message': '💾 메모리가 부족합니다.',
            'solution': '• 다른 프로그램을 종료해주세요.\n• 더 작은 PDF 파일로 시도해주세요.\n• 컴퓨터를 재시작해보세요.',
            'icon': '📈'
        },
        
        # 타입 관련 오류
        'TypeError': {
            'message': '🔧 내부 처리 오류가 발생했습니다.',
            'solution': '• 프로그램을 다시 시작해주세요.\n• 문제가 계속되면 개발자에게 문의해주세요.',
            'icon': '🐛'
        },
        'ValueError': {
            'message': '📊 데이터 처리 중 오류가 발생했습니다.',
            'solution': '• PDF 파일 형식이 올바른지 확인해주세요.\n• 다른 방법으로 PDF를 생성해보세요.',
            'icon': '❗'
        },
        
        # 네트워크 관련 (향후 온라인 기능용)
        'ConnectionError': {
            'message': '🌐 네트워크 연결 오류',
            'solution': '• 인터넷 연결을 확인해주세요.\n• 방화벽 설정을 확인해주세요.',
            'icon': '📡'
        },
        
        # 기타
        'KeyboardInterrupt': {
            'message': '⏹️ 사용자가 작업을 중단했습니다.',
            'solution': '• 정상적인 중단입니다.',
            'icon': '✋'
        }
    }
    
    # 특정 오류 메시지에 대한 처리
    SPECIFIC_MESSAGES = {
        "object of type 'int' has no len()": {
            'message': '📊 보고서 생성 중 내부 오류가 발생했습니다.',
            'solution': '• 이 문제는 프로그램 업데이트로 해결되었습니다.\n• 프로그램을 다시 시작해주세요.',
            'icon': '🐛',
            'error_code': 'REPORT_001'
        },
        "No such file or directory": {
            'message': '📁 파일이나 폴더를 찾을 수 없습니다.',
            'solution': '• 파일 경로를 확인해주세요.\n• 한글이나 특수문자가 포함된 경로는 문제가 될 수 있습니다.',
            'icon': '❓',
            'error_code': 'FILE_001'
        },
        "Permission denied": {
            'message': '🔒 파일 접근 권한이 없습니다.',
            'solution': '• 파일이 다른 프로그램에서 열려있는지 확인해주세요.\n• 읽기 전용 파일인지 확인해주세요.',
            'icon': '🚫',
            'error_code': 'PERM_001'
        },
        "cannot identify image file": {
            'message': '🖼️ 이미지 파일을 인식할 수 없습니다.',
            'solution': '• PDF 내의 이미지가 손상되었을 수 있습니다.\n• 다시 PDF를 생성해보세요.',
            'icon': '🖼️',
            'error_code': 'IMG_001'
        }
    }
    
    def __init__(self, logger=None):
        """
        오류 처리기 초기화
        
        Args:
            logger: 로거 인스턴스 (선택사항)
        """
        self.logger = logger
        self.error_log = []
        
    def handle_error(self, error, context=None):
        """
        오류를 사용자 친화적 메시지로 변환
        
        Args:
            error: 발생한 예외 객체
            context: 오류 발생 상황 설명 (선택사항)
            
        Returns:
            dict: 사용자 친화적 오류 정보
        """
        error_type = type(error).__name__
        error_str = str(error)
        
        # 기본 오류 정보
        error_info = {
            'timestamp': datetime.now(),
            'type': error_type,
            'original_message': error_str,
            'context': context,
            'traceback': traceback.format_exc()
        }
        
        # 알려진 오류 타입인지 확인
        if error_type in self.ERROR_MESSAGES:
            user_error = self.ERROR_MESSAGES[error_type].copy()
        else:
            # 특정 오류 메시지 확인
            user_error = None
            for msg_pattern, msg_info in self.SPECIFIC_MESSAGES.items():
                if msg_pattern in error_str:
                    user_error = msg_info.copy()
                    break
            
            if not user_error:
                # 기본 오류 메시지
                user_error = {
                    'message': '😥 예상치 못한 오류가 발생했습니다.',
                    'solution': '• 프로그램을 다시 시작해주세요.\n• 문제가 계속되면 오류 보고서를 전송해주세요.',
                    'icon': '❌',
                    'error_code': 'UNKNOWN_001'
                }
        
        # 컨텍스트 추가
        if context:
            user_error['context'] = context
        
        # 오류 코드 생성
        if 'error_code' not in user_error:
            user_error['error_code'] = f"{error_type[:3].upper()}_{hash(error_str) % 1000:03d}"
        
        # 전체 오류 정보
        error_info.update(user_error)
        
        # 로그에 추가
        self.error_log.append(error_info)
        
        # 로거가 있으면 로그 기록
        if self.logger:
            self.logger.log(f"오류 발생: {user_error['message']} (코드: {user_error['error_code']})")
        
        return error_info
    
    def get_user_message(self, error_info):
        """
        사용자에게 표시할 메시지 포맷팅
        
        Args:
            error_info: handle_error가 반환한 오류 정보
            
        Returns:
            str: 포맷팅된 사용자 메시지
        """
        icon = error_info.get('icon', '❌')
        message = error_info.get('message', '오류가 발생했습니다.')
        solution = error_info.get('solution', '')
        error_code = error_info.get('error_code', 'UNKNOWN')
        context = error_info.get('context', '')
        
        # 메시지 구성
        user_message = f"{icon} {message}\n"
        
        if context:
            user_message += f"\n상황: {context}\n"
        
        if solution:
            user_message += f"\n해결 방법:\n{solution}\n"
        
        user_message += f"\n오류 코드: {error_code}"
        
        return user_message
    
    def get_technical_details(self, error_info):
        """
        기술적 상세 정보 (개발자/지원팀용)
        
        Args:
            error_info: handle_error가 반환한 오류 정보
            
        Returns:
            str: 기술적 상세 정보
        """
        details = f"""
=== 기술적 오류 정보 ===
시간: {error_info['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}
오류 타입: {error_info['type']}
오류 코드: {error_info.get('error_code', 'UNKNOWN')}
원본 메시지: {error_info['original_message']}
컨텍스트: {error_info.get('context', 'N/A')}

스택 트레이스:
{error_info['traceback']}
"""
        return details
    
    def save_error_report(self, filename=None):
        """
        오류 보고서 저장
        
        Args:
            filename: 저장할 파일명 (없으면 자동 생성)
            
        Returns:
            Path: 저장된 파일 경로
        """
        if not filename:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"error_report_{timestamp}.txt"
        
        report_path = Path("logs") / filename
        report_path.parent.mkdir(exist_ok=True)
        
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write("PDF 품질 검수 시스템 오류 보고서\n")
            f.write("=" * 70 + "\n\n")
            
            f.write(f"생성 일시: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"총 오류 수: {len(self.error_log)}\n\n")
            
            for i, error_info in enumerate(self.error_log, 1):
                f.write(f"\n[오류 {i}]\n")
                f.write("-" * 50 + "\n")
                
                # 사용자 메시지
                f.write("사용자 메시지:\n")
                f.write(self.get_user_message(error_info))
                f.write("\n\n")
                
                # 기술적 상세
                f.write("기술적 상세:\n")
                f.write(self.get_technical_details(error_info))
                f.write("\n")
        
        return report_path
    
    def clear_log(self):
        """오류 로그 초기화"""
        self.error_log.clear()
    
    def get_error_summary(self):
        """
        오류 요약 정보
        
        Returns:
            dict: 오류 타입별 발생 횟수
        """
        summary = {}
        for error in self.error_log:
            error_type = error['type']
            summary[error_type] = summary.get(error_type, 0) + 1
        return summary


# 사용 예시
if __name__ == "__main__":
    # 오류 처리기 생성
    handler = UserFriendlyErrorHandler()
    
    # 예시 1: FileNotFoundError
    try:
        with open("없는파일.pdf", "r") as f:
            pass
    except Exception as e:
        error_info = handler.handle_error(e, "PDF 파일을 열려고 했습니다")
        print(handler.get_user_message(error_info))
        print("\n" + "="*50 + "\n")
    
    # 예시 2: TypeError
    try:
        len(123)  # TypeError 발생
    except Exception as e:
        error_info = handler.handle_error(e, "보고서 생성 중")
        print(handler.get_user_message(error_info))
        print("\n" + "="*50 + "\n")
    
    # 예시 3: 특정 메시지
    try:
        raise ValueError("object of type 'int' has no len()")
    except Exception as e:
        error_info = handler.handle_error(e, "HTML 보고서 생성")
        print(handler.get_user_message(error_info))
    
    # 오류 보고서 저장
    report_path = handler.save_error_report()
    print(f"\n오류 보고서 저장됨: {report_path}")
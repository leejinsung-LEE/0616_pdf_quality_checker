# notification_manager.py - Windows 알림 시스템
# 처리 완료/오류 시 Windows 토스트 알림 표시
# 다양한 알림 라이브러리 지원 (fallback 포함)

"""
notification_manager.py - Windows 알림 시스템
처리 완료, 오류, 일괄 처리 완료 시 알림
설정으로 활성화/비활성화 가능
"""

import platform
from pathlib import Path
from typing import Optional, Dict, List
import json

# 알림 라이브러리들 - 우선순위대로 시도
notification_libraries = []

# 1. Windows 10/11 토스트 (win10toast)
try:
    from win10toast import ToastNotifier
    notification_libraries.append('win10toast')
except ImportError:
    pass

# 2. plyer (크로스 플랫폼)
try:
    from plyer import notification as plyer_notification
    notification_libraries.append('plyer')
except ImportError:
    pass

# 3. Windows 네이티브 (win11toast - 더 현대적)
try:
    from win11toast import toast as win11_toast
    notification_libraries.append('win11toast')
except ImportError:
    pass

class NotificationManager:
    """Windows 알림 관리 클래스"""
    
    def __init__(self, enabled: bool = False):
        """
        알림 매니저 초기화
        
        Args:
            enabled: 알림 활성화 여부 (기본값: False)
        """
        self.enabled = enabled
        self.platform = platform.system()
        self.notification_method = None
        self.toaster = None
        
        # 알림 아이콘 경로 설정
        self.icon_path = self._find_icon()
        
        # 알림 방법 초기화
        self._init_notification_method()
        
        # 알림 설정 로드
        self._load_settings()
    
    def _find_icon(self) -> Optional[str]:
        """아이콘 파일 찾기"""
        possible_paths = [
            Path("assets/icon.ico"),
            Path("icon.ico"),
            Path("assets/pdf_icon.png"),
            Path("pdf_icon.png")
        ]
        
        for path in possible_paths:
            if path.exists():
                return str(path.absolute())
        
        return None
    
    def _init_notification_method(self):
        """사용 가능한 알림 방법 초기화"""
        if self.platform != 'Windows':
            print("알림: Windows가 아닌 시스템에서는 알림이 제한될 수 있습니다.")
            
        # 사용 가능한 라이브러리 확인
        if 'win11toast' in notification_libraries:
            self.notification_method = 'win11toast'
        elif 'win10toast' in notification_libraries:
            self.notification_method = 'win10toast'
            self.toaster = ToastNotifier()
        elif 'plyer' in notification_libraries:
            self.notification_method = 'plyer'
        else:
            self.notification_method = None
            if self.enabled:
                print("경고: 알림 라이브러리가 설치되지 않았습니다.")
                print("설치 방법: pip install win10toast 또는 pip install plyer")
    
    def _load_settings(self):
        """사용자 설정 파일에서 알림 설정 로드"""
        settings_file = Path("user_settings.json")
        
        if settings_file.exists():
            try:
                with open(settings_file, 'r', encoding='utf-8') as f:
                    settings = json.load(f)
                    self.enabled = settings.get('enable_notifications', False)
                    
                    # 세부 알림 설정
                    self.notify_on_success = settings.get('notify_on_success', True)
                    self.notify_on_error = settings.get('notify_on_error', True)
                    self.notify_on_batch = settings.get('notify_on_batch_complete', True)
                    self.play_sound = settings.get('notification_sound', True)
            except Exception as e:
                print(f"설정 로드 실패: {e}")
                self._set_default_settings()
        else:
            self._set_default_settings()
    
    def _set_default_settings(self):
        """기본 설정값"""
        self.notify_on_success = True
        self.notify_on_error = True
        self.notify_on_batch = True
        self.play_sound = True
    
    def notify_success(self, filename: str, issue_count: int, 
                      page_count: Optional[int] = None,
                      processing_time: Optional[float] = None):
        """
        처리 성공 알림
        
        Args:
            filename: 파일명
            issue_count: 발견된 문제 수
            page_count: 페이지 수
            processing_time: 처리 시간 (초)
        """
        if not self.enabled or not self.notify_on_success:
            return
        
        # 알림 제목과 메시지 구성
        title = "PDF 검수 완료 ✅"
        
        if issue_count == 0:
            status = "문제없음"
            emoji = "😊"
        elif issue_count < 5:
            status = f"{issue_count}개 문제 발견"
            emoji = "⚠️"
        else:
            status = f"{issue_count}개 문제 발견"
            emoji = "❗"
        
        message_parts = [f"{filename}", f"{emoji} {status}"]
        
        if page_count:
            message_parts.append(f"📄 {page_count}페이지")
        
        if processing_time:
            message_parts.append(f"⏱️ {processing_time:.1f}초")
        
        message = " | ".join(message_parts)
        
        self._show_notification(title, message, duration=5)
    
    def notify_error(self, filename: str, error_msg: str):
        """
        처리 오류 알림
        
        Args:
            filename: 파일명
            error_msg: 오류 메시지
        """
        if not self.enabled or not self.notify_on_error:
            return
        
        title = "PDF 검수 오류 ❌"
        
        # 오류 메시지 줄이기 (너무 길면 알림에 표시 안됨)
        if len(error_msg) > 100:
            error_msg = error_msg[:97] + "..."
        
        message = f"{filename}\n{error_msg}"
        
        self._show_notification(title, message, duration=10)
    
    def notify_batch_complete(self, total_files: int, success_count: int, 
                            error_count: int, total_time: Optional[float] = None,
                            auto_fixed: int = 0):
        """
        일괄 처리 완료 알림
        
        Args:
            total_files: 전체 파일 수
            success_count: 성공한 파일 수
            error_count: 오류 파일 수
            total_time: 전체 처리 시간
            auto_fixed: 자동 수정된 파일 수
        """
        if not self.enabled or not self.notify_on_batch:
            return
        
        title = "PDF 일괄 처리 완료 🎉"
        
        # 성공률 계산
        success_rate = (success_count / total_files * 100) if total_files > 0 else 0
        
        message_parts = [
            f"총 {total_files}개 파일 처리",
            f"✅ 성공: {success_count}개 ({success_rate:.0f}%)"
        ]
        
        if error_count > 0:
            message_parts.append(f"❌ 오류: {error_count}개")
        
        if auto_fixed > 0:
            message_parts.append(f"🔧 자동수정: {auto_fixed}개")
        
        if total_time:
            if total_time < 60:
                time_str = f"{total_time:.1f}초"
            else:
                minutes = int(total_time // 60)
                seconds = int(total_time % 60)
                time_str = f"{minutes}분 {seconds}초"
            message_parts.append(f"⏱️ 소요시간: {time_str}")
        
        message = "\n".join(message_parts)
        
        self._show_notification(title, message, duration=10)
    
    def notify_warning(self, title: str, message: str):
        """
        경고 알림 (범용)
        
        Args:
            title: 알림 제목
            message: 알림 메시지
        """
        if not self.enabled:
            return
        
        self._show_notification(f"⚠️ {title}", message, duration=7)
    
    def notify_info(self, title: str, message: str):
        """
        정보 알림 (범용)
        
        Args:
            title: 알림 제목
            message: 알림 메시지
        """
        if not self.enabled:
            return
        
        self._show_notification(f"ℹ️ {title}", message, duration=5)
    
    def notify_auto_fix(self, filename: str, fixes_applied: List[str]):
        """
        자동 수정 완료 알림
        
        Args:
            filename: 파일명
            fixes_applied: 적용된 수정 목록
        """
        if not self.enabled:
            return
        
        title = "자동 수정 완료 🔧"
        
        fix_descriptions = {
            'RGB→CMYK 변환': '색상 변환',
            '폰트 아웃라인 변환': '폰트 처리',
            '이미지 최적화': '이미지 처리'
        }
        
        fixes_text = ", ".join([
            fix_descriptions.get(fix, fix) for fix in fixes_applied
        ])
        
        message = f"{filename}\n✅ {fixes_text}"
        
        self._show_notification(title, message, duration=5)
    
    def _show_notification(self, title: str, message: str, duration: int = 5):
        """
        실제 알림 표시 (라이브러리별 구현)
        
        Args:
            title: 알림 제목
            message: 알림 메시지
            duration: 표시 시간 (초)
        """
        if not self.notification_method:
            print(f"[알림] {title}: {message}")
            return
        
        try:
            if self.notification_method == 'win11toast':
                # Windows 11 토스트
                win11_toast(
                    title=title,
                    body=message,
                    duration='short' if duration <= 5 else 'long',
                    icon=self.icon_path,
                    app_id='PDF 품질 검수 시스템'
                )
                
            elif self.notification_method == 'win10toast':
                # Windows 10 토스트
                self.toaster.show_toast(
                    title=title,
                    msg=message,
                    icon_path=self.icon_path,
                    duration=duration,
                    threaded=True  # 비동기로 실행
                )
                
            elif self.notification_method == 'plyer':
                # plyer (크로스 플랫폼)
                plyer_notification.notify(
                    title=title,
                    message=message,
                    app_icon=self.icon_path,
                    timeout=duration,
                    app_name='PDF 품질 검수 시스템'
                )
                
        except Exception as e:
            print(f"알림 표시 실패: {e}")
            print(f"[알림] {title}: {message}")
    
    def test_notification(self):
        """알림 테스트"""
        self.enabled = True  # 임시로 활성화
        
        title = "알림 테스트 🔔"
        message = "PDF 품질 검수 시스템 알림이 정상적으로 작동합니다!"
        
        self._show_notification(title, message, duration=5)
    
    def set_enabled(self, enabled: bool):
        """
        알림 활성화/비활성화
        
        Args:
            enabled: 활성화 여부
        """
        self.enabled = enabled
        
        if enabled and not self.notification_method:
            print("경고: 알림 라이브러리가 설치되지 않았습니다.")
            print("알림 기능을 사용하려면 다음 중 하나를 설치하세요:")
            print("  pip install win10toast")
            print("  pip install plyer")
            print("  pip install win11toast")
    
    def get_status(self) -> Dict:
        """
        알림 시스템 상태 확인
        
        Returns:
            dict: 상태 정보
        """
        return {
            'enabled': self.enabled,
            'platform': self.platform,
            'method': self.notification_method,
            'available_libraries': notification_libraries,
            'has_icon': self.icon_path is not None,
            'settings': {
                'notify_on_success': self.notify_on_success,
                'notify_on_error': self.notify_on_error,
                'notify_on_batch': self.notify_on_batch,
                'play_sound': self.play_sound
            }
        }

# 알림 시스템 싱글톤 인스턴스
_notification_instance = None

def get_notification_manager(enabled: bool = None) -> NotificationManager:
    """
    알림 매니저 싱글톤 인스턴스 반환
    
    Args:
        enabled: 활성화 여부 (최초 생성시만 적용)
        
    Returns:
        NotificationManager: 알림 매니저 인스턴스
    """
    global _notification_instance
    
    if _notification_instance is None:
        _notification_instance = NotificationManager(enabled=enabled or False)
    
    return _notification_instance

# 테스트 코드
if __name__ == "__main__":
    # 알림 매니저 생성
    notifier = NotificationManager(enabled=True)
    
    # 상태 확인
    print("알림 시스템 상태:")
    status = notifier.get_status()
    for key, value in status.items():
        print(f"  {key}: {value}")
    
    # 테스트 알림
    print("\n테스트 알림 발송...")
    notifier.test_notification()
    
    # 다양한 알림 테스트
    import time
    
    time.sleep(2)
    notifier.notify_success("test_document.pdf", 3, page_count=25, processing_time=5.2)
    
    time.sleep(2)
    notifier.notify_error("problematic.pdf", "PDF 파일이 손상되었습니다")
    
    time.sleep(2)
    notifier.notify_batch_complete(10, 8, 2, total_time=45.6, auto_fixed=3)
    
    time.sleep(2)
    notifier.notify_auto_fix("sample.pdf", ["RGB→CMYK 변환", "폰트 아웃라인 변환"])
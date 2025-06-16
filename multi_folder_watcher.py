# multi_folder_watcher.py - 다중 폴더 감시 시스템
# 여러 폴더를 동시에 감시하며 각각 다른 설정 적용
# watchdog 라이브러리 사용 (실시간 파일 시스템 감시)

"""
multi_folder_watcher.py - 다중 폴더 감시 시스템
각 폴더별로 다른 프로파일과 자동 수정 설정 적용
watchdog을 사용한 효율적인 파일 시스템 모니터링
"""

import os
import time
import json
import threading
from pathlib import Path
from typing import Dict, List, Optional, Callable
from datetime import datetime
from queue import Queue
import shutil

# watchdog 라이브러리 사용 시도
try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler, FileCreatedEvent
    HAS_WATCHDOG = True
except ImportError:
    HAS_WATCHDOG = False
    print("경고: watchdog 라이브러리가 설치되지 않았습니다.")
    print("설치: pip install watchdog")

# 프로젝트 모듈
from config import Config
from simple_logger import SimpleLogger

class PDFEventHandler(FileSystemEventHandler):
    """PDF 파일 이벤트 처리기"""
    
    def __init__(self, folder_config: Dict, callback: Callable):
        """
        이벤트 핸들러 초기화
        
        Args:
            folder_config: 폴더 설정
            callback: PDF 파일 발견시 호출할 콜백
        """
        super().__init__()
        self.folder_config = folder_config
        self.callback = callback
        self.logger = SimpleLogger()
        
        # 처리 중인 파일 추적 (중복 방지)
        self.processing_files = set()
        self.lock = threading.Lock()
    
    def on_created(self, event):
        """파일 생성 이벤트"""
        if not event.is_directory and event.src_path.lower().endswith('.pdf'):
            self._handle_pdf_file(event.src_path)
    
    def on_moved(self, event):
        """파일 이동 이벤트"""
        if not event.is_directory and event.dest_path.lower().endswith('.pdf'):
            self._handle_pdf_file(event.dest_path)
    
    def _handle_pdf_file(self, file_path: str):
        """PDF 파일 처리"""
        file_path = Path(file_path)
        
        with self.lock:
            # 이미 처리 중인 파일인지 확인
            if file_path in self.processing_files:
                return
            
            # 파일이 완전히 복사되었는지 확인
            if not self._is_file_ready(file_path):
                return
            
            self.processing_files.add(file_path)
        
        try:
            # 콜백 호출
            self.callback(file_path, self.folder_config)
            self.logger.log(f"새 PDF 발견: {file_path.name} (폴더: {file_path.parent.name})")
        except Exception as e:
            self.logger.error(f"PDF 처리 중 오류: {e}")
        finally:
            with self.lock:
                self.processing_files.discard(file_path)
    
    def _is_file_ready(self, file_path: Path, timeout: float = 5.0) -> bool:
        """
        파일이 완전히 복사되었는지 확인
        
        Args:
            file_path: 파일 경로
            timeout: 최대 대기 시간
            
        Returns:
            bool: 파일 준비 여부
        """
        if not file_path.exists():
            return False
        
        # 파일 크기 안정화 확인
        try:
            initial_size = file_path.stat().st_size
            time.sleep(0.5)  # 짧은 대기
            
            # 파일 크기가 변하지 않으면 준비 완료
            if file_path.exists() and file_path.stat().st_size == initial_size:
                return True
        except:
            pass
        
        return False

class FolderConfig:
    """폴더별 설정 클래스"""
    
    def __init__(self, path: str, profile: str = 'offset', 
                 auto_fix_settings: Optional[Dict] = None,
                 output_folder: Optional[str] = None):
        """
        폴더 설정 초기화
        
        Args:
            path: 감시할 폴더 경로
            profile: 프리플라이트 프로파일
            auto_fix_settings: 자동 수정 설정
            output_folder: 출력 폴더 (None이면 기본값)
        """
        self.path = Path(path).absolute()
        self.profile = profile
        self.auto_fix_settings = auto_fix_settings or {}
        self.output_folder = output_folder or str(Config.OUTPUT_PATH)
        self.enabled = True
        
        # 통계
        self.files_processed = 0
        self.last_processed = None
    
    def to_dict(self) -> Dict:
        """딕셔너리로 변환"""
        return {
            'path': str(self.path),
            'profile': self.profile,
            'auto_fix_settings': self.auto_fix_settings,
            'output_folder': self.output_folder,
            'enabled': self.enabled,
            'files_processed': self.files_processed,
            'last_processed': self.last_processed.isoformat() if self.last_processed else None
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'FolderConfig':
        """딕셔너리에서 생성"""
        config = cls(
            path=data['path'],
            profile=data.get('profile', 'offset'),
            auto_fix_settings=data.get('auto_fix_settings', {}),
            output_folder=data.get('output_folder')
        )
        config.enabled = data.get('enabled', True)
        config.files_processed = data.get('files_processed', 0)
        if data.get('last_processed'):
            config.last_processed = datetime.fromisoformat(data['last_processed'])
        return config

class MultiFolderWatcher:
    """다중 폴더 감시 클래스"""
    
    def __init__(self, config_file: str = "folder_watch_config.json"):
        """
        다중 폴더 감시기 초기화
        
        Args:
            config_file: 설정 파일 경로
        """
        self.config_file = Path(config_file)
        self.folder_configs = {}  # {path: FolderConfig}
        self.observers = {}  # {path: Observer}
        self.is_watching = False
        self.callback = None
        self.logger = SimpleLogger()
        
        # 설정 로드
        self._load_config()
        
        # watchdog 사용 불가시 폴백
        if not HAS_WATCHDOG:
            self.use_polling = True
            self.polling_thread = None
            self.polling_interval = 2  # 초
        else:
            self.use_polling = False
    
    def _load_config(self):
        """설정 파일 로드"""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                for folder_data in data.get('folders', []):
                    config = FolderConfig.from_dict(folder_data)
                    self.folder_configs[str(config.path)] = config
                    
                self.logger.log(f"{len(self.folder_configs)}개 폴더 설정 로드됨")
            except Exception as e:
                self.logger.error(f"설정 파일 로드 실패: {e}")
    
    def _save_config(self):
        """설정 파일 저장"""
        try:
            data = {
                'folders': [
                    config.to_dict() 
                    for config in self.folder_configs.values()
                ],
                'last_saved': datetime.now().isoformat()
            }
            
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                
        except Exception as e:
            self.logger.error(f"설정 파일 저장 실패: {e}")
    
    def add_folder(self, path: str, profile: str = 'offset', 
                   auto_fix_settings: Optional[Dict] = None,
                   output_folder: Optional[str] = None) -> bool:
        """
        감시할 폴더 추가
        
        Args:
            path: 폴더 경로
            profile: 프리플라이트 프로파일
            auto_fix_settings: 자동 수정 설정
            output_folder: 출력 폴더
            
        Returns:
            bool: 추가 성공 여부
        """
        folder_path = Path(path).absolute()
        
        # 폴더 존재 확인
        if not folder_path.exists():
            try:
                folder_path.mkdir(parents=True, exist_ok=True)
                self.logger.log(f"폴더 생성: {folder_path}")
            except Exception as e:
                self.logger.error(f"폴더 생성 실패: {e}")
                return False
        
        # 이미 감시 중인지 확인
        path_str = str(folder_path)
        if path_str in self.folder_configs:
            self.logger.log(f"이미 감시 중인 폴더: {folder_path.name}")
            return False
        
        # 설정 추가
        config = FolderConfig(
            path=path_str,
            profile=profile,
            auto_fix_settings=auto_fix_settings,
            output_folder=output_folder
        )
        
        self.folder_configs[path_str] = config
        
        # 감시 중이면 즉시 시작
        if self.is_watching:
            self._start_watching_folder(config)
        
        # 설정 저장
        self._save_config()
        
        self.logger.log(f"폴더 추가됨: {folder_path.name} (프로파일: {profile})")
        return True
    
    def remove_folder(self, path: str) -> bool:
        """
        폴더 감시 제거
        
        Args:
            path: 폴더 경로
            
        Returns:
            bool: 제거 성공 여부
        """
        folder_path = Path(path).absolute()
        path_str = str(folder_path)
        
        if path_str not in self.folder_configs:
            return False
        
        # 감시 중지
        if self.use_polling:
            # 폴링 모드에서는 설정만 제거
            pass
        else:
            if path_str in self.observers:
                self.observers[path_str].stop()
                self.observers[path_str].join()
                del self.observers[path_str]
        
        # 설정 제거
        del self.folder_configs[path_str]
        
        # 설정 저장
        self._save_config()
        
        self.logger.log(f"폴더 제거됨: {folder_path.name}")
        return True
    
    def update_folder_config(self, path: str, **kwargs) -> bool:
        """
        폴더 설정 업데이트
        
        Args:
            path: 폴더 경로
            **kwargs: 업데이트할 설정
            
        Returns:
            bool: 업데이트 성공 여부
        """
        folder_path = Path(path).absolute()
        path_str = str(folder_path)
        
        if path_str not in self.folder_configs:
            return False
        
        config = self.folder_configs[path_str]
        
        # 설정 업데이트
        if 'profile' in kwargs:
            config.profile = kwargs['profile']
        if 'auto_fix_settings' in kwargs:
            config.auto_fix_settings = kwargs['auto_fix_settings']
        if 'output_folder' in kwargs:
            config.output_folder = kwargs['output_folder']
        if 'enabled' in kwargs:
            config.enabled = kwargs['enabled']
        
        # 설정 저장
        self._save_config()
        
        self.logger.log(f"폴더 설정 업데이트: {folder_path.name}")
        return True
    
    def set_callback(self, callback: Callable[[Path, Dict], None]):
        """
        PDF 파일 발견시 호출할 콜백 설정
        
        Args:
            callback: 콜백 함수 (file_path, folder_config)
        """
        self.callback = callback
    
    def start_watching(self):
        """모든 폴더 감시 시작"""
        if self.is_watching:
            self.logger.log("이미 감시 중입니다")
            return
        
        self.is_watching = True
        
        if self.use_polling:
            # 폴링 모드
            self._start_polling()
        else:
            # watchdog 모드
            for config in self.folder_configs.values():
                if config.enabled:
                    self._start_watching_folder(config)
        
        self.logger.log(f"{len([c for c in self.folder_configs.values() if c.enabled])}개 폴더 감시 시작")
    
    def _start_watching_folder(self, config: FolderConfig):
        """개별 폴더 감시 시작 (watchdog)"""
        if self.use_polling:
            return
        
        path_str = str(config.path)
        
        # 이벤트 핸들러 생성
        event_handler = PDFEventHandler(config.to_dict(), self._on_pdf_found)
        
        # Observer 생성
        observer = Observer()
        observer.schedule(event_handler, path_str, recursive=False)
        observer.start()
        
        self.observers[path_str] = observer
        
    def _start_polling(self):
        """폴링 모드 시작"""
        def polling_loop():
            # 각 폴더의 처리된 파일 추적
            processed_files = {
                path: set() for path in self.folder_configs.keys()
            }
            
            while self.is_watching:
                for path_str, config in self.folder_configs.items():
                    if not config.enabled:
                        continue
                    
                    try:
                        folder_path = Path(path_str)
                        if not folder_path.exists():
                            continue
                        
                        # PDF 파일 검색
                        pdf_files = list(folder_path.glob("*.pdf"))
                        
                        # 새 파일 찾기
                        new_files = [
                            f for f in pdf_files 
                            if f not in processed_files[path_str]
                        ]
                        
                        for pdf_file in new_files:
                            # 파일이 준비되었는지 확인
                            if self._is_file_ready_polling(pdf_file):
                                self._on_pdf_found(pdf_file, config.to_dict())
                                processed_files[path_str].add(pdf_file)
                        
                    except Exception as e:
                        self.logger.error(f"폴링 중 오류 ({path_str}): {e}")
                
                # 폴링 간격 대기
                time.sleep(self.polling_interval)
        
        self.polling_thread = threading.Thread(target=polling_loop, daemon=True)
        self.polling_thread.start()
    
    def _is_file_ready_polling(self, file_path: Path) -> bool:
        """파일 준비 상태 확인 (폴링용)"""
        try:
            # 파일 크기 확인
            size1 = file_path.stat().st_size
            time.sleep(0.5)
            size2 = file_path.stat().st_size
            
            return size1 == size2 and size1 > 0
        except:
            return False
    
    def _on_pdf_found(self, file_path: Path, folder_config: Dict):
        """
        PDF 파일 발견시 호출
        
        Args:
            file_path: PDF 파일 경로
            folder_config: 폴더 설정
        """
        # 통계 업데이트
        path_str = folder_config['path']
        if path_str in self.folder_configs:
            self.folder_configs[path_str].files_processed += 1
            self.folder_configs[path_str].last_processed = datetime.now()
        
        # 콜백 호출
        if self.callback:
            self.callback(file_path, folder_config)
        else:
            self.logger.log(f"콜백 미설정 - PDF 발견: {file_path.name}")
    
    def stop_watching(self):
        """모든 폴더 감시 중지"""
        if not self.is_watching:
            return
        
        self.is_watching = False
        
        if self.use_polling:
            # 폴링 스레드 종료 대기
            if self.polling_thread:
                self.polling_thread.join(timeout=5)
        else:
            # 모든 Observer 중지
            for observer in self.observers.values():
                observer.stop()
                observer.join()
            
            self.observers.clear()
        
        self.logger.log("폴더 감시 중지됨")
    
    def get_status(self) -> Dict:
        """
        감시 상태 조회
        
        Returns:
            dict: 상태 정보
        """
        active_folders = [
            config for config in self.folder_configs.values() 
            if config.enabled
        ]
        
        return {
            'is_watching': self.is_watching,
            'use_polling': self.use_polling,
            'total_folders': len(self.folder_configs),
            'active_folders': len(active_folders),
            'folders': [
                {
                    'path': config.path.name,
                    'full_path': str(config.path),
                    'profile': config.profile,
                    'enabled': config.enabled,
                    'files_processed': config.files_processed,
                    'last_processed': config.last_processed.isoformat() if config.last_processed else None,
                    'auto_fix': any(config.auto_fix_settings.values())
                }
                for config in self.folder_configs.values()
            ]
        }
    
    def get_folder_list(self) -> List[Dict]:
        """
        폴더 목록 조회 (GUI용)
        
        Returns:
            list: 폴더 정보 목록
        """
        return [
            {
                'path': str(config.path),
                'name': config.path.name,
                'profile': config.profile,
                'enabled': config.enabled,
                'processed': config.files_processed,
                'auto_convert_rgb': config.auto_fix_settings.get('auto_convert_rgb', False),
                'auto_outline_fonts': config.auto_fix_settings.get('auto_outline_fonts', False)
            }
            for config in self.folder_configs.values()
        ]

# 테스트 코드
if __name__ == "__main__":
    # 다중 폴더 감시기 생성
    watcher = MultiFolderWatcher()
    
    # 테스트 콜백
    def test_callback(file_path: Path, folder_config: Dict):
        print(f"\n새 PDF 발견!")
        print(f"  파일: {file_path.name}")
        print(f"  폴더: {file_path.parent.name}")
        print(f"  프로파일: {folder_config['profile']}")
        print(f"  자동 수정: {folder_config.get('auto_fix_settings', {})}")
    
    watcher.set_callback(test_callback)
    
    # 테스트 폴더 추가
    test_folders = [
        {
            'path': 'C:/PDF_인쇄소A',
            'profile': 'offset',
            'auto_fix': {'auto_convert_rgb': True}
        },
        {
            'path': 'C:/PDF_신문사B',
            'profile': 'newspaper',
            'auto_fix': {'auto_outline_fonts': True}
        }
    ]
    
    for folder in test_folders:
        watcher.add_folder(
            folder['path'],
            profile=folder['profile'],
            auto_fix_settings=folder['auto_fix']
        )
    
    # 상태 확인
    print("\n감시 상태:")
    status = watcher.get_status()
    print(f"  감시 중: {status['is_watching']}")
    print(f"  폴더 수: {status['total_folders']}")
    print(f"  폴링 모드: {status['use_polling']}")
    
    # 감시 시작
    print("\n감시 시작... (Ctrl+C로 종료)")
    watcher.start_watching()
    
    try:
        # 계속 실행
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n감시 중지...")
        watcher.stop_watching()
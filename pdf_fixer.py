# pdf_fixer.py - PDF 자동 수정 기능의 메인 컨트롤러
# 2025.01 신규 생성

"""
pdf_fixer.py - PDF 자동 수정 모듈
분석된 문제점을 자동으로 수정하는 기능 제공
"""

import shutil
from pathlib import Path
from datetime import datetime
import json
from typing import Dict, List, Optional, Union

# 프로젝트 모듈
from config import Config
from simple_logger import SimpleLogger

# 수정 모듈들 (구현 예정)
try:
    from color_converter import ColorConverter
    HAS_COLOR_CONVERTER = True
except ImportError:
    HAS_COLOR_CONVERTER = False
    print("경고: color_converter 모듈을 찾을 수 없습니다.")

try:
    from font_handler import FontHandler
    HAS_FONT_HANDLER = True
except ImportError:
    HAS_FONT_HANDLER = False
    print("경고: font_handler 모듈을 찾을 수 없습니다.")


class PDFFixer:
    """PDF 자동 수정 클래스"""
    
    def __init__(self, settings: Optional[Dict] = None, settings_path: str = "user_settings.json"):
        """
        PDF 수정기 초기화
        
        Args:
            settings: 설정 딕셔너리 (제공되지 않으면 파일에서 로드)
            settings_path: 설정 파일 경로
        """
        self.logger = SimpleLogger()
        
        # 설정 로드
        if settings:
            self.settings = settings
        else:
            self.settings = self._load_settings(settings_path)
        
        # 수정 모듈 초기화
        self.color_converter = ColorConverter() if HAS_COLOR_CONVERTER else None
        self.font_handler = FontHandler() if HAS_FONT_HANDLER else None
        
        # 백업 폴더 확인
        self.backup_folder = Config.OUTPUT_PATH / Config.BACKUP_FOLDER
        self.fixed_folder = Config.OUTPUT_PATH / Config.FIXED_FOLDER
        self._ensure_folders()
    
    def _load_settings(self, settings_path: str) -> Dict:
        """
        설정 파일 로드
        
        Args:
            settings_path: 설정 파일 경로
            
        Returns:
            설정 딕셔너리
        """
        settings_file = Path(settings_path)
        
        if settings_file.exists():
            try:
                with open(settings_file, 'r', encoding='utf-8') as f:
                    settings = json.load(f)
                    self.logger.log(f"설정 파일 로드됨: {settings_path}")
                    return settings
            except Exception as e:
                self.logger.error(f"설정 파일 로드 실패: {e}")
        
        # 기본 설정값
        return {
            'auto_convert_rgb': False,
            'auto_outline_fonts': False,
            'always_backup': True,
            'create_comparison_report': True
        }
    
    def _ensure_folders(self):
        """필요한 폴더 생성"""
        self.backup_folder.mkdir(exist_ok=True, parents=True)
        self.fixed_folder.mkdir(exist_ok=True, parents=True)
    
    def fix_pdf(self, pdf_path: Union[str, Path], analysis_result: Dict) -> Dict:
        """
        PDF 파일의 문제점을 자동으로 수정
        
        Args:
            pdf_path: 원본 PDF 파일 경로
            analysis_result: PDFAnalyzer의 분석 결과
            
        Returns:
            수정 결과 딕셔너리
        """
        pdf_path = Path(pdf_path)
        
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF 파일을 찾을 수 없습니다: {pdf_path}")
        
        self.logger.log(f"자동 수정 시작: {pdf_path.name}")
        
        # 결과 초기화
        result = {
            'original': str(pdf_path),
            'fixed': None,
            'backup': None,
            'modifications': [],
            'errors': []
        }
        
        # 1. 백업 생성 (항상)
        if self.settings.get('always_backup', True):
            try:
                backup_path = self._create_backup(pdf_path)
                result['backup'] = str(backup_path)
                self.logger.log(f"백업 생성 완료: {backup_path.name}")
            except Exception as e:
                error_msg = f"백업 생성 실패: {str(e)}"
                self.logger.error(error_msg)
                result['errors'].append(error_msg)
                # 백업 실패시 중단
                return result
        
        # 2. 수정이 필요한지 확인
        modifications_needed = self._check_modifications_needed(analysis_result)
        
        if not modifications_needed:
            self.logger.log("수정이 필요한 문제가 없습니다.")
            return result
        
        # 3. 수정 작업 수행
        current_path = pdf_path
        temp_paths = []  # 임시 파일 추적용
        
        try:
            # RGB→CMYK 변환
            if 'rgb_to_cmyk' in modifications_needed:
                if self.color_converter:
                    self.logger.log("RGB→CMYK 색상 변환 중...")
                    
                    # 출력 경로 생성
                    temp_path = self._get_temp_path(current_path, "color_converted")
                    
                    # 색상 변환 수행
                    success = self.color_converter.convert_rgb_to_cmyk(
                        current_path, 
                        temp_path
                    )
                    
                    if success:
                        current_path = temp_path
                        temp_paths.append(temp_path)
                        result['modifications'].append('RGB→CMYK 변환')
                        self.logger.log("색상 변환 완료")
                    else:
                        error_msg = "색상 변환 실패"
                        self.logger.error(error_msg)
                        result['errors'].append(error_msg)
                else:
                    result['errors'].append("색상 변환 모듈을 사용할 수 없습니다")
            
            # 폰트 아웃라인 변환
            if 'font_outline' in modifications_needed:
                if self.font_handler:
                    self.logger.log("폰트 아웃라인 변환 중...")
                    
                    # 출력 경로 생성
                    temp_path = self._get_temp_path(current_path, "font_outlined")
                    
                    # 아웃라인 변환 수행
                    success = self.font_handler.convert_all_to_outline(
                        current_path,
                        temp_path
                    )
                    
                    if success:
                        current_path = temp_path
                        temp_paths.append(temp_path)
                        result['modifications'].append('폰트 아웃라인 변환')
                        self.logger.log("폰트 아웃라인 변환 완료")
                    else:
                        error_msg = "폰트 아웃라인 변환 실패"
                        self.logger.error(error_msg)
                        result['errors'].append(error_msg)
                else:
                    result['errors'].append("폰트 처리 모듈을 사용할 수 없습니다")
            
            # 4. 최종 파일 저장
            if result['modifications']:
                # 수정된 파일을 fixed 폴더로 이동
                fixed_path = self._save_fixed_file(current_path, pdf_path.name)
                result['fixed'] = str(fixed_path)
                
                # 임시 파일 정리
                for temp_path in temp_paths[:-1]:  # 마지막 파일은 이미 이동됨
                    try:
                        temp_path.unlink()
                    except:
                        pass
                
                self.logger.log(f"자동 수정 완료: {', '.join(result['modifications'])}")
            
        except Exception as e:
            error_msg = f"자동 수정 중 오류 발생: {str(e)}"
            self.logger.error(error_msg)
            result['errors'].append(error_msg)
            
            # 임시 파일 정리
            for temp_path in temp_paths:
                try:
                    if temp_path.exists():
                        temp_path.unlink()
                except:
                    pass
        
        return result
    
    def _check_modifications_needed(self, analysis_result: Dict) -> List[str]:
        """
        어떤 수정이 필요한지 확인
        
        Args:
            analysis_result: 분석 결과
            
        Returns:
            필요한 수정 작업 리스트
        """
        modifications = []
        
        # RGB→CMYK 변환 필요 확인
        if self.settings.get('auto_convert_rgb', False):
            colors = analysis_result.get('colors', {})
            if colors.get('has_rgb') and not colors.get('has_cmyk'):
                modifications.append('rgb_to_cmyk')
                self.logger.log("RGB 색상 발견 - CMYK 변환 필요")
        
        # 폰트 아웃라인 변환 필요 확인
        if self.settings.get('auto_outline_fonts', False):
            fonts = analysis_result.get('fonts', {})
            not_embedded = sum(1 for f in fonts.values() if not f.get('embedded', False))
            if not_embedded > 0:
                modifications.append('font_outline')
                self.logger.log(f"미임베딩 폰트 {not_embedded}개 발견 - 아웃라인 변환 필요")
        
        return modifications
    
    def _create_backup(self, pdf_path: Path) -> Path:
        """
        원본 파일 백업 생성
        
        Args:
            pdf_path: 원본 PDF 파일 경로
            
        Returns:
            백업 파일 경로
        """
        # 백업 파일명 생성 (타임스탬프 포함)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"{pdf_path.stem}_backup_{timestamp}{pdf_path.suffix}"
        backup_path = self.backup_folder / backup_name
        
        # 파일 복사
        shutil.copy2(pdf_path, backup_path)
        
        return backup_path
    
    def _get_temp_path(self, current_path: Path, suffix: str) -> Path:
        """
        임시 파일 경로 생성
        
        Args:
            current_path: 현재 파일 경로
            suffix: 파일명에 추가할 접미사
            
        Returns:
            임시 파일 경로
        """
        # 임시 폴더는 fixed 폴더 사용
        temp_name = f"{current_path.stem}_{suffix}{current_path.suffix}"
        return self.fixed_folder / temp_name
    
    def _save_fixed_file(self, source_path: Path, original_name: str) -> Path:
        """
        수정된 파일을 최종 위치에 저장
        
        Args:
            source_path: 수정된 파일 경로
            original_name: 원본 파일명
            
        Returns:
            최종 파일 경로
        """
        # 최종 파일명 생성
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        fixed_name = f"{Path(original_name).stem}_fixed_{timestamp}.pdf"
        fixed_path = self.fixed_folder / fixed_name
        
        # 파일 이동 (이미 fixed 폴더에 있으면 이름만 변경)
        if source_path.parent == self.fixed_folder:
            source_path.rename(fixed_path)
        else:
            shutil.move(str(source_path), str(fixed_path))
        
        return fixed_path
    
    def get_fixable_issues(self, analysis_result: Dict) -> Dict[str, bool]:
        """
        수정 가능한 문제 목록과 현재 설정 상태 반환
        
        Args:
            analysis_result: 분석 결과
            
        Returns:
            수정 가능한 문제와 활성화 여부
        """
        fixable = {}
        
        # RGB 색상 문제
        colors = analysis_result.get('colors', {})
        if colors.get('has_rgb') and not colors.get('has_cmyk'):
            fixable['RGB 색상 사용'] = {
                'can_fix': HAS_COLOR_CONVERTER,
                'enabled': self.settings.get('auto_convert_rgb', False),
                'description': 'RGB를 CMYK로 변환'
            }
        
        # 폰트 임베딩 문제
        fonts = analysis_result.get('fonts', {})
        not_embedded = sum(1 for f in fonts.values() if not f.get('embedded', False))
        if not_embedded > 0:
            fixable['폰트 미임베딩'] = {
                'can_fix': HAS_FONT_HANDLER,
                'enabled': self.settings.get('auto_outline_fonts', False),
                'description': f'{not_embedded}개 폰트를 아웃라인으로 변환'
            }
        
        return fixable


# 테스트용 메인
if __name__ == "__main__":
    # 테스트 설정
    test_settings = {
        'auto_convert_rgb': True,
        'auto_outline_fonts': True,
        'always_backup': True,
        'create_comparison_report': True
    }
    
    # PDF 수정기 생성
    fixer = PDFFixer(settings=test_settings)
    
    # 테스트 분석 결과
    test_analysis = {
        'colors': {
            'has_rgb': True,
            'has_cmyk': False
        },
        'fonts': {
            'font1': {'embedded': False},
            'font2': {'embedded': True},
            'font3': {'embedded': False}
        }
    }
    
    # 수정 가능한 문제 확인
    fixable = fixer.get_fixable_issues(test_analysis)
    print("수정 가능한 문제:")
    for issue, info in fixable.items():
        print(f"  - {issue}: {info['description']}")
        print(f"    수정 가능: {'예' if info['can_fix'] else '아니오'}")
        print(f"    활성화됨: {'예' if info['enabled'] else '아니오'}")
    
    # 실제 수정은 PDF 파일이 있을 때만 가능
    # result = fixer.fix_pdf("sample.pdf", test_analysis)
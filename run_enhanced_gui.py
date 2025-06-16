#!/usr/bin/env python
# run_enhanced_gui.py - 향상된 GUI 실행 스크립트
# 기존 pdf_checker_gui.py 대신 새로운 통합 GUI를 실행

"""
run_enhanced_gui.py - PDF 검수 시스템 v3.5 실행기
모든 기능이 통합된 GUI를 실행합니다.
"""

import sys
import os
from pathlib import Path

# 필요한 라이브러리 확인
def check_requirements():
    """필수 라이브러리 확인"""
    missing = []
    
    # 필수 라이브러리
    required = {
        'tkinter': 'tkinter',
        'PyMuPDF': 'fitz',
        'pikepdf': 'pikepdf',
        'numpy': 'numpy'
    }
    
    # 선택적 라이브러리
    optional = {
        'tkinterdnd2': 'tkinterdnd2',
        'watchdog': 'watchdog',
        'win10toast': 'win10toast',
        'plyer': 'plyer',
        'matplotlib': 'matplotlib'
    }
    
    print("라이브러리 확인 중...")
    
    # 필수 확인
    for name, module in required.items():
        try:
            __import__(module)
            print(f"✓ {name} ... OK")
        except ImportError:
            missing.append(name)
            print(f"✗ {name} ... 없음")
    
    # 선택적 확인
    print("\n선택적 라이브러리:")
    for name, module in optional.items():
        try:
            __import__(module)
            print(f"✓ {name} ... OK")
        except ImportError:
            print(f"  {name} ... 없음 (선택사항)")
    
    if missing:
        print(f"\n필수 라이브러리가 없습니다: {', '.join(missing)}")
        print("설치 명령어:")
        print(f"pip install {' '.join(missing)}")
        return False
    
    return True

def main():
    """메인 실행 함수"""
    print("=" * 60)
    print("PDF 품질 검수 시스템 v3.5 - 통합 에디션")
    print("=" * 60)
    
    # 라이브러리 확인
    if not check_requirements():
        print("\n필수 라이브러리를 설치한 후 다시 실행하세요.")
        input("\n엔터를 눌러 종료...")
        sys.exit(1)
    
    print("\n시스템을 시작합니다...")
    
    try:
        # 향상된 GUI 임포트 및 실행
        from pdf_checker_gui_enhanced import EnhancedPDFCheckerGUI
        
        # GUI 실행
        app = EnhancedPDFCheckerGUI()
        app.run()
        
    except ImportError as e:
        print(f"\n오류: pdf_checker_gui_enhanced.py 파일을 찾을 수 없습니다.")
        print(f"상세: {e}")
        print("\n파일이 같은 폴더에 있는지 확인하세요.")
        input("\n엔터를 눌러 종료...")
        sys.exit(1)
        
    except Exception as e:
        print(f"\n예상치 못한 오류가 발생했습니다:")
        print(f"{type(e).__name__}: {e}")
        
        import traceback
        traceback.print_exc()
        
        input("\n엔터를 눌러 종료...")
        sys.exit(1)

if __name__ == "__main__":
    # 현재 디렉토리를 작업 디렉토리로 설정
    os.chdir(Path(__file__).parent)
    
    # 메인 실행
    main()
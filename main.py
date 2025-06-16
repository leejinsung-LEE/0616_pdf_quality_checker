# main.py - 프로그램의 시작점입니다
# Phase 2.5: 프리플라이트 프로파일 선택 기능 추가

"""
main.py - PDF 자동검수 시스템 Phase 2.5 메인 진입점
"""

import sys
import argparse
from pathlib import Path
from config import Config
from pdf_analyzer import PDFAnalyzer
from report_generator import ReportGenerator
from file_monitor import PDFMonitor, check_existing_files
from preflight_profiles import PreflightProfiles
from utils import format_datetime
import shutil

def print_banner():
    """프로그램 배너 출력"""
    print("""
╔═══════════════════════════════════════════════════════════╗
║           PDF 자동검수 시스템 - Phase 2.5                 ║
║                                                           ║
║   • 기본 PDF 정보 분석                                   ║
║   • 잉크량 계산 (TAC)                                    ║
║   • 폰트 임베딩 검사                                     ║
║   • 이미지 해상도 검사                                   ║
║   • 투명도/중복인쇄 검사                                 ║
║   • 재단선 여백 검사                                     ║
║   • 프리플라이트 프로파일                                ║
║   • HTML/텍스트 보고서 생성                              ║
╚═══════════════════════════════════════════════════════════╝
    """)

def list_profiles():
    """사용 가능한 프리플라이트 프로파일 목록 표시"""
    print("\n📋 사용 가능한 프리플라이트 프로파일:")
    print("=" * 60)
    
    profiles = PreflightProfiles.get_all_profiles()
    for key, profile in profiles.items():
        print(f"\n🎯 {key}")
        print(f"   이름: {profile.name}")
        print(f"   설명: {profile.description}")
        print(f"   규칙: {len(profile.rules)}개")
    
    print("\n💡 사용법: --profile [프로파일명]")
    print("   예시: python main.py sample.pdf --profile offset")

def process_single_pdf(pdf_path, options=None):
    """
    단일 PDF 파일을 처리하는 함수
    
    Args:
        pdf_path: 처리할 PDF 파일 경로
        options: 명령줄 옵션
    """
    pdf_path = Path(pdf_path)
    
    if not pdf_path.exists():
        print(f"❌ 파일을 찾을 수 없습니다: {pdf_path}")
        return False
    
    if not pdf_path.suffix.lower() == '.pdf':
        print(f"❌ PDF 파일이 아닙니다: {pdf_path}")
        return False
    
    print(f"\n{'='*70}")
    print(f"📄 PDF 파일 처리: {pdf_path.name}")
    print(f"시간: {format_datetime()}")
    print(f"{'='*70}")
    
    # PDF 분석
    analyzer = PDFAnalyzer()
    
    # 옵션 처리
    include_ink = True  # 기본값
    if options and hasattr(options, 'no_ink'):
        include_ink = not options.no_ink
    
    # 프리플라이트 프로파일 선택
    profile = Config.DEFAULT_PREFLIGHT_PROFILE
    if options and hasattr(options, 'profile') and options.profile:
        profile = options.profile
    
    print(f"\n🎯 프리플라이트 프로파일: {profile}")
    
    result = analyzer.analyze(pdf_path, include_ink_analysis=include_ink, preflight_profile=profile)
    
    if 'error' in result:
        print(f"\n❌ 분석 실패: {result['error']}")
        return False
    
    # 보고서 생성
    generator = ReportGenerator()
    
    # 보고서 형식 결정
    report_format = Config.DEFAULT_REPORT_FORMAT
    if options:
        if hasattr(options, 'text_only') and options.text_only:
            report_format = 'text'
        elif hasattr(options, 'html_only') and options.html_only:
            report_format = 'html'
    
    report_paths = generator.generate_reports(result, format_type=report_format)
    
    # 결과에 따라 파일 분류 (옵션이 있는 경우)
    if options and hasattr(options, 'auto_sort') and options.auto_sort:
        # 프리플라이트 결과 우선 고려
        preflight_result = result.get('preflight_result', {})
        preflight_status = preflight_result.get('overall_status', 'unknown')
        
        issues = result.get('issues', [])
        errors = [i for i in issues if i['severity'] == 'error']
        warnings = [i for i in issues if i['severity'] == 'warning']
        
        # 파일 이동
        if preflight_status == 'fail' or errors:
            dest_folder = Config.OUTPUT_PATH / "오류"
            prefix = f"오류{len(errors)}_"
        elif preflight_status == 'warning' or warnings:
            dest_folder = Config.OUTPUT_PATH / "경고"
            prefix = f"경고{len(warnings)}_"
        else:
            dest_folder = Config.OUTPUT_PATH / "정상"
            prefix = "정상_"
        
        # 대상 폴더 생성
        dest_folder.mkdir(exist_ok=True, parents=True)
        
        # 파일 복사 (원본 유지)
        dest_path = dest_folder / (prefix + pdf_path.name)
        shutil.copy2(str(pdf_path), str(dest_path))
        print(f"\n✅ 파일 분류 완료: {dest_path.parent.name}/{dest_path.name}")
    
    # 완료 메시지
    print(f"\n✅ 처리 완료!")
    if 'text' in report_paths:
        print(f"  • 텍스트 보고서: {report_paths['text']}")
    if 'html' in report_paths:
        print(f"  • HTML 보고서: {report_paths['html']}")
    
    # 주요 정보 출력
    basic = result['basic_info']
    print(f"\n📊 분석 요약:")
    print(f"  • 총 페이지: {basic['page_count']}페이지")
    print(f"  • PDF 버전: {basic['pdf_version']}")
    
    # 프리플라이트 결과
    preflight_result = result.get('preflight_result', {})
    if preflight_result:
        print(f"\n🎯 프리플라이트 결과:")
        print(f"  • 프로파일: {preflight_result.get('profile', 'Unknown')}")
        print(f"  • 상태: {preflight_result.get('overall_status', 'Unknown')}")
        print(f"  • 통과: {len(preflight_result.get('passed', []))}개")
        print(f"  • 실패: {len(preflight_result.get('failed', []))}개")
        print(f"  • 경고: {len(preflight_result.get('warnings', []))}개")
    
    return True

def process_batch(folder_path, options=None):
    """
    폴더 내의 모든 PDF 파일을 일괄 처리
    
    Args:
        folder_path: PDF 파일들이 있는 폴더 경로
        options: 명령줄 옵션
    """
    folder_path = Path(folder_path)
    
    if not folder_path.exists() or not folder_path.is_dir():
        print(f"❌ 폴더를 찾을 수 없습니다: {folder_path}")
        return
    
    pdf_files = list(folder_path.glob("*.pdf"))
    
    if not pdf_files:
        print(f"❌ 폴더에 PDF 파일이 없습니다: {folder_path}")
        return
    
    print(f"\n📂 일괄 처리 모드")
    print(f"폴더: {folder_path}")
    print(f"PDF 파일: {len(pdf_files)}개")
    
    # 프로파일 확인
    profile = Config.DEFAULT_PREFLIGHT_PROFILE
    if options and hasattr(options, 'profile') and options.profile:
        profile = options.profile
    print(f"프리플라이트 프로파일: {profile}")
    print("-" * 70)
    
    success_count = 0
    
    for i, pdf_file in enumerate(pdf_files, 1):
        print(f"\n[{i}/{len(pdf_files)}] 처리 중...")
        if process_single_pdf(pdf_file, options):
            success_count += 1
    
    print(f"\n{'='*70}")
    print(f"✅ 일괄 처리 완료!")
    print(f"  • 성공: {success_count}/{len(pdf_files)}개")
    print(f"  • 실패: {len(pdf_files) - success_count}개")

def create_argument_parser():
    """명령줄 인자 파서 생성"""
    parser = argparse.ArgumentParser(
        description='PDF 자동검수 시스템 Phase 2.5',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
사용 예시:
  # 폴더 모니터링 모드 (기본)
  python main.py
  
  # 단일 파일 처리
  python main.py sample.pdf
  
  # 특정 프로파일로 처리
  python main.py sample.pdf --profile digital
  
  # 일괄 처리
  python main.py --batch ./pdfs/ --profile offset
  
  # 잉크량 분석 제외
  python main.py sample.pdf --no-ink
  
  # HTML 보고서만 생성
  python main.py sample.pdf --html-only
  
  # 처리 후 자동 분류
  python main.py sample.pdf --auto-sort
  
  # 사용 가능한 프로파일 보기
  python main.py --list-profiles
        """
    )
    
    # 위치 인자
    parser.add_argument(
        'input',
        nargs='?',
        help='처리할 PDF 파일 또는 폴더 경로'
    )
    
    # 선택적 인자
    parser.add_argument(
        '--batch', '-b',
        action='store_true',
        help='폴더 내 모든 PDF 파일을 일괄 처리'
    )
    
    parser.add_argument(
        '--profile', '-p',
        type=str,
        choices=['offset', 'digital', 'newspaper', 'large_format', 'high_quality'],
        default=Config.DEFAULT_PREFLIGHT_PROFILE,
        help='프리플라이트 프로파일 선택 (기본: offset)'
    )
    
    parser.add_argument(
        '--list-profiles',
        action='store_true',
        help='사용 가능한 프리플라이트 프로파일 목록 표시'
    )
    
    parser.add_argument(
        '--no-ink',
        action='store_true',
        help='잉크량 분석을 건너뜀 (빠른 처리)'
    )
    
    parser.add_argument(
        '--text-only',
        action='store_true',
        help='텍스트 보고서만 생성'
    )
    
    parser.add_argument(
        '--html-only',
        action='store_true',
        help='HTML 보고서만 생성'
    )
    
    parser.add_argument(
        '--auto-sort',
        action='store_true',
        help='분석 후 파일을 자동으로 분류 (정상/경고/오류)'
    )
    
    parser.add_argument(
        '--config',
        action='store_true',
        help='현재 설정 표시'
    )
    
    parser.add_argument(
        '--monitor-profile',
        type=str,
        choices=['offset', 'digital', 'newspaper', 'large_format', 'high_quality'],
        default=Config.DEFAULT_PREFLIGHT_PROFILE,
        help='모니터링 모드에서 사용할 프로파일'
    )
    
    return parser

def show_config():
    """현재 설정 표시"""
    print("\n⚙️  현재 설정")
    print("=" * 50)
    print(f"입력 폴더: {Config.INPUT_PATH}")
    print(f"출력 폴더: {Config.OUTPUT_PATH}")
    print(f"보고서 폴더: {Config.REPORTS_PATH}")
    print(f"\n품질 기준:")
    print(f"  • 최대 잉크량: {Config.MAX_INK_COVERAGE}%")
    print(f"  • 경고 잉크량: {Config.WARNING_INK_COVERAGE}%")
    print(f"  • 최소 이미지 해상도: {Config.MIN_IMAGE_DPI} DPI")
    print(f"  • 페이지 크기 허용 오차: {Config.PAGE_SIZE_TOLERANCE}mm")
    print(f"  • 표준 재단 여백: {Config.STANDARD_BLEED_SIZE}mm")
    print(f"\n프리플라이트:")
    print(f"  • 기본 프로파일: {Config.DEFAULT_PREFLIGHT_PROFILE}")
    print(f"  • 사용 가능: {', '.join(Config.AVAILABLE_PROFILES)}")
    print(f"\n고급 검사:")
    print(f"  • 투명도 검사: {'활성' if Config.CHECK_OPTIONS['transparency'] else '비활성'}")
    print(f"  • 중복인쇄 검사: {'활성' if Config.CHECK_OPTIONS['overprint'] else '비활성'}")
    print(f"  • 재단선 검사: {'활성' if Config.CHECK_OPTIONS['bleed'] else '비활성'}")
    print(f"\n보고서 설정:")
    print(f"  • 기본 형식: {Config.DEFAULT_REPORT_FORMAT}")
    print(f"  • HTML 스타일: {Config.HTML_REPORT_STYLE}")
    print("=" * 50)

def main():
    """메인 함수"""
    # 명령줄 인자 파싱
    parser = create_argument_parser()
    args = parser.parse_args()
    
    # 필요한 폴더들 생성
    Config.create_folders()
    
    # 배너 출력
    print_banner()
    
    # 프로파일 목록 표시
    if args.list_profiles:
        list_profiles()
        return
    
    # 설정 표시
    if args.config:
        show_config()
        return
    
    # 입력이 제공된 경우
    if args.input:
        input_path = Path(args.input)
        
        if args.batch or input_path.is_dir():
            # 일괄 처리 모드
            process_batch(input_path, args)
        else:
            # 단일 파일 처리
            process_single_pdf(input_path, args)
    else:
        # 폴더 모니터링 모드 (기본)
        print("📂 폴더 모니터링 모드로 시작합니다...")
        print(f"PDF 파일을 '{Config.INPUT_FOLDER}' 폴더에 넣어주세요.")
        print(f"프리플라이트 프로파일: {args.monitor_profile}")
        print(f"다른 프로파일을 사용하려면: python main.py --monitor-profile [프로파일명]\n")
        
        # 기존 파일 처리 확인
        check_existing_files(preflight_profile=args.monitor_profile)
        
        # 모니터링 시작
        monitor = PDFMonitor(preflight_profile=args.monitor_profile)
        monitor.start()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 프로그램을 종료합니다.")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ 예상치 못한 오류가 발생했습니다: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
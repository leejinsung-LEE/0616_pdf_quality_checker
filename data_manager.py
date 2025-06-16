# data_manager.py - 통합 데이터 관리 시스템
# PDF 처리 이력과 통계를 SQLite 데이터베이스로 관리
# 처리 패턴 분석 및 통계 제공

"""
data_manager.py - 통합 데이터 관리 시스템
처리 이력 저장, 통계 분석, 패턴 찾기 기능
"""

import sqlite3
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import json
from collections import defaultdict, Counter
import statistics

class DataManager:
    """PDF 처리 데이터 관리 클래스"""
    
    def __init__(self, db_path: str = "pdf_checker_history.db"):
        """
        데이터 매니저 초기화
        
        Args:
            db_path: 데이터베이스 파일 경로
        """
        self.db_path = Path(db_path)
        self._init_database()
    
    def _init_database(self):
        """데이터베이스 초기화 및 테이블 생성"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # 메인 처리 기록 테이블
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS processing_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_name TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    file_size INTEGER,
                    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    processing_time REAL,  -- 처리 소요 시간 (초)
                    profile TEXT,          -- 사용된 프로파일
                    
                    -- 기본 정보
                    page_count INTEGER,
                    pdf_version TEXT,
                    
                    -- 검사 결과 요약
                    total_issues INTEGER DEFAULT 0,
                    error_count INTEGER DEFAULT 0,
                    warning_count INTEGER DEFAULT 0,
                    info_count INTEGER DEFAULT 0,
                    
                    -- 주요 지표
                    max_ink_coverage REAL,
                    avg_ink_coverage REAL,
                    font_count INTEGER,
                    not_embedded_fonts INTEGER,
                    image_count INTEGER,
                    low_res_images INTEGER,
                    has_rgb_colors BOOLEAN,
                    has_spot_colors BOOLEAN,
                    spot_color_count INTEGER,
                    
                    -- 프리플라이트 결과
                    preflight_status TEXT,  -- pass, warning, fail
                    
                    -- 자동 수정
                    auto_fix_applied BOOLEAN DEFAULT 0,
                    auto_fix_types TEXT,    -- JSON 배열
                    
                    -- 전체 분석 결과 (JSON)
                    full_result TEXT
                )
            """)
            
            # 문제점 상세 테이블
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS issue_details (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    history_id INTEGER NOT NULL,
                    issue_type TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    message TEXT,
                    affected_pages TEXT,  -- JSON 배열
                    additional_info TEXT, -- JSON 객체
                    
                    FOREIGN KEY (history_id) REFERENCES processing_history(id)
                )
            """)
            
            # 자동 수정 내역 테이블
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS fix_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    history_id INTEGER NOT NULL,
                    fix_type TEXT NOT NULL,
                    fix_description TEXT,
                    before_state TEXT,
                    after_state TEXT,
                    success BOOLEAN DEFAULT 1,
                    
                    FOREIGN KEY (history_id) REFERENCES processing_history(id)
                )
            """)
            
            # 인덱스 생성 (검색 성능 향상)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_file_name 
                ON processing_history(file_name)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_processed_at 
                ON processing_history(processed_at)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_issue_type 
                ON issue_details(issue_type)
            """)
            
            conn.commit()
    
    def save_analysis_result(self, analysis_result: Dict) -> int:
        """
        분석 결과를 데이터베이스에 저장
        
        Args:
            analysis_result: PDFAnalyzer의 분석 결과
            
        Returns:
            int: 저장된 레코드의 ID
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # 기본 정보 추출
            basic_info = analysis_result.get('basic_info', {})
            colors = analysis_result.get('colors', {})
            fonts = analysis_result.get('fonts', {})
            images = analysis_result.get('images', {})
            ink = analysis_result.get('ink_coverage', {}).get('summary', {})
            preflight = analysis_result.get('preflight_result', {})
            issues = analysis_result.get('issues', [])
            
            # 이슈 카운트
            error_count = sum(1 for i in issues if i.get('severity') == 'error')
            warning_count = sum(1 for i in issues if i.get('severity') == 'warning')
            info_count = sum(1 for i in issues if i.get('severity') == 'info')
            
            # 폰트 카운트
            not_embedded = sum(1 for f in fonts.values() if not f.get('embedded', False))
            
            # 자동 수정 정보
            auto_fix_applied = 'auto_fix_applied' in analysis_result
            auto_fix_types = json.dumps(analysis_result.get('auto_fix_applied', []))
            
            # 메인 레코드 삽입
            cursor.execute("""
                INSERT INTO processing_history (
                    file_name, file_path, file_size, processing_time,
                    profile, page_count, pdf_version,
                    total_issues, error_count, warning_count, info_count,
                    max_ink_coverage, avg_ink_coverage,
                    font_count, not_embedded_fonts,
                    image_count, low_res_images,
                    has_rgb_colors, has_spot_colors, spot_color_count,
                    preflight_status,
                    auto_fix_applied, auto_fix_types,
                    full_result
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                analysis_result.get('filename'),
                analysis_result.get('file_path'),
                analysis_result.get('file_size'),
                float(analysis_result.get('analysis_time', '0').replace('초', '')),
                analysis_result.get('preflight_profile'),
                basic_info.get('page_count'),
                basic_info.get('pdf_version'),
                len(issues),
                error_count,
                warning_count,
                info_count,
                ink.get('max_coverage'),
                ink.get('avg_coverage'),
                len(fonts),
                not_embedded,
                images.get('total_count'),
                images.get('low_resolution_count'),
                colors.get('has_rgb'),
                colors.get('has_spot_colors'),
                len(colors.get('spot_color_names', [])),
                preflight.get('overall_status'),
                auto_fix_applied,
                auto_fix_types,
                json.dumps(analysis_result, ensure_ascii=False)
            ))
            
            history_id = cursor.lastrowid
            
            # 이슈 상세 정보 저장
            for issue in issues:
                cursor.execute("""
                    INSERT INTO issue_details (
                        history_id, issue_type, severity, message,
                        affected_pages, additional_info
                    ) VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    history_id,
                    issue.get('type'),
                    issue.get('severity'),
                    issue.get('message'),
                    json.dumps(issue.get('affected_pages', [])),
                    json.dumps({
                        k: v for k, v in issue.items() 
                        if k not in ['type', 'severity', 'message', 'affected_pages']
                    })
                ))
            
            # 자동 수정 내역 저장
            if 'fix_comparison' in analysis_result:
                comparison = analysis_result['fix_comparison']
                for modification in comparison.get('modifications', []):
                    cursor.execute("""
                        INSERT INTO fix_history (
                            history_id, fix_type, fix_description,
                            before_state, after_state
                        ) VALUES (?, ?, ?, ?, ?)
                    """, (
                        history_id,
                        modification,
                        modification,
                        json.dumps(comparison.get('before', {})),
                        json.dumps(comparison.get('after', {}))
                    ))
            
            conn.commit()
            return history_id
    
    def get_statistics(self, date_range: Optional[Tuple[datetime, datetime]] = None) -> Dict:
        """
        통계 정보 조회
        
        Args:
            date_range: 조회 기간 (시작일, 종료일) 튜플. None이면 전체 기간
            
        Returns:
            dict: 각종 통계 정보
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # 기본 WHERE 절
            where_clause = ""
            params = []
            
            if date_range:
               where_clause = "WHERE processed_at BETWEEN ? AND ?"
               # isoformat() 대신 strftime 사용하여 SQLite 형식에 맞춤
            params = [
            date_range[0].strftime('%Y-%m-%d %H:%M:%S'), 
            date_range[1].strftime('%Y-%m-%d %H:%M:%S')
            ]
            
            # 기본 통계
            cursor.execute(f"""
                SELECT 
                    COUNT(*) as total_files,
                    SUM(page_count) as total_pages,
                    AVG(processing_time) as avg_processing_time,
                    SUM(error_count) as total_errors,
                    SUM(warning_count) as total_warnings,
                    SUM(auto_fix_applied) as auto_fixed_count
                FROM processing_history
                {where_clause}
            """, params)
            
            basic_stats = cursor.fetchone()
            
            # 이슈 타입별 통계
            cursor.execute(f"""
                SELECT 
                    issue_type,
                    severity,
                    COUNT(*) as count
                FROM issue_details
                JOIN processing_history ON issue_details.history_id = processing_history.id
                {where_clause}
                GROUP BY issue_type, severity
                ORDER BY count DESC
            """, params)
            
            issue_stats = cursor.fetchall()
            
            # 프리플라이트 통계
            cursor.execute(f"""
                SELECT 
                    preflight_status,
                    COUNT(*) as count
                FROM processing_history
                {where_clause}
                GROUP BY preflight_status
            """, params)
            
            preflight_stats = cursor.fetchall()
            
            # 일별 처리량
            cursor.execute(f"""
                SELECT 
                    DATE(processed_at) as date,
                    COUNT(*) as count,
                    SUM(page_count) as pages
                FROM processing_history
                {where_clause}
                GROUP BY DATE(processed_at)
                ORDER BY date DESC
                LIMIT 7
            """, params)
            
            daily_stats = cursor.fetchall()
            
            # 가장 흔한 문제
            cursor.execute(f"""
                SELECT 
                    issue_type,
                    COUNT(*) as count,
                    COUNT(DISTINCT history_id) as affected_files
                FROM issue_details
                JOIN processing_history ON issue_details.history_id = processing_history.id
                {where_clause}
                GROUP BY issue_type
                ORDER BY count DESC
                LIMIT 10
            """, params)
            
            common_issues = cursor.fetchall()
            
            # 자동 수정 통계
            cursor.execute(f"""
                SELECT 
                    fix_type,
                    COUNT(*) as count,
                    SUM(success) as success_count
                FROM fix_history
                JOIN processing_history ON fix_history.history_id = processing_history.id
                {where_clause}
                GROUP BY fix_type
            """, params)
            
            fix_stats = cursor.fetchall()
            
            return {
                'basic': {
                    'total_files': basic_stats[0] or 0,
                    'total_pages': basic_stats[1] or 0,
                    'avg_processing_time': basic_stats[2] or 0,
                    'total_errors': basic_stats[3] or 0,
                    'total_warnings': basic_stats[4] or 0,
                    'auto_fixed_count': basic_stats[5] or 0
                },
                'issues_by_type': [
                    {'type': row[0], 'severity': row[1], 'count': row[2]}
                    for row in issue_stats
                ],
                'preflight': dict(preflight_stats),
                'daily': [
                    {'date': row[0], 'files': row[1], 'pages': row[2]}
                    for row in daily_stats
                ],
                'common_issues': [
                    {'type': row[0], 'count': row[1], 'affected_files': row[2]}
                    for row in common_issues
                ],
                'auto_fixes': [
                    {'type': row[0], 'count': row[1], 'success': row[2]}
                    for row in fix_stats
                ]
            }
    
    def get_file_history(self, filename: str) -> List[Dict]:
        """
        특정 파일의 처리 이력 조회
        
        Args:
            filename: 파일명
            
        Returns:
            list: 처리 이력 목록
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT 
                    id, processed_at, processing_time, profile,
                    page_count, error_count, warning_count,
                    preflight_status, auto_fix_applied
                FROM processing_history
                WHERE file_name = ?
                ORDER BY processed_at DESC
            """, (filename,))
            
            history = []
            for row in cursor.fetchall():
                history_id = row[0]
                
                # 이슈 상세 조회
                cursor.execute("""
                    SELECT issue_type, severity, COUNT(*)
                    FROM issue_details
                    WHERE history_id = ?
                    GROUP BY issue_type, severity
                """, (history_id,))
                
                issues = cursor.fetchall()
                
                history.append({
                    'id': history_id,
                    'processed_at': row[1],
                    'processing_time': row[2],
                    'profile': row[3],
                    'page_count': row[4],
                    'error_count': row[5],
                    'warning_count': row[6],
                    'preflight_status': row[7],
                    'auto_fix_applied': bool(row[8]),
                    'issues': [
                        {'type': i[0], 'severity': i[1], 'count': i[2]}
                        for i in issues
                    ]
                })
            
            return history
    
    def find_common_patterns(self) -> Dict:
        """
        일반적인 문제 패턴 찾기
        
        Returns:
            dict: 패턴 분석 결과
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            patterns = {}
            
            # 1. 가장 흔한 문제 조합
            cursor.execute("""
                SELECT 
                    GROUP_CONCAT(issue_type, ',') as issue_combo,
                    COUNT(*) as count
                FROM (
                    SELECT 
                        history_id,
                        issue_type
                    FROM issue_details
                    WHERE severity = 'error'
                    ORDER BY history_id, issue_type
                )
                GROUP BY history_id
                HAVING COUNT(*) > 1
            """)
            
            issue_combos = defaultdict(int)
            for row in cursor.fetchall():
                if row[0]:
                    issue_combos[row[0]] += 1
            
            patterns['common_issue_combinations'] = [
                {'issues': combo.split(','), 'count': count}
                for combo, count in sorted(issue_combos.items(), 
                                         key=lambda x: x[1], reverse=True)[:5]
            ]
            
            # 2. 시간대별 처리 패턴
            cursor.execute("""
                SELECT 
                    strftime('%H', processed_at) as hour,
                    COUNT(*) as count,
                    AVG(processing_time) as avg_time
                FROM processing_history
                GROUP BY hour
                ORDER BY hour
            """)
            
            patterns['hourly_pattern'] = [
                {'hour': int(row[0]), 'count': row[1], 'avg_time': row[2]}
                for row in cursor.fetchall()
            ]
            
            # 3. 파일 크기와 문제의 상관관계
            cursor.execute("""
                SELECT 
                    CASE 
                        WHEN file_size < 1048576 THEN '< 1MB'
                        WHEN file_size < 5242880 THEN '1-5MB'
                        WHEN file_size < 10485760 THEN '5-10MB'
                        WHEN file_size < 52428800 THEN '10-50MB'
                        ELSE '> 50MB'
                    END as size_range,
                    COUNT(*) as file_count,
                    AVG(error_count) as avg_errors,
                    AVG(processing_time) as avg_time
                FROM processing_history
                GROUP BY size_range
                ORDER BY file_size
            """)
            
            patterns['size_patterns'] = [
                {
                    'range': row[0],
                    'count': row[1],
                    'avg_errors': row[2],
                    'avg_processing_time': row[3]
                }
                for row in cursor.fetchall()
            ]
            
            # 4. 자동 수정 효과성
            cursor.execute("""
                SELECT 
                    auto_fix_types,
                    AVG(
                        CASE 
                            WHEN error_count = 0 THEN 100
                            ELSE (1 - CAST(error_count AS FLOAT) / total_issues) * 100
                        END
                    ) as fix_effectiveness
                FROM processing_history
                WHERE auto_fix_applied = 1
                GROUP BY auto_fix_types
            """)
            
            patterns['auto_fix_effectiveness'] = [
                {'types': json.loads(row[0] or '[]'), 'effectiveness': row[1]}
                for row in cursor.fetchall()
            ]
            
            # 5. 프로파일별 성공률
            cursor.execute("""
                SELECT 
                    profile,
                    COUNT(*) as total,
                    SUM(CASE WHEN preflight_status = 'pass' THEN 1 ELSE 0 END) as passed,
                    AVG(processing_time) as avg_time
                FROM processing_history
                GROUP BY profile
            """)
            
            patterns['profile_stats'] = [
                {
                    'profile': row[0],
                    'total': row[1],
                    'pass_rate': (row[2] / row[1] * 100) if row[1] > 0 else 0,
                    'avg_time': row[3]
                }
                for row in cursor.fetchall()
            ]
            
            return patterns
    
    def get_recent_files(self, limit: int = 10) -> List[Dict]:
        """
        최근 처리한 파일 목록 조회
        
        Args:
            limit: 조회할 파일 수
            
        Returns:
            list: 최근 파일 목록
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT 
                    file_name, file_path, processed_at,
                    page_count, error_count, warning_count,
                    preflight_status, auto_fix_applied
                FROM processing_history
                ORDER BY processed_at DESC
                LIMIT ?
            """, (limit,))
            
            return [
                {
                    'filename': row[0],
                    'filepath': row[1],
                    'processed_at': row[2],
                    'page_count': row[3],
                    'error_count': row[4],
                    'warning_count': row[5],
                    'status': row[6],
                    'auto_fixed': bool(row[7])
                }
                for row in cursor.fetchall()
            ]
    
    def search_files(self, 
                     filename_pattern: Optional[str] = None,
                     date_from: Optional[datetime] = None,
                     date_to: Optional[datetime] = None,
                     issue_type: Optional[str] = None,
                     min_errors: Optional[int] = None) -> List[Dict]:
        """
        조건에 따른 파일 검색
        
        Args:
            filename_pattern: 파일명 패턴 (와일드카드 지원)
            date_from: 시작일
            date_to: 종료일
            issue_type: 특정 이슈 타입
            min_errors: 최소 오류 개수
            
        Returns:
            list: 검색 결과
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # 동적 쿼리 구성
            query = """
                SELECT DISTINCT
                    h.id, h.file_name, h.file_path, h.processed_at,
                    h.page_count, h.error_count, h.warning_count,
                    h.preflight_status
                FROM processing_history h
            """
            
            conditions = []
            params = []
            
            # 이슈 타입 조건이 있으면 JOIN
            if issue_type:
                query += " JOIN issue_details i ON h.id = i.history_id"
                conditions.append("i.issue_type = ?")
                params.append(issue_type)
            
            # 조건 추가
            if filename_pattern:
                conditions.append("h.file_name LIKE ?")
                params.append(f"%{filename_pattern}%")
            
            if date_from:
                conditions.append("h.processed_at >= ?")
                params.append(date_from.isoformat())
            
            if date_to:
                conditions.append("h.processed_at <= ?")
                params.append(date_to.isoformat())
            
            if min_errors is not None:
                conditions.append("h.error_count >= ?")
                params.append(min_errors)
            
            # WHERE 절 추가
            if conditions:
                query += " WHERE " + " AND ".join(conditions)
            
            query += " ORDER BY h.processed_at DESC"
            
            cursor.execute(query, params)
            
            return [
                {
                    'id': row[0],
                    'filename': row[1],
                    'filepath': row[2],
                    'processed_at': row[3],
                    'page_count': row[4],
                    'error_count': row[5],
                    'warning_count': row[6],
                    'status': row[7]
                }
                for row in cursor.fetchall()
            ]
    
    def export_statistics_report(self, output_path: str, 
                                date_range: Optional[Tuple[datetime, datetime]] = None):
        """
        통계 리포트를 HTML 파일로 내보내기
        
        Args:
            output_path: 출력 파일 경로
            date_range: 기간 설정
        """
        stats = self.get_statistics(date_range)
        patterns = self.find_common_patterns()
        
        # HTML 리포트 생성
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>PDF 검수 통계 리포트</title>
    <style>
        body {{ font-family: 'Malgun Gothic', sans-serif; margin: 20px; }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        h1, h2 {{ color: #333; }}
        .stat-card {{ 
            background: #f5f5f5; 
            padding: 20px; 
            margin: 10px 0; 
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .stat-value {{ font-size: 2em; font-weight: bold; color: #2196F3; }}
        table {{ 
            width: 100%; 
            border-collapse: collapse; 
            margin: 20px 0;
        }}
        th, td {{ 
            padding: 10px; 
            text-align: left; 
            border-bottom: 1px solid #ddd;
        }}
        th {{ background: #f0f0f0; font-weight: bold; }}
        .chart {{ margin: 20px 0; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>PDF 검수 시스템 통계 리포트</h1>
        <p>생성일시: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        
        <h2>기본 통계</h2>
        <div class="stat-card">
            <div>총 처리 파일: <span class="stat-value">{stats['basic']['total_files']}</span>개</div>
            <div>총 페이지 수: <span class="stat-value">{stats['basic']['total_pages']}</span>페이지</div>
            <div>평균 처리 시간: <span class="stat-value">{stats['basic']['avg_processing_time']:.1f}</span>초</div>
            <div>자동 수정 적용: <span class="stat-value">{stats['basic']['auto_fixed_count']}</span>건</div>
        </div>
        
        <h2>일별 처리량 (최근 7일)</h2>
        <table>
            <tr><th>날짜</th><th>파일 수</th><th>페이지 수</th></tr>
            {''.join(f"<tr><td>{d['date']}</td><td>{d['files']}</td><td>{d['pages']}</td></tr>" 
                     for d in stats['daily'])}
        </table>
        
        <h2>가장 흔한 문제</h2>
        <table>
            <tr><th>문제 유형</th><th>발생 횟수</th><th>영향받은 파일</th></tr>
            {''.join(f"<tr><td>{i['type']}</td><td>{i['count']}</td><td>{i['affected_files']}</td></tr>" 
                     for i in stats['common_issues'])}
        </table>
        
        <h2>프로파일별 성공률</h2>
        <table>
            <tr><th>프로파일</th><th>처리 수</th><th>성공률</th><th>평균 시간</th></tr>
            {''.join(f"<tr><td>{p['profile']}</td><td>{p['total']}</td><td>{p['pass_rate']:.1f}%</td><td>{p['avg_time']:.1f}초</td></tr>" 
                     for p in patterns['profile_stats'])}
        </table>
    </div>
</body>
</html>
        """
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)

# 테스트 코드
if __name__ == "__main__":
    # 데이터 매니저 생성
    dm = DataManager()
    
    # 테스트 데이터
    test_result = {
        'filename': 'test.pdf',
        'file_path': '/path/to/test.pdf',
        'file_size': 1024000,
        'analysis_time': '5.2초',
        'preflight_profile': 'offset',
        'basic_info': {
            'page_count': 10,
            'pdf_version': '1.7'
        },
        'issues': [
            {'type': 'font_not_embedded', 'severity': 'error', 'message': '폰트 미임베딩'},
            {'type': 'low_resolution_image', 'severity': 'warning', 'message': '저해상도 이미지'}
        ]
    }
    
    # 저장 테스트
    print("데이터 저장 중...")
    history_id = dm.save_analysis_result(test_result)
    print(f"저장 완료! ID: {history_id}")
    
    # 통계 조회
    print("\n통계 정보:")
    stats = dm.get_statistics()
    print(f"총 파일: {stats['basic']['total_files']}")
    print(f"총 오류: {stats['basic']['total_errors']}")
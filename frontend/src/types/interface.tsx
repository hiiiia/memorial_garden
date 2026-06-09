// ==========================================
// 공통 및 하위 도메인 인터페이스
// ==========================================



// (App.tsx에서 받아온 리모컨)
export interface LoginPageProps {
  setIsLoggedIn: (value: boolean) => void;
}


export interface SeniorStatus {
  name: string;
  status: string;
}

export interface TodayCondition {
  state: string;       // 'good', 'normal', 'bad'
  label: string;       // '안정', '주의', '위험'
  description: string; // 실시간 요약 문구
  color_code: string;  // 상태별 테마 색상 상수 (#388E3C 등)
}

export interface RiskAssessment {
  score: number;
  level: string;       // '낮음', '보통', '위험'
  status_text: string; // AI 분석 안내 문구
}

export interface LastInteraction {
  time_label: string;     // '오늘 오전 09:12' 등
  duration_label: string; // 'AI와 대화 완료' 등
}

export interface RecentAlert {
  id: number;
  content: string;
  time_ago: string;
  type: string;        // 'info', 'success', 'warning'
}

export interface TrendData {
  date: string;        // '06.03' 형태의 차트 축 레이블
  score: number;       // 해당 날짜의 위험도 점수
}


export interface HealthData { 
    id: number; 
    date: string; 
    depressionScore: number; 
    dementiaScore: number; 
    insight: string; 
}


// ==========================================
// 페이지별 핵심 API 응답 인터페이스
// ==========================================

// 1. 메인 대시보드 조회 (/dashboard)
export interface DashboardData {
  guardian_name: string;
  senior: SeniorStatus;
  today_condition: TodayCondition;
  risk_assessment: RiskAssessment;
  last_interaction: LastInteraction;
  recent_alerts: RecentAlert[];
}

// 2. 그림일기 단건 상세 조회 (/diary)
export interface DiaryData {
  log_id: string;
  date: string;
  image_url: string;
  primary_emotion: string;
  stt_text: string;
  reply_text: string;
  summary: string;
  keywords: string[];
}

// 3. 주간 위험도 추이 분석 조회 (/analysis)
export interface AnalysisData {
  trend_data: TrendData[];
  average_score: number;
  insight: string;
}

// 4. 어르신 아이디 검색 결과 (/dependents/search)
export interface SeniorInfo {
  id: string;
  username: string;
  name: string;
  join_date: string;
  last_active: string;
}

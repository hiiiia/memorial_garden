// src/pages/DashboardPage.tsx

import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import Calendar from 'react-calendar';
import 'react-calendar/dist/Calendar.css';
import '../css/CustomCalendar.css';
import '../css/DashboardPage.css'; // 
import '../css/MainPage.css';

import { config } from '../config'; // API 주소 세팅
// --- 인터페이스 정의 ---
interface DashboardData {
  guardian_name: string;
  senior: { name: string; status: string };
  today_condition: { state: string; label: string; description: string; color_code: string };
  risk_assessment: { score: number; level: string; status_text: string };
  last_interaction: { time_label: string; duration_label: string };
  recent_alerts: { id: number; content: string; time_ago: string; type: string }[];
}

interface DiaryData { id: number; date: string; imageUrl: string; content: string; keywords: string[]; }
interface HealthData { id: number; date: string; depressionScore: number; dementiaScore: number; insight: string; }

// --- 가상 데이터 (추후 백엔드 API로 교체) ---
const mockDiaryData: DiaryData[] = [
  { id: 1, date: "2026-06-05", imageUrl: "https://images.unsplash.com/photo-1490730141103-6cac27aaab94?auto=format&fit=crop&w=800&q=80", content: "오늘은 어린 시절 동네 어귀에서 친구들과 뛰놀던 기억을 떠올리셨어요...", keywords: ["어린시절", "골목길", "그리움"] },
];
const mockHealthData: HealthData[] = [
  { id: 1, date: "2026-06-05", depressionScore: 15, dementiaScore: 8, insight: "최근 일주일 대비 발화 속도와 어휘 다양성이 매우 안정적입니다." },
];

const DashboardPage = () => {
  const navigate = useNavigate();
  
  // 1. 대시보드 상태 관리
  const [dashData, setDashData] = useState<DashboardData | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string>('');

  // 2. 하단 달력/탭 상태 관리
  const [activeTab, setActiveTab] = useState<'diary' | 'report'>('diary');
  const [selectedDate, setSelectedDate] = useState<Date>(new Date(2026, 5, 5)); // 2026년 6월 5일 기준 (임시)

  // API 데이터 호출
  useEffect(() => {
    const fetchDashboard = async () => {
      try {
        const token = localStorage.getItem('access_token');
        const guardianInfoStr = localStorage.getItem('guardian_info');
        
        if (!token || !guardianInfoStr) {
          setError('로그인이 필요합니다.');
          setIsLoading(false);
          return;
        }

        const guardianInfo = JSON.parse(guardianInfoStr);
        const guardianId = guardianInfo.id;
        const targetUserId = 'USER_ABC'; 
        const currentDate = new Date().toISOString();

        // const response = await fetch(
        //   `${config.apiBaseUrl}/guardian/${guardianId}/dashboard?user_id=${targetUserId}&date=${currentDate}`,
        //   {
        //     method: 'GET',
        //     headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` }
        //   }
        // );

        
        // // =================================================================
        // 🚨 원래 있던 fetch 로직을 잠시 주석 처리하거나 지웁니다.
        // 테스트용테스트용테스트용테스트용테스트용테스트용테스트용테스트용테스트용테스트용테스트용
        // 테스트용테스트용테스트용테스트용테스트용테스트용테스트용테스트용테스트용테스트용테스트용테스트용
        // 테스트용테스트용테스트용테스트용테스트용테스트용테스트용테스트용테스트용테스트용테스트용테스트용
        // 테스트용테스트용테스트용테스트용테스트용테스트용테스트용테스트용테스트용테스트용테스트용테스트용
        // 테스트용테스트용테스트용테스트용테스트용테스트용테스트용테스트용테스트용테스트용테스트용테스트용

        // =================================================================

        // 1. 임시 데이터를 객체로 만듭니다.
        const dummyData = {
          guardian_name: "가족", 
          senior: { name: "김영희", status: "연동 중" },
          today_condition: { 
            state: "good", 
            label: "안정", 
            description: "특이사항이 없습니다.", 
            color_code: "#388E3C" 
          },
          risk_assessment: { 
            score: 32, 
            level: "낮음", 
            status_text: "안정적인 상태입니다." 
          },
          last_interaction: { 
            time_label: "오늘 오전 9:12", 
            duration_label: "AI와 15분 대화" 
          },
          recent_alerts: [
            { id: 1, content: "오늘 일기가 공유되었습니다.", time_ago: "오전 9:15", type: "info" },
            { id: 2, content: "위험도 변동이 없습니다.", time_ago: "어제", type: "success" },
            { id: 3, content: "도움 요청이 없습니다.", time_ago: "어제", type: "success" }
          ]
        };

        // 2. .json() 변환 과정 없이 곧바로 State에 집어넣습니다!
        setDashData(dummyData);
        setIsLoading(false);

        // 테스트용테스트용테스트용테스트용테스트용테스트용테스트용테스트용테스트용테스트용테스트용테스트용
        // 테스트용테스트용테스트용테스트용테스트용테스트용테스트용테스트용테스트용테스트용테스트용테스트용
        // 테스트용테스트용테스트용테스트용테스트용테스트용테스트용테스트용테스트용테스트용테스트용테스트용
        // 테스트용테스트용테스트용테스트용테스트용테스트용테스트용테스트용테스트용테스트용테스트용테스트용
        // 테스트용테스트용테스트용테스트용테스트용테스트용테스트용테스트용테스트용테스트용테스트용테스트용
        

        // const result = await response.json();
        // if (response.ok && result.code === 200) {
        //   setDashData(result.data);
        // } else {
        //   setError(result.error || '데이터를 불러오지 못했습니다.');
        // }
      } catch (err) {
        setError('서버와의 통신에 실패했습니다.');
      } finally {
        setIsLoading(false);
      }
    };
    fetchDashboard();
  }, []);

  // 날짜 변환 및 데이터 필터링
  const formatYYYYMMDD = (date: Date) => {
    const offset = date.getTimezoneOffset() * 60000;
    return new Date(date.getTime() - offset).toISOString().split('T')[0];
  };

  const selectedDateStr = formatYYYYMMDD(selectedDate);
  const filteredDiary = mockDiaryData.find(d => d.date === selectedDateStr);
  const filteredHealth = mockHealthData.find(d => d.date === selectedDateStr);

  const getAlertIcon = (type: string) => type === 'warning' ? '🔴' : type === 'info' ? '🟡' : '🟢';
  const getConditionIcon = (state: string) => state === 'good' ? '🙂' : state === 'bad' ? '😥' : '😐';

  if (isLoading) return <div style={{ padding: '50px', textAlign: 'center', color: '#888' }}>대시보드를 준비 중입니다...</div>;
  if (error || !dashData) return <div style={{ padding: '50px', textAlign: 'center', color: '#E57373' }}>{error}</div>;

  return (
    <div className="dashboard-container" style={{ paddingBottom: '80px' }}>
      <div className="dashboard-content">
        
        {/* =========================================
            SECTION 1: 실시간 대시보드 요약 (기존 DashboardPage 영역)
            ========================================= */}
        <header className="dashboard-header">
          <div className="header-left">
            <h1 className="header-title">안녕하세요, {dashData.guardian_name}님!</h1>
            <p className="header-subtitle">연동된 가족의 실시간 상태를 확인하세요.</p>
          </div>
          <div className="header-profile">
            <div className="profile-avatar">👵🏻</div>
            <div className="profile-info">
              <p className="profile-name">{dashData.senior.name}님</p>
              <p className="profile-status">{dashData.senior.status}</p>
            </div>
          </div>
        </header>

        {/* 상단 3개 카드 */}
        <div className="card-grid-top">
          <div className="dashboard-card" style={{ borderTop: `4px solid ${dashData.today_condition.color_code}` }}>
            <h3 className="card-title">오늘의 상태</h3>
            <div className="status-content">
              <span className="status-icon">{getConditionIcon(dashData.today_condition.state)}</span>
              <span className="status-text" style={{ color: dashData.today_condition.color_code }}>{dashData.today_condition.label}</span>
            </div>
            <p className="card-subtext">{dashData.today_condition.description}</p>
          </div>
          <div className="dashboard-card interactive" onClick={() => navigate('/analysis')}>
            <h3 className="card-title">위험도 <span style={{fontSize:'12px', fontWeight:'normal', color:'#888'}}>(자세히 보기 ↗)</span></h3>
            <h2 className="score-text">{dashData.risk_assessment.score}점</h2>
            <p className="score-label">{dashData.risk_assessment.level}</p>
            <p className="card-subtext">{dashData.risk_assessment.status_text}</p>
          </div>
          <div className="dashboard-card interactive" onClick={() => navigate('/diary')}>
            <h3 className="card-title">마지막 대화 <span style={{fontSize:'12px', fontWeight:'normal', color:'#888'}}>(오늘 일기 ↗)</span></h3>
            <div className="time-text">{dashData.last_interaction.time_label}</div>
            <p className="card-subtext">{dashData.last_interaction.duration_label}</p>
          </div>
        </div>

        {/* =========================================
            SECTION 2: 과거 기록 달력 및 상세 탭 (기존 MainPage 영역)
            ========================================= */}
        <div style={{ marginTop: '50px', marginBottom: '20px', borderTop: '2px dashed #EAE5D9', paddingTop: '40px' }}>
          <h2 style={{ fontSize: '20px', fontWeight: 'bold', marginBottom: '10px' }}>지난 기록 찾아보기</h2>
          <p style={{ fontSize: '14px', color: '#888', marginBottom: '30px' }}>날짜를 선택하여 과거의 그림일기와 건강 지표를 확인해보세요.</p>
        </div>

        <div className="calendar-wrapper">
          <Calendar 
            onChange={(value: any) => setSelectedDate(value as Date)} 
            value={selectedDate}
            formatDay={(locale: string | undefined, date: Date) => date.getDate().toString()}
            tileContent={({ date, view }: { date: Date; view: string }) => {
              if (view === 'month' && mockDiaryData.some(d => d.date === formatYYYYMMDD(date))) {
                return (
                  <div style={{ display: 'flex', justifyContent: 'center', marginTop: '2px' }}>
                    <div style={{ width: '6px', height: '6px', backgroundColor: '#7A8B5F', borderRadius: '50%' }} />
                  </div>
                );
              }
              return null;
            }}
          />
        </div>

        <div className="tab-container">
          <button onClick={() => setActiveTab('diary')} className={`tab-button ${activeTab === 'diary' ? 'active' : 'inactive'}`}>
            📖 {selectedDate.getDate()}일 그림일기
          </button>
          <button onClick={() => setActiveTab('report')} className={`tab-button ${activeTab === 'report' ? 'active' : 'inactive'}`}>
            🩺 마음 건강 지표
          </button>
        </div>

        <div>
          {!filteredDiary && !filteredHealth && (
            <div className="empty-state">해당 날짜에는 기록된 데이터가 없습니다.</div>
          )}

          {activeTab === 'diary' && filteredDiary && (
            <div className="diary-card interactive" onClick={() => navigate('/diary')}>
              <img src={filteredDiary.imageUrl} alt="AI 그림일기" className="diary-img" />
              <div className="diary-content-box">
                <p className="diary-text">{filteredDiary.content}</p>
                <div className="keyword-container">
                  {filteredDiary.keywords.map((kw, idx) => (
                    <span key={idx} className="keyword-tag">#{kw}</span>
                  ))}
                </div>
                <div className="view-detail-link">전체 일기 및 감정 분석 보기 →</div>
              </div>
            </div>
          )}

          {activeTab === 'report' && filteredHealth && (
            <div className="report-card interactive" onClick={() => navigate('/analysis')}>
              <div className="score-section">
                <div className="score-header">
                  <span className="score-title">우울/고립감 지수</span>
                  <span className={`score-value ${filteredHealth.depressionScore > 50 ? 'high' : 'normal'}`}>{filteredHealth.depressionScore}점</span>
                </div>
                <div className="progress-bar-bg">
                  <div className={`progress-bar-fill ${filteredHealth.depressionScore > 50 ? 'high' : 'normal'}`} style={{ width: `${filteredHealth.depressionScore}%` }} />
                </div>
              </div>
              <div className="score-section">
                <div className="score-header">
                  <span className="score-title">인지 저하(치매) 징후 스코어</span>
                  <span className={`score-value ${filteredHealth.dementiaScore > 50 ? 'high' : 'normal'}`}>{filteredHealth.dementiaScore}점</span>
                </div>
                <div className="progress-bar-bg">
                  <div className={`progress-bar-fill ${filteredHealth.dementiaScore > 50 ? 'high' : 'normal'}`} style={{ width: `${filteredHealth.dementiaScore}%` }} />
                </div>
              </div>
              <div className="insight-box">
                <p className="insight-text"><strong>💡 주치의 AI 소견:</strong><br/>{filteredHealth.insight}</p>
              </div>
              <div className="view-detail-link">7일간 변화 및 추천 행동 보기 →</div>
            </div>
          )}
        </div>

      </div>
    </div>
  );
};

export default DashboardPage;
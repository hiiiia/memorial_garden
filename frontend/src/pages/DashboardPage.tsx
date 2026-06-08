// src/pages/DashboardPage.tsx

import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import Calendar from 'react-calendar';
import 'react-calendar/dist/Calendar.css';
import '../css/CustomCalendar.css';
import '../css/DashboardPage.css'; 
import '../css/MainPage.css';

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

// 하단 달력용 임시 데이터
const mockDiaryData: DiaryData[] = [
  { id: 1, date: "2026-06-05", imageUrl: "https://images.unsplash.com/photo-1490730141103-6cac27aaab94?auto=format&fit=crop&w=800&q=80", content: "오늘은 어린 시절 동네 어귀에서 친구들과 뛰놀던 기억을 떠올리셨어요...", keywords: ["어린시절", "골목길", "그리움"] },
];
const mockHealthData: HealthData[] = [
  { id: 1, date: "2026-06-05", depressionScore: 15, dementiaScore: 8, insight: "최근 일주일 대비 발화 속도와 어휘 다양성이 매우 안정적입니다." },
];

const DashboardPage = () => {
  const navigate = useNavigate();
  
  // 상태 관리
  const [dashData, setDashData] = useState<DashboardData | null>(null);
  const [pendingSenior, setPendingSenior] = useState<{ name: string } | null>(null); // 🌟 대기 중인 어르신 정보
  const [isLoading, setIsLoading] = useState<boolean>(true);

  const [activeTab, setActiveTab] = useState<'diary' | 'report'>('diary');
  const [selectedDate, setSelectedDate] = useState<Date>(new Date(2026, 5, 5)); 

  // 데이터 호출 (Mock 데이터 활용)
  useEffect(() => {
    // UI 테스트용 스위치 (아래 3개 중 하나로 변경해보세요)
    // 'none': 아무것도 없는 빈 화면
    // 'pending': 수락 대기 중 화면
    // 'linked': 연동 완료된 정상 대시보드
    var testStatus: 'none' | 'pending' | 'linked' = 'pending'; 

    setTimeout(() => {
      if (testStatus === 'linked') {
        setDashData({
          guardian_name: "가족", 
          senior: { name: "김영희", status: "연동 중" }, 
          today_condition: { state: "good", label: "안정", description: "특이사항이 없습니다.", color_code: "#388E3C" },
          risk_assessment: { score: 32, level: "낮음", status_text: "안정적인 상태입니다." },
          last_interaction: { time_label: "오늘 오전 9:12", duration_label: "AI와 15분 대화" },
          recent_alerts: [
            { id: 1, content: "오늘 일기가 공유되었습니다.", time_ago: "오전 9:15", type: "info" },
            { id: 2, content: "위험도 변동이 없습니다.", time_ago: "어제", type: "success" },
            { id: 3, content: "도움 요청이 없습니다.", time_ago: "어제", type: "success" }
          ]
        });
        setPendingSenior(null);
      } else if (testStatus === 'pending') {
        // 연동 요청은 보냈지만 아직 수락하지 않은 상태
        setDashData(null);
        setPendingSenior({ name: "김영희" });
      } else {
        // 아예 연동을 시도조차 안 한 상태
        setDashData(null); 
        setPendingSenior(null);
      }
      setIsLoading(false);
    }, 500); 
  }, []);

  const formatYYYYMMDD = (date: Date) => {
    const offset = date.getTimezoneOffset() * 60000;
    return new Date(date.getTime() - offset).toISOString().split('T')[0];
  };

  const selectedDateStr = formatYYYYMMDD(selectedDate);
  const filteredDiary = mockDiaryData.find(d => d.date === selectedDateStr);
  const filteredHealth = mockHealthData.find(d => d.date === selectedDateStr);

  const getConditionIcon = (state: string) => state === 'good' ? '🙂' : state === 'bad' ? '😥' : '😐';

  // 로딩 화면
  if (isLoading) return <div style={{ padding: '50px', textAlign: 'center', color: '#888' }}>대시보드를 준비 중입니다...</div>;

  // 1. 수락 대기 중 화면 (Pending State)
  if (pendingSenior) {
    return (
      <div className="dashboard-container" style={{ padding: '100px 20px', textAlign: 'center' }}>
        <div style={{ fontSize: '50px', marginBottom: '20px' }}>⏳</div>
        <h2 style={{ color: '#333', marginBottom: '15px' }}>연동 수락 대기 중</h2>
        <div style={{ backgroundColor: '#FFF', border: '1px solid #EAE5D9', borderRadius: '12px', padding: '20px', maxWidth: '400px', margin: '0 auto 30px auto', boxShadow: '0 4px 12px rgba(0,0,0,0.03)' }}>
          <p style={{ color: '#4A4A4A', fontSize: '16px', margin: 0, lineHeight: '1.6' }}>
            <strong style={{ color: '#1B873F' }}>{pendingSenior.name} 어르신</strong> 연동 요청 진행중...<br/>
            어르신이 앱에서 수락하시면<br/>
            실시간 대시보드가 활성화됩니다.
          </p>
        </div>
        <button
          onClick={() => alert('요청을 취소하시겠습니까? (기능 연결 필요)')}
          style={{ backgroundColor: '#FFF', color: '#888', border: '1px solid #CCC', padding: '10px 20px', borderRadius: '8px', fontSize: '14px', cursor: 'pointer', transition: '0.2s' }}
        >
          요청 취소하기
        </button>
      </div>
    );
  }

  //  2. 아예 아무도 연동되지 않은 빈 화면 (Empty State)
  if (!dashData) {
    return (
      <div className="dashboard-container" style={{ padding: '100px 20px', textAlign: 'center' }}>
        <div style={{ fontSize: '50px', marginBottom: '20px' }}>🔗</div>
        <h2 style={{ color: '#333', marginBottom: '10px' }}>아직 연동된 어르신이 없습니다.</h2>
        <p style={{ color: '#888', marginBottom: '30px' }}>어르신 계정을 연동하고 실시간 상태를 확인해보세요.</p>
        <button
          onClick={() => navigate('/register-senior')}
          style={{ backgroundColor: '#7A8B5F', color: '#FFF', border: 'none', padding: '14px 28px', borderRadius: '12px', fontSize: '16px', fontWeight: 'bold', cursor: 'pointer', transition: '0.2s' }}
        >
          어르신 연동하기
        </button>
      </div>
    );
  }

  // 3. 연동이 완료된 정상 대시보드 화면 (Linked State)
  return (
    <div className="dashboard-container" style={{ paddingBottom: '80px' }}>
      <div className="dashboard-content">
        
        {/* 헤더 및 추가 연동 버튼 */}
        <header className="dashboard-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '30px' }}>
          <div className="header-left">
            <h1 className="header-title">안녕하세요, {dashData.guardian_name}님!</h1>
            <p className="header-subtitle">연동된 가족의 실시간 상태를 확인하세요.</p>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '15px' }}>
            <button 
              onClick={() => navigate('/register-senior')}
              style={{ backgroundColor: '#FFF', color: '#7A8B5F', border: '1px solid #7A8B5F', padding: '6px 12px', borderRadius: '8px', fontSize: '13px', fontWeight: 'bold', cursor: 'pointer' }}
            >
              + 연동 추가
            </button>
            <div className="header-profile">
              <div className="profile-avatar" style={{ fontSize: '20px' }}>👵🏻</div>
              <div className="profile-info">
                <p className="profile-name">{dashData.senior.name}님</p>
                <p className="profile-status" style={{ color: '#7A8B5F', fontWeight: 'bold' }}>{dashData.senior.status}</p>
              </div>
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

        {/* 하단 달력 영역 */}
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
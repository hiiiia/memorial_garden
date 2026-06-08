// src/pages/MainPage.tsx
import React, { useEffect, useState } from 'react';
import Calendar from 'react-calendar';
import { useNavigate } from 'react-router-dom';
import 'react-calendar/dist/Calendar.css'; // 라이브러리 기본 CSS
import '../css/CustomCalendar.css'; // 커스텀 달력 CSS
import '../css/MainPage.css'; // 메인 페이지 CSS


interface DiaryData { id: number; date: string; imageUrl: string; content: string; keywords: string[]; }
interface HealthData { id: number; date: string; depressionScore: number; dementiaScore: number; insight: string; }

const mockDiaryData: DiaryData[] = [
  { id: 1, date: "2026-06-05", imageUrl: "https://images.unsplash.com/photo-1490730141103-6cac27aaab94?auto=format&fit=crop&w=800&q=80", content: "오늘은 어린 시절 동네 어귀에서 친구들과 뛰놀던 기억을 떠올리셨어요...", keywords: ["어린시절", "골목길", "그리움"] },
  { id: 2, date: "2026-06-03", imageUrl: "https://images.unsplash.com/photo-1518531933037-91b2f5f229cc?auto=format&fit=crop&w=800&q=80", content: "예전에 즐겨 드시던 시장통 국밥 이야기를 하시며 입맛을 다시셨습니다...", keywords: ["시장국밥", "입맛", "가족식사"] }
];
const mockHealthData: HealthData[] = [
  { id: 1, date: "2026-06-05", depressionScore: 15, dementiaScore: 8, insight: "최근 일주일 대비 발화 속도와 어휘 다양성이 매우 안정적입니다." },
  { id: 2, date: "2026-06-03", depressionScore: 25, dementiaScore: 10, insight: "조금 피곤함을 느끼셨으나 전반적인 인지 논리성은 양호합니다." }
];

const MainPage = () => {
  const navigate = useNavigate(); // 2. 네비게이트 함수 선언
  const [userName, setUserName] = useState<string>('보호자');
  const [activeTab, setActiveTab] = useState<'diary' | 'report'>('diary');
  const [selectedDate, setSelectedDate] = useState<Date>(new Date(2026, 5, 5));

  useEffect(() => {
    const guardianInfoStr = localStorage.getItem('guardian_info');
    if (guardianInfoStr) {
      try {
        const info = JSON.parse(guardianInfoStr);
        if (info.name) setUserName(info.name);
      } catch (e) {}
    }
  }, []);

  const formatYYYYMMDD = (date: Date) => {
    const offset = date.getTimezoneOffset() * 60000;
    const dateOffset = new Date(date.getTime() - offset);
    return dateOffset.toISOString().split('T')[0];
  };

  const selectedDateStr = formatYYYYMMDD(selectedDate);
  const filteredDiary = mockDiaryData.find(d => d.date === selectedDateStr);
  const filteredHealth = mockHealthData.find(d => d.date === selectedDateStr);

  return (
    <div className="main-container">
      <div className="main-content">
        
        <div className="main-header">
          <h1 className="main-title">
            <span className="highlight-text">{userName}</span>님, 평안한 하루 되세요.
          </h1>
        </div>

        {/* 달력 컴포넌트 */}
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

        {/* 탭 네비게이션 */}
        <div className="tab-container">
          <button 
            onClick={() => setActiveTab('diary')} 
            className={`tab-button ${activeTab === 'diary' ? 'active' : 'inactive'}`}
          >
            📖 {selectedDate.getDate()}일 그림일기
          </button>
          <button 
            onClick={() => setActiveTab('report')} 
            className={`tab-button ${activeTab === 'report' ? 'active' : 'inactive'}`}
          >
            🩺 마음 건강 지표
          </button>
        </div>

        {/* 탭 내용 렌더링 */}
        <div>
          {!filteredDiary && !filteredHealth && (
            <div className="empty-state">해당 날짜에는 기록된 데이터가 없습니다.</div>
          )}

          {/* 그림일기 탭 데이터 렌더링 */}
          {activeTab === 'diary' && filteredDiary && (
            // 🌟 3. 카드 클릭 시 /diary 주소로 이동하도록 링크 연결 (interactive 클래스 추가)
            <div className="diary-card interactive" onClick={() => navigate('/diary')}>
              <img src={filteredDiary.imageUrl} alt="AI 그림일기" className="diary-img" />
              <div className="diary-content-box">
                <p className="diary-text">{filteredDiary.content}</p>
                <div className="keyword-container">
                  {filteredDiary.keywords.map((kw, idx) => (
                    <span key={idx} className="keyword-tag">#{kw}</span>
                  ))}
                </div>
                <div className="view-detail-link">자세히 보기 →</div>
              </div>
            </div>
          )}

          {/* 마음 건강 지표 탭 데이터 렌더링 */}
          {activeTab === 'report' && filteredHealth && (
            // 🌟 4. 카드 클릭 시 /analysis 주소로 이동하도록 링크 연결 (interactive 클래스 추가)
            <div className="report-card interactive" onClick={() => navigate('/analysis')}>
              
              <div className="score-section">
                <div className="score-header">
                  <span className="score-title">우울/고립감 지수</span>
                  <span className={`score-value ${filteredHealth.depressionScore > 50 ? 'high' : 'normal'}`}>
                    {filteredHealth.depressionScore}점
                  </span>
                </div>
                <div className="progress-bar-bg">
                  <div 
                    className={`progress-bar-fill ${filteredHealth.depressionScore > 50 ? 'high' : 'normal'}`} 
                    style={{ width: `${filteredHealth.depressionScore}%` }} 
                  />
                </div>
              </div>

              <div className="score-section">
                <div className="score-header">
                  <span className="score-title">인지 저하(치매) 징후 스코어</span>
                  <span className={`score-value ${filteredHealth.dementiaScore > 50 ? 'high' : 'normal'}`}>
                    {filteredHealth.dementiaScore}점
                  </span>
                </div>
                <div className="progress-bar-bg">
                  <div 
                    className={`progress-bar-fill ${filteredHealth.dementiaScore > 50 ? 'high' : 'normal'}`} 
                    style={{ width: `${filteredHealth.dementiaScore}%` }} 
                  />
                </div>
              </div>

              <div className="insight-box">
                <p className="insight-text">
                  <strong>💡 주치의 AI 소견:</strong><br/>
                  {filteredHealth.insight}
                </p>
              </div>
              <div className="view-detail-link">상세 분석 보기 →</div>
            </div>
          )}
        </div>

      </div>
    </div>
  );
};

export default MainPage;
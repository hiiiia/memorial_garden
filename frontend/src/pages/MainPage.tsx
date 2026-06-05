// src/pages/MainPage.tsx
import React, { useEffect, useState } from 'react';
import Calendar from 'react-calendar';
import 'react-calendar/dist/Calendar.css'; // 라이브러리 기본 CSS
import './CustomCalendar.css'; // 🌟 우리가 덮어씌울 예쁜 테마 CSS (아래 3단계에서 만듭니다)

// --- 데이터 타입 및 가상 데이터 (기존과 동일) ---
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
  const [userName, setUserName] = useState<string>('보호자');
  const [activeTab, setActiveTab] = useState<'diary' | 'report'>('diary');
  
  // 달력 상태 관리 (라이브러리는 Date 객체를 사용합니다)
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

  // Date 객체를 'YYYY-MM-DD' 문자열로 변환하는 헬퍼 함수
  const formatYYYYMMDD = (date: Date) => {
    const offset = date.getTimezoneOffset() * 60000;
    const dateOffset = new Date(date.getTime() - offset);
    return dateOffset.toISOString().split('T')[0];
  };

  const selectedDateStr = formatYYYYMMDD(selectedDate);
  const filteredDiary = mockDiaryData.find(d => d.date === selectedDateStr);
  const filteredHealth = mockHealthData.find(d => d.date === selectedDateStr);

  return (
    <div style={{ minHeight: '100vh', backgroundColor: '#FDFBF7', padding: '40px 20px', color: '#4A4A4A' }}>
      <div style={{ maxWidth: '600px', margin: '0 auto' }}>
        
        <div style={{ marginBottom: '30px', textAlign: 'center' }}>
          <h1 style={{ fontSize: '24px', marginBottom: '8px' }}>
            <span style={{ color: '#7A8B5F', fontWeight: 'bold' }}>{userName}</span>님, 평안한 하루 되세요.
          </h1>
        </div>

        {/* 🌟 1. 라이브러리로 교체된 달력 컴포넌트 */}
        <div style={{ marginBottom: '30px', display: 'flex', justifyContent: 'center' }}>
          <Calendar 
            onChange={(value) => setSelectedDate(value as Date)} 
            value={selectedDate}
            formatDay={(locale, date) => date.getDate().toString()} // '일' 글자 빼고 숫자만 표시
            tileContent={({ date, view }) => {
              // 데이터가 있는 날짜에 초록색 마커 추가
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

        {/* 🌟 2. 탭 네비게이션 */}
        <div style={{ display: 'flex', marginBottom: '30px', borderBottom: '2px solid #EAE5D9' }}>
          <button onClick={() => setActiveTab('diary')} style={{ flex: 1, padding: '15px 0', fontSize: '16px', fontWeight: 'bold', cursor: 'pointer', backgroundColor: 'transparent', border: 'none', color: activeTab === 'diary' ? '#7A8B5F' : '#AAAAAA', borderBottom: activeTab === 'diary' ? '3px solid #7A8B5F' : 'none' }}>
            📖 {selectedDate.getDate()}일 그림일기
          </button>
          <button onClick={() => setActiveTab('report')} style={{ flex: 1, padding: '15px 0', fontSize: '16px', fontWeight: 'bold', cursor: 'pointer', backgroundColor: 'transparent', border: 'none', color: activeTab === 'report' ? '#7A8B5F' : '#AAAAAA', borderBottom: activeTab === 'report' ? '3px solid #7A8B5F' : 'none' }}>
            🩺 마음 건강 지표
          </button>
        </div>

        {/* 🌟 3. 탭 내용 렌더링 (기존과 동일) */}
        <div>
          {!filteredDiary && !filteredHealth && (
            <div style={{ textAlign: 'center', padding: '50px 0', color: '#AAA' }}>해당 날짜에는 기록된 대화가 없습니다.</div>
          )}

          {activeTab === 'diary' && filteredDiary && (
            <div style={{ backgroundColor: '#FFF', borderRadius: '16px', overflow: 'hidden', boxShadow: '0 4px 12px rgba(0,0,0,0.05)' }}>
              <img src={filteredDiary.imageUrl} alt="AI 그림일기" style={{ width: '100%', height: '220px', objectFit: 'cover' }} />
              <div style={{ padding: '24px' }}>
                <p style={{ fontSize: '16px', lineHeight: '1.7', color: '#333', marginBottom: '20px' }}>{filteredDiary.content}</p>
                <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                  {filteredDiary.keywords.map((kw, idx) => (
                    <span key={idx} style={{ fontSize: '13px', color: '#7A8B5F', backgroundColor: '#F4F7F0', padding: '6px 12px', borderRadius: '20px' }}>#{kw}</span>
                  ))}
                </div>
              </div>
            </div>
          )}

          {activeTab === 'report' && filteredHealth && (
            <div style={{ backgroundColor: '#FFF', borderRadius: '16px', padding: '24px', boxShadow: '0 4px 12px rgba(0,0,0,0.05)' }}>
              <div style={{ marginBottom: '20px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
                  <span style={{ fontSize: '15px', fontWeight: 'bold', color: '#555' }}>우울/고립감 지수</span>
                  <span style={{ fontSize: '14px', color: filteredHealth.depressionScore > 50 ? '#E57373' : '#7A8B5F', fontWeight: 'bold' }}>{filteredHealth.depressionScore}점</span>
                </div>
                <div style={{ width: '100%', height: '10px', backgroundColor: '#F0F0F0', borderRadius: '5px', overflow: 'hidden' }}>
                  <div style={{ width: `${filteredHealth.depressionScore}%`, height: '100%', backgroundColor: filteredHealth.depressionScore > 50 ? '#E57373' : '#7A8B5F', transition: 'width 1s ease-in-out' }} />
                </div>
              </div>
              <div style={{ marginBottom: '30px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
                  <span style={{ fontSize: '15px', fontWeight: 'bold', color: '#555' }}>인지 저하(치매) 징후 스코어</span>
                  <span style={{ fontSize: '14px', color: filteredHealth.dementiaScore > 50 ? '#E57373' : '#7A8B5F', fontWeight: 'bold' }}>{filteredHealth.dementiaScore}점</span>
                </div>
                <div style={{ width: '100%', height: '10px', backgroundColor: '#F0F0F0', borderRadius: '5px', overflow: 'hidden' }}>
                  <div style={{ width: `${filteredHealth.dementiaScore}%`, height: '100%', backgroundColor: filteredHealth.dementiaScore > 50 ? '#E57373' : '#7A8B5F', transition: 'width 1s ease-in-out' }} />
                </div>
              </div>
              <div style={{ backgroundColor: '#FDFBF7', padding: '15px', borderRadius: '12px', borderLeft: '4px solid #7A8B5F' }}>
                <p style={{ fontSize: '14px', lineHeight: '1.6', color: '#555', margin: 0 }}><strong>💡 주치의 AI 소견:</strong><br/>{filteredHealth.insight}</p>
              </div>
            </div>
          )}
        </div>

      </div>
    </div>
  );
};

export default MainPage;
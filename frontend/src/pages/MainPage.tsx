import React, { useEffect, useState } from 'react';
import Calendar from 'react-calendar';
import { useNavigate } from 'react-router-dom';

// HealthData 대신 통합된 AnalysisData 인터페이스 사용
import { DiaryData, AnalysisData } from '../types/interface';

import 'react-calendar/dist/Calendar.css';
import '../css/CustomCalendar.css';
import '../css/MainPage.css';

const MainPage = () => {
  const navigate = useNavigate();
  const [userName, setUserName] = useState<string>('보호자');
  const [activeTab, setActiveTab] = useState<'diary' | 'report'>('diary');

  // 기본값을 오늘 날짜로 설정
  const [selectedDate, setSelectedDate] = useState<Date>(new Date());
  const [markedDates, setMarkedDates] = useState<string[]>([]); // 일기가 존재하는 날짜 리스트 (예: ["2026-06-03", "2026-06-05"])

  // API 데이터 상태 관리
  const [selectedDiary, setSelectedDiary] = useState<DiaryData | null>(null);
  const [analysisData, setAnalysisData] = useState<AnalysisData | null>(null);
  const [isTabLoading, setIsTabLoading] = useState<boolean>(false);

  const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

  // 1. 로그인한 보호자 정보 가져오기
  useEffect(() => {
    const guardianInfoStr = localStorage.getItem('guardian_info');
    if (guardianInfoStr) {
      try {
        const info = JSON.parse(guardianInfoStr);
        if (info.name) setUserName(info.name);
      } catch (e) { }
    }
  }, []);

  const formatYYYYMMDD = (date: Date) => {
    const offset = date.getTimezoneOffset() * 60000;
    const dateOffset = new Date(date.getTime() - offset);
    return dateOffset.toISOString().split('T')[0];
  };

  const selectedDateStr = formatYYYYMMDD(selectedDate);

  // 2. 탭 및 날짜 변경 시 API 호출
  useEffect(() => {
    const fetchTabContent = async () => {
      const token = localStorage.getItem('access_token');
      const guardianStr = localStorage.getItem('guardian_info');
      const dependentId = localStorage.getItem('dependent_id');

      if (!token || !guardianStr || !dependentId) return;

      const guardianId = JSON.parse(guardianStr).id;
      setIsTabLoading(true);

      try {
        if (activeTab === 'diary') {
          // 선택한 날짜의 그림일기 조회
          const response = await fetch(
            `${API_BASE_URL}/api/v1/dashboard/${guardianId}/diary?user_id=${dependentId}&date=${selectedDateStr}`,
            { method: 'GET', headers: { 'Authorization': `Bearer ${token}` } }
          );


          // JSON으로 변환하기 전에 401 토큰 만료부터 최우선으로 검사
          if (response.status === 401) {
            alert("세션이 만료되었습니다. 다시 로그인해주세요.");
            localStorage.clear(); // 로컬 스토리지 전체 초기화
            navigate('/login');
            return;
          }

          const result = await response.json();

          if (response.ok && result.code === 200) setSelectedDiary(result.data);
          else setSelectedDiary(null);

        } else if (activeTab === 'report') {
          // 위험도 분석 조회
          const response = await fetch(
            `${API_BASE_URL}/api/v1/dashboard/${guardianId}/analysis?user_id=${dependentId}`,
            { method: 'GET', headers: { 'Authorization': `Bearer ${token}` } }
          );
          const result = await response.json();

          if (response.ok && result.code === 200) setAnalysisData(result.data);
          else setAnalysisData(null);
        }
      } catch (error) {
        console.error("Tab content fetch error:", error);
        setSelectedDiary(null);
        setAnalysisData(null);
      } finally {
        setIsTabLoading(false);
      }
    };

    fetchTabContent();
  }, [selectedDateStr, activeTab, API_BASE_URL]);

  // 월별 일기 존재 여부 조회 함수 (실제 API 연동)
  const fetchMonthlyRecords = async (date: Date) => {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const yearMonth = `${year}-${month}`; // 백엔드가 요구하는 "YYYY-MM" 포맷

    try {
      const token = localStorage.getItem('access_token');
      const guardianStr = localStorage.getItem('guardian_info');
      const dependentId = localStorage.getItem('dependent_id');

      // 인증 정보나 연동된 어르신 ID가 없으면 중단
      if (!token || !guardianStr || !dependentId) return;

      const guardianId = JSON.parse(guardianStr).id;
      const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

      const response = await fetch(
        `${API_BASE_URL}/api/v1/dashboard/${guardianId}/diary/monthly?user_id=${dependentId}&month=${yearMonth}`,
        {
          method: 'GET',
          headers: { 'Authorization': `Bearer ${token}` }
        }
      );

      // 🌟 1. JSON 변환 전 401 에러(세션 만료) 최우선 체크
      if (response.status === 401) {
        alert("세션이 만료되었습니다. 다시 로그인해주세요.");
        localStorage.clear();
        window.location.href = '/login';
        return;
      }

      // 2. 안전하게 JSON 파싱
      const result = await response.json();

      // 3. 백엔드에서 넘겨준 날짜 배열 저장 (예: ["2026-06-03", "2026-06-05"])
      if (response.ok && result.code === 200) {
        setMarkedDates(result.data || []);
      } else {
        setMarkedDates([]); // 에러나 데이터가 없을 경우 배열 비우기
      }
    } catch (err) {
      console.error("Monthly records fetch error:", err);
      setMarkedDates([]);
    }
  };

  // 3. 사용자가 연동되어 있는 상태일 때만 최초 이번 달 기록 조회
  useEffect(() => {
    const dependentId = localStorage.getItem('dependent_id');
    if (dependentId) {
      fetchMonthlyRecords(new Date());
    }
  }, []);
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
            
            // 사용자가 달력의 화살표를 눌러 월(Month)을 변경할 때마다 해당 월의 데이터를 새로 요청
            onActiveStartDateChange={({ activeStartDate }) => {
              if (activeStartDate) {
                fetchMonthlyRecords(activeStartDate);
              }
            }}

            // 타일의 날짜가 백엔드(혹은 Mock)에서 받아온 '기록 있는 날 리스트'에 포함되면 점(Dot)을 찍음
            tileContent={({ date, view }) => {
              if (view === 'month' && markedDates.includes(formatYYYYMMDD(date))) {
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
        <div style={{ minHeight: '150px' }}>
          {isTabLoading ? (
            <div style={{ textAlign: 'center', padding: '40px', color: '#888' }}>데이터를 불러오는 중입니다...</div>
          ) : (
            <>
              {activeTab === 'diary' && !selectedDiary && (
                <div className="empty-state">해당 날짜에는 기록된 데이터가 없습니다.</div>
              )}
              {activeTab === 'report' && !analysisData && (
                <div className="empty-state">분석된 건강 지표 데이터가 없습니다.</div>
              )}

              {/* 그림일기 탭 데이터 렌더링 */}
              {activeTab === 'diary' && selectedDiary && (
                <div className="diary-card interactive" onClick={() => navigate(`/diary?date=${selectedDateStr}`)}>
                  {/* 회색 대체 이미지 */}
                  <img src={selectedDiary.image_url} alt="AI 그림일기" className="diary-img" onError={(e) => { e.currentTarget.src = 'https://via.placeholder.com/400x300?text=Image+Not+Found'; }} />
                  <div className="diary-content-box">
                    <p className="diary-text">{selectedDiary.summary}</p>
                    <div className="keyword-container">
                      {selectedDiary.keywords.map((kw, idx) => (
                        <span key={idx} className="keyword-tag">#{kw}</span>
                      ))}
                    </div>
                    <div className="view-detail-link">자세히 보기 →</div>
                  </div>
                </div>
              )}

              {/* 마음 건강 지표 탭 데이터 렌더링 */}
              {activeTab === 'report' && analysisData && (
                <div className="report-card interactive" onClick={() => navigate('/analysis')}>

                  <div className="score-section">
                    <div className="score-header">
                      <span className="score-title">종합 위험도 스코어</span>
                      <span className={`score-value ${analysisData.average_score >= 70 ? 'high' : 'normal'}`}>
                        {analysisData.average_score}점
                      </span>
                    </div>
                    <div className="progress-bar-bg">
                      <div
                        className={`progress-bar-fill ${analysisData.average_score >= 70 ? 'high' : 'normal'}`}
                        style={{ width: `${analysisData.average_score}%` }}
                      />
                    </div>
                  </div>

                  <div className="insight-box">
                    <p className="insight-text">
                      <strong>💡 주치의 AI 소견:</strong><br />
                      {analysisData.insight}
                    </p>
                  </div>
                  <div className="view-detail-link">상세 분석 보기 →</div>
                </div>
              )}
            </>
          )}
        </div>

      </div>
    </div>
  );
};

export default MainPage;
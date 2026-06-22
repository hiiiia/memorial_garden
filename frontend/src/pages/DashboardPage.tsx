import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import Calendar from 'react-calendar';

// 전역 타입 파일에서 인터페이스 불러오기 (경로가 다를 경우 수정 필요)
import { DashboardData, DiaryData, AnalysisData } from '../types/interface';

import 'react-calendar/dist/Calendar.css';
import '../css/CustomCalendar.css';
import '../css/DashboardPage.css';
import '../css/MainPage.css';

const DashboardPage = () => {
  const navigate = useNavigate();

  // 메인 대시보드 상태 관리
  const [dashData, setDashData] = useState<DashboardData | null>(null);
  const [pendingSenior, setPendingSenior] = useState<{ name: string } | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // 하단 탭 및 달력 상태 관리
  const [activeTab, setActiveTab] = useState<'diary' | 'report'>('diary');
  const [selectedDate, setSelectedDate] = useState<Date>(new Date());
  const [markedDates, setMarkedDates] = useState<string[]>([]); // 일기가 존재하는 날짜 리스트 (예: ["2026-06-03", "2026-06-05"])

  // 하단 위젯 데이터 상태 관리 (Mock 대체)
  const [selectedDiary, setSelectedDiary] = useState<DiaryData | null>(null);
  const [analysisData, setAnalysisData] = useState<AnalysisData | null>(null);
  const [isTabLoading, setIsTabLoading] = useState<boolean>(false);

  const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

  // YYYY-MM-DD 포맷 변환 함수
  const formatYYYYMMDD = (date: Date) => {
    const offset = date.getTimezoneOffset() * 60000;
    return new Date(date.getTime() - offset).toISOString().split('T')[0];
  };

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
        `${API_BASE_URL}/api/v1/dashboard/diary/monthly?user_id=${dependentId}&month=${yearMonth}`,
        {
          method: 'GET',
          headers: { 'Authorization': `Bearer ${token}` }
        }
      );

      // 1. JSON 변환 전 401 에러(세션 만료) 최우선 체크
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
        if (result.data && result.data.diary_list) {
          // 새로운 백엔드 포맷: diary_list 배열 안의 객체들에서 date 값만 쏙쏙 뽑아냄
          const datesOnly = result.data.diary_list.map((diary: any) => diary.date);
          setMarkedDates(datesOnly);
        } else if (Array.isArray(result.data)) {
          // 혹시라도 예전 API가 응답할 경우를 대비한 방어 코드
          setMarkedDates(result.data);
        } else {
          setMarkedDates([]);
        }
      } else {
        setMarkedDates([]);
      }
    } catch (err) {
      console.error("Monthly records fetch error:", err);
      setMarkedDates([]);
    }
  };


  const selectedDateStr = formatYYYYMMDD(selectedDate);

  // 1. 메인 상단 대시보드 API 호출
  useEffect(() => {
    const fetchDashboard = async () => {
      try {
        const token = localStorage.getItem('access_token');
        const guardianStr = localStorage.getItem('guardian_info');
        const dependentId = localStorage.getItem('dependent_id');

        if (!token || !guardianStr) {
          navigate('/login');
          return;
        }

        if (!dependentId) {
          setDashData(null);
          setPendingSenior(null);
          setIsLoading(false);
          return;
        }

        const guardianId = JSON.parse(guardianStr).id;

        const response = await fetch(
          `${API_BASE_URL}/api/v1/dashboard?user_id=${dependentId}`,
          {
            method: 'GET',
            headers: {
              'Content-Type': 'application/json',
              'Authorization': `Bearer ${token}`
            }
          }
        );

        // JSON으로 변환하기 전에 401 토큰 만료부터 최우선으로 검사
        if (response.status === 401) {
          alert("세션이 만료되었습니다. 다시 로그인해주세요.");
          localStorage.clear(); // 로컬 스토리지 전체 초기화
          navigate('/login');
          return;
        }

        const result = await response.json();

        if (response.status === 202 || result.code === 202) {
          setDashData(null);
          setPendingSenior({ name: result.data.senior_name });
        } else if (response.ok && result.code === 200) {
          setDashData(result.data);
          setPendingSenior(null);
        } else {
          setError(result.error || '데이터를 불러오지 못했습니다.');
          if (result.code === 404) {
            localStorage.removeItem('dependent_id');
            setDashData(null);
            setPendingSenior(null);
          }
        }
      } catch (err) {
        console.error("Dashboard fetch error:", err);
        setError('서버와의 통신에 실패했습니다.');
      } finally {
        setIsLoading(false);
      }
    };

    fetchDashboard();
  }, [navigate, API_BASE_URL]);

  // 2. 하단 탭(그림일기/위험도) API 호출 로직 (날짜나 탭이 변경될 때마다 실행)
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
            `${API_BASE_URL}/api/v1/dashboard/diary?user_id=${dependentId}&date=${selectedDateStr}`,
            { method: 'GET', headers: { 'Authorization': `Bearer ${token}` } }
          );
          const result = await response.json();

          if (response.ok && result.code === 200) setSelectedDiary(result.data);
          else setSelectedDiary(null); // 기록 없음

        } else if (activeTab === 'report') {
          // 위험도 분석 조회 (주간 데이터 반환)
          const response = await fetch(
            `${API_BASE_URL}/api/v1/dashboard/analysis?user_id=${dependentId}`,
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

    // 대시보드 데이터(연동)가 정상적으로 로드된 상태에서만 하단 탭 데이터를 불러옴
    if (dashData) {
      fetchTabContent();
    }
  }, [selectedDateStr, activeTab, dashData, API_BASE_URL]);

  // 3. 사용자가 연동되어 있는 상태일 때만 최초 이번 달 기록 조회
  useEffect(() => {
    const dependentId = localStorage.getItem('dependent_id');
    if (dependentId) {
      fetchMonthlyRecords(new Date());
    }
  }, []);

  // 4. 연동 취소 함수
  const handleCancelRequest = async () => {
    try {
      const token = localStorage.getItem('access_token');
      const dependentId = localStorage.getItem('dependent_id');

      if (!token || !dependentId) return;

      const response = await fetch(
        `${API_BASE_URL}/api/v1/guardian/cancel-link/${dependentId}`,
        {
          method: 'DELETE',
          headers: { 'Authorization': `Bearer ${token}` }
        }
      );

      if (response.status === 401) {
        alert("세션이 만료되었습니다. 다시 로그인해주세요.");
        localStorage.clear();
        navigate('/login');
        return;
      }

      const result = await response.json();

      if (response.ok && result.code === 200) {
        alert("연동 요청이 취소되었습니다.");
        localStorage.removeItem('dependent_id');
        setPendingSenior(null);
        window.location.reload(); // 화면 갱신
      } else {
        alert(result.error || "연동 취소에 실패했습니다.");
      }
    } catch (error) {
      console.error("Cancel link error:", error);
      alert("서버 통신 중 오류가 발생했습니다.");
    }
  };

  const getConditionIcon = (state: string) => state === 'good' ? '🙂' : state === 'bad' ? '😥' : '😐';

  if (isLoading) return <div style={{ padding: '50px', textAlign: 'center', color: '#888' }}>대시보드를 준비 중입니다...</div>;
  if (error) return <div style={{ padding: '50px', textAlign: 'center', color: 'red' }}>오류 발생: {error}</div>;

  // 1. 수락 대기 중 화면 (Pending State)
  if (pendingSenior) {
    return (
      <div className="dashboard-container" style={{ padding: '100px 20px', textAlign: 'center' }}>
        <div style={{ fontSize: '50px', marginBottom: '20px' }}>⏳</div>
        <h2 style={{ color: '#333', marginBottom: '15px' }}>연동 수락 대기 중</h2>
        <div style={{ backgroundColor: '#FFF', border: '1px solid #EAE5D9', borderRadius: '12px', padding: '20px', maxWidth: '400px', margin: '0 auto 30px auto', boxShadow: '0 4px 12px rgba(0,0,0,0.03)' }}>
          <p style={{ color: '#4A4A4A', fontSize: '16px', margin: 0, lineHeight: '1.6' }}>
            <strong style={{ color: '#1B873F' }}>{pendingSenior.name} 어르신</strong> 연동 요청 진행중...<br />
            어르신이 라즈베리파이(또는 앱)에서 수락하시면<br />
            실시간 대시보드가 활성화됩니다.
          </p>
        </div>
        <button
          onClick={handleCancelRequest} // 🌟 기존 로컬스토리지 삭제 로직 대신 API 호출 함수 연결
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

        {/* 헤더 영역 */}
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

        {/* 상단 3개 데이터 위젯 */}
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
            <h3 className="card-title">위험도 <span style={{ fontSize: '12px', fontWeight: 'normal', color: '#888' }}>(자세히 보기 ↗)</span></h3>
            <h2 className="score-text" style={{ color: dashData.today_condition.color_code }}>{dashData.risk_assessment.score}점</h2>
            <p className="score-label">{dashData.risk_assessment.level}</p>
            <p className="card-subtext">{dashData.risk_assessment.status_text}</p>
          </div>
          <div className="dashboard-card interactive" onClick={() => navigate('/diary')}>
            <h3 className="card-title">마지막 대화 <span style={{ fontSize: '12px', fontWeight: 'normal', color: '#888' }}>(오늘 일기 ↗)</span></h3>
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

        <div className="tab-container">
          <button onClick={() => setActiveTab('diary')} className={`tab-button ${activeTab === 'diary' ? 'active' : 'inactive'}`}>
            📖 {selectedDate.getDate()}일 그림일기
          </button>
          <button onClick={() => setActiveTab('report')} className={`tab-button ${activeTab === 'report' ? 'active' : 'inactive'}`}>
            🩺 마음 건강 지표
          </button>
        </div>

        {/* 실제 API 데이터 기반 탭 컨텐츠 렌더링 */}
        <div style={{ minHeight: '150px' }}>
          {isTabLoading ? (
            <div style={{ textAlign: 'center', padding: '40px', color: '#888' }}>데이터를 불러오는 중입니다...</div>
          ) : (
            <>
              {/* 데이터가 없을 때 */}
              {activeTab === 'diary' && !selectedDiary && (
                <div className="empty-state">해당 날짜에는 기록된 그림일기가 없습니다.</div>
              )}
              {activeTab === 'report' && !analysisData && (
                <div className="empty-state">분석된 건강 지표 데이터가 없습니다.</div>
              )}

              {/* 그림일기 탭 내용 */}
              {activeTab === 'diary' && selectedDiary && (
                <div className="diary-card interactive" onClick={() => navigate(`/diary?date=${selectedDateStr}`)}>
                  {/* 회색 대체 이미지 */}
                  <img src={selectedDiary.image_url} alt="AI 그림일기" className="diary-img" onError={(e) => { e.currentTarget.src = 'data:image/svg+xml;charset=UTF-8,%3Csvg xmlns="http://www.w3.org/2000/svg" width="400" height="300" viewBox="0 0 400 300"%3E%3Crect fill="%23e2e8f0" width="400" height="300"/%3E%3Ctext fill="%23475569" font-family="sans-serif" font-size="20" dy="10.5" font-weight="bold" x="50%25" y="50%25" text-anchor="middle"%3EImage Not Found%3C/text%3E%3C/svg%3E'; }} />
                  <div className="diary-content-box">
                    <p className="diary-text">{selectedDiary.summary}</p>
                    <div className="keyword-container">
                      {selectedDiary.keywords.map((kw, idx) => (
                        <span key={idx} className="keyword-tag">#{kw}</span>
                      ))}
                    </div>
                    <div className="view-detail-link">전체 일기 및 감정 분석 보기 →</div>
                  </div>
                </div>
              )}

              {/* 마음 건강 지표(Analysis) 탭 내용 */}
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
                    <p className="insight-text"><strong>💡 소견:</strong><br />{analysisData.insight}</p>
                  </div>
                  <div className="view-detail-link">7일간 추이 차트 자세히 보기 →</div>
                </div>
              )}
            </>
          )}
        </div>

      </div>
    </div>
  );
};

export default DashboardPage;
import React, { useEffect, useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';

import { DiaryData } from '../types/interface';

import '../css/DetailPage.css'; // 기존에 쓰시던 CSS 파일 경로를 맞춰주세요.


const DiaryPage = () => {
  const navigate = useNavigate();
  const location = useLocation();
  
  // 상태 관리
  const [diaryData, setDiaryData] = useState<DiaryData | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // URL에서 date 쿼리 파라미터 추출 (없으면 오늘 날짜 사용)
  const queryParams = new URLSearchParams(location.search);
  const targetDate = queryParams.get('date') || new Date().toISOString().split('T')[0];

  useEffect(() => {
    const fetchDiary = async () => {
      try {
        const token = localStorage.getItem('access_token');
        const guardianStr = localStorage.getItem('guardian_info');
        const dependentId = localStorage.getItem('dependent_id');

        // 인증 정보가 없으면 로그인 창으로
        if (!token || !guardianStr || !dependentId) {
          setError('권한이 없거나 선택된 어르신 정보가 없습니다.');
          setIsLoading(false);
          return;
        }

        const guardianId = JSON.parse(guardianStr).id;
        const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

        // 백엔드 /diary 엔드포인트 호출
        const response = await fetch(
          `${API_BASE_URL}/api/v1/dashboard/${guardianId}/diary?user_id=${dependentId}&date=${targetDate}`,
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

        if (response.ok && result.code === 200) {
          setDiaryData(result.data);
        } else if (result.code === 404) {
          // 해당 날짜에 일기가 없는 경우
          setDiaryData(null);
        } else {
          setError(result.error || '일기 데이터를 불러오지 못했습니다.');
        }
      } catch (err) {
        console.error("Diary fetch error:", err);
        setError('서버와의 통신에 실패했습니다.');
      } finally {
        setIsLoading(false);
      }
    };

    fetchDiary();
  }, [targetDate]);

  // 로딩 화면
  if (isLoading) {
    return <div style={{ padding: '50px', textAlign: 'center', color: '#888' }}>일기 데이터를 불러오는 중입니다...</div>;
  }

  // 에러 화면
  if (error) {
    return (
      <div style={{ padding: '50px', textAlign: 'center' }}>
        <p style={{ color: 'red', marginBottom: '20px' }}>{error}</p>
        <button onClick={() => navigate(-1)}>뒤로 가기</button>
      </div>
    );
  }

  // 빈 데이터 화면 (일기가 없을 때)
  if (!diaryData) {
    return (
      <div className="diary-container" style={{ padding: '40px 20px', textAlign: 'center' }}>
        <header style={{ display: 'flex', alignItems: 'center', marginBottom: '30px' }}>
          <button onClick={() => navigate(-1)} style={{ background: 'none', border: 'none', fontSize: '20px', cursor: 'pointer' }}>←</button>
          <h2 style={{ margin: '0 auto', fontSize: '18px' }}>{targetDate} 그림일기</h2>
        </header>
        <div style={{ padding: '100px 0', color: '#888' }}>
          <div style={{ fontSize: '40px', marginBottom: '15px' }}>📝</div>
          이 날은 어르신과 나눈 대화 기록이 없습니다.
        </div>
      </div>
    );
  }

  // 정상 데이터 렌더링 화면
  return (
    <div className="diary-container" style={{ padding: '20px', maxWidth: '600px', margin: '0 auto' }}>
      {/* 상단 네비게이션 */}
      <header style={{ display: 'flex', alignItems: 'center', marginBottom: '20px' }}>
        <button onClick={() => navigate(-1)} style={{ background: 'none', border: 'none', fontSize: '20px', cursor: 'pointer', color: '#333' }}>←</button>
        <h2 style={{ margin: '0 auto', fontSize: '18px', fontWeight: 'bold' }}>{diaryData.date} 그림일기</h2>
      </header>

      {/* 그림일기 이미지 영역 */}
      <div style={{ width: '100%', borderRadius: '16px', overflow: 'hidden', marginBottom: '20px', boxShadow: '0 4px 12px rgba(0,0,0,0.1)' }}>
        <img src={diaryData.image_url} alt="AI 그림일기" style={{ width: '100%', height: 'auto', display: 'block' }} onError={(e) => {e.currentTarget.src = 'https://via.placeholder.com/600x400?text=Image+Not+Found';}}/>
      </div>

      {/* 키워드 및 요약 영역 */}
      <div style={{ backgroundColor: '#FFF', borderRadius: '12px', padding: '20px', marginBottom: '20px', boxShadow: '0 2px 8px rgba(0,0,0,0.04)' }}>
        <div style={{ display: 'flex', gap: '8px', marginBottom: '15px', flexWrap: 'wrap' }}>
          <span style={{ backgroundColor: '#FFF0F0', color: '#D32F2F', padding: '4px 12px', borderRadius: '20px', fontSize: '14px', fontWeight: 'bold' }}>
            {diaryData.primary_emotion}
          </span>
          {diaryData.keywords?.map((kw, idx) => (
            <span key={idx} style={{ backgroundColor: '#F0F4E8', color: '#7A8B5F', padding: '4px 12px', borderRadius: '20px', fontSize: '14px' }}>
              #{kw}
            </span>
          ))}
        </div>
        <p style={{ fontSize: '16px', lineHeight: '1.6', color: '#333', margin: 0 }}>
          <strong>💡 AI 요약:</strong> {diaryData.summary}
        </p>
      </div>

      {/* 상세 대화(STT) 원문 영역 */}
      <div style={{ backgroundColor: '#F9F9F9', borderRadius: '12px', padding: '20px', border: '1px solid #EEE' }}>
        <h3 style={{ fontSize: '15px', color: '#555', marginBottom: '15px' }}>💬 대화 원문 보기</h3>
        
        {/* 어르신 말풍선 */}
        <div style={{ marginBottom: '15px' }}>
          <div style={{ fontSize: '13px', color: '#888', marginBottom: '4px' }}>어르신</div>
          <div style={{ backgroundColor: '#FFF', padding: '12px 16px', borderRadius: '0 12px 12px 12px', display: 'inline-block', boxShadow: '0 1px 4px rgba(0,0,0,0.05)', color: '#333', lineHeight: '1.5' }}>
            {diaryData.stt_text}
          </div>
        </div>

        {/* AI 말풍선 */}
        <div style={{ textAlign: 'right' }}>
          <div style={{ fontSize: '13px', color: '#888', marginBottom: '4px' }}>AI 주치의</div>
          <div style={{ backgroundColor: '#7A8B5F', color: '#FFF', padding: '12px 16px', borderRadius: '12px 0 12px 12px', display: 'inline-block', boxShadow: '0 1px 4px rgba(0,0,0,0.05)', lineHeight: '1.5', textAlign: 'left' }}>
            {diaryData.reply_text}
          </div>
        </div>
      </div>
    </div>
  );
};

export default DiaryPage;
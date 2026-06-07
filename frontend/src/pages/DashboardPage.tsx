// src/pages/DashboardPage.tsx

import React, { useEffect, useState } from 'react';
import { config } from '../config'; // API 주소 세팅

// --- TypeScript 인터페이스 정의 ---
interface DashboardData {
  guardian_name: string;
  senior: { name: string; status: string };
  today_condition: { state: string; label: string; description: string; color_code: string };
  risk_assessment: { score: number; level: string; status_text: string };
  last_interaction: { time_label: string; duration_label: string };
  recent_alerts: { id: number; content: string; time_ago: string; type: string }[];
}

const DashboardPage = () => {
  const [data, setData] = useState<DashboardData | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string>('');

  useEffect(() => {
    const fetchDashboard = async () => {
      try {
        // 로컬 스토리지에서 정보 꺼내기
        const token = localStorage.getItem('access_token');
        const guardianInfoStr = localStorage.getItem('guardian_info');
        
        if (!token || !guardianInfoStr) {
          setError('로그인이 필요합니다.');
          setIsLoading(false);
          return;
        }

        const guardianInfo = JSON.parse(guardianInfoStr);
        const guardianId = guardianInfo.id;
        const targetUserId = 'USER_ABC'; // 임시 하드코딩 (실제로는 연동된 어르신 ID)
        const currentDate = new Date().toISOString();

        // 백엔드 API 호출
        const response = await fetch(
          `${config.apiBaseUrl}/guardian/${guardianId}/dashboard?user_id=${targetUserId}&date=${currentDate}`,
          {
            method: 'GET',
            headers: {
              'Content-Type': 'application/json',
              'Authorization': `Bearer ${token}` // JWT 방문증 제시!
            }
          }
        );

        const result = await response.json();

        if (response.ok && result.code === 200) {
          setData(result.data);
        } else {
          setError(result.error || '데이터를 불러오지 못했습니다.');
        }
      } catch (err) {
        setError('서버와의 통신에 실패했습니다.');
      } finally {
        setIsLoading(false);
      }
    };

    fetchDashboard();
  }, []);

  // 로딩 화면
  if (isLoading) return <div style={{ padding: '50px', textAlign: 'center', color: '#888' }}>데이터를 불러오는 중입니다...</div>;
  
  // 에러 화면
  if (error || !data) return <div style={{ padding: '50px', textAlign: 'center', color: '#E57373' }}>{error}</div>;

  // 메인 렌더링 화면
  return (
    <div style={{ minHeight: '100vh', backgroundColor: '#FDFBF7', padding: '40px 20px', color: '#4A4A4A', fontFamily: 'sans-serif' }}>
      <div style={{ maxWidth: '500px', margin: '0 auto' }}>
        
        {/* 1. 상단 헤더 (인사말 & 연동 상태) */}
        <div style={{ marginBottom: '30px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <h1 style={{ fontSize: '24px', margin: '0 0 5px 0' }}>안녕하세요, <strong>{data.guardian_name}</strong>님!</h1>
            <p style={{ margin: 0, color: '#888', fontSize: '15px' }}>오늘도 평안한 하루 되세요.</p>
          </div>
          <div style={{ textAlign: 'right' }}>
            <div style={{ fontSize: '14px', fontWeight: 'bold', color: '#333' }}>{data.senior.name} 님</div>
            <div style={{ fontSize: '12px', color: '#7A8B5F', backgroundColor: '#F4F7F0', padding: '4px 8px', borderRadius: '12px', display: 'inline-block', marginTop: '4px' }}>
              ● {data.senior.status}
            </div>
          </div>
        </div>

        {/* 2. 오늘의 상태 카드 */}
        <div style={{ backgroundColor: '#FFF', borderRadius: '20px', padding: '25px', boxShadow: '0 4px 12px rgba(0,0,0,0.03)', marginBottom: '20px', borderTop: `5px solid ${data.today_condition.color_code}` }}>
          <div style={{ fontSize: '14px', color: '#999', marginBottom: '10px' }}>오늘의 상태</div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '15px' }}>
            <div style={{ fontSize: '32px', fontWeight: '900', color: data.today_condition.color_code }}>{data.today_condition.label}</div>
            <div style={{ fontSize: '16px', color: '#555' }}>{data.today_condition.description}</div>
          </div>
        </div>

        {/* 3. 2단 그리드 (위험도 & 마지막 대화) */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '15px', marginBottom: '20px' }}>
          
          {/* 위험도 위젯 */}
          <div style={{ backgroundColor: '#FFF', borderRadius: '20px', padding: '20px', boxShadow: '0 4px 12px rgba(0,0,0,0.03)' }}>
            <div style={{ fontSize: '13px', color: '#999', marginBottom: '10px' }}>위험도 평가 ({data.risk_assessment.score}점)</div>
            <div style={{ fontSize: '20px', fontWeight: 'bold', color: '#333', marginBottom: '5px' }}>{data.risk_assessment.level}</div>
            <div style={{ fontSize: '13px', color: '#777' }}>{data.risk_assessment.status_text}</div>
          </div>

          {/* 마지막 대화 위젯 */}
          <div style={{ backgroundColor: '#FFF', borderRadius: '20px', padding: '20px', boxShadow: '0 4px 12px rgba(0,0,0,0.03)' }}>
            <div style={{ fontSize: '13px', color: '#999', marginBottom: '10px' }}>마지막 대화</div>
            <div style={{ fontSize: '16px', fontWeight: 'bold', color: '#333', marginBottom: '5px' }}>{data.last_interaction.time_label}</div>
            <div style={{ fontSize: '13px', color: '#7A8B5F' }}>{data.last_interaction.duration_label}</div>
          </div>
        </div>

        {/* 4. 최근 알림 리스트 */}
        <div style={{ backgroundColor: '#FFF', borderRadius: '20px', padding: '25px', boxShadow: '0 4px 12px rgba(0,0,0,0.03)' }}>
          <div style={{ fontSize: '16px', fontWeight: 'bold', color: '#333', marginBottom: '20px' }}>최근 소식</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '15px' }}>
            {data.recent_alerts.map((alert) => (
              <div key={alert.id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid #F0F0F0', paddingBottom: '15px' }}>
                <div style={{ fontSize: '15px', color: '#4A4A4A' }}>{alert.content}</div>
                <div style={{ fontSize: '13px', color: '#AAA' }}>{alert.time_ago}</div>
              </div>
            ))}
          </div>
        </div>

      </div>
    </div>
  );
};

export default DashboardPage;
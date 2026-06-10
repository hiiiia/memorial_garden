// src/pages/RiskAnalysisPage.tsx

import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine } from 'recharts';

import { TrendData, AnalysisData } from '../types/interface';

import { config } from '../config'; // API 주소 세팅
import '../css/DetailPage.css';


const AnalysisPage = () => {
  const navigate = useNavigate();
  
  // 상태 관리
  const [analysisData, setAnalysisData] = useState<AnalysisData | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchAnalysis = async () => {
      try {
        const token = localStorage.getItem('access_token');
        const guardianStr = localStorage.getItem('guardian_info');
        const dependentId = localStorage.getItem('dependent_id');

        // 인증 정보 확인
        if (!token || !guardianStr || !dependentId) {
          setError('권한이 없거나 선택된 어르신 정보가 없습니다.');
          setIsLoading(false);
          return;
        }

        const guardianId = JSON.parse(guardianStr).id;
        const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

        // 백엔드 /analysis 엔드포인트 호출
        const response = await fetch(
          `${API_BASE_URL}/api/v1/dashboard/analysis?user_id=${dependentId}`,
          {
            method: 'GET',
            headers: {
              'Content-Type': 'application/json',
              'Authorization': `Bearer ${token}`
            }
          }
        );

        const result = await response.json();

        if (response.ok && result.code === 200) {
          setAnalysisData(result.data);
        } else {
          setError(result.error || '분석 데이터를 불러오지 못했습니다.');
        }
      } catch (err) {
        console.error("Analysis fetch error:", err);
        setError('서버와의 통신에 실패했습니다.');
      } finally {
        setIsLoading(false);
      }
    };

    fetchAnalysis();
  }, []);

  // 상태별 렌더링
  if (isLoading) return <div style={{ padding: '50px', textAlign: 'center', color: '#888' }}>데이터를 분석 중입니다...</div>;
  if (error) return (
    <div style={{ padding: '50px', textAlign: 'center' }}>
      <p style={{ color: 'red', marginBottom: '20px' }}>{error}</p>
      <button onClick={() => navigate(-1)} style={{ padding: '8px 16px', borderRadius: '8px', border: '1px solid #CCC' }}>뒤로 가기</button>
    </div>
  );
  if (!analysisData) return null;

  // 평균 점수에 따른 상태 색상 및 텍스트 결정 로직
  const isHighRisk = analysisData.average_score >= 70;
  const isWarning = analysisData.average_score >= 35 && analysisData.average_score < 70;
  
  const statusColor = isHighRisk ? '#D32F2F' : isWarning ? '#FBC02D' : '#388E3C';
  const statusLabel = isHighRisk ? '위험' : isWarning ? '주의' : '안정';

  return (
    <div style={{ padding: '20px', maxWidth: '600px', margin: '0 auto', backgroundColor: '#FAFAFA', minHeight: '100vh' }}>
      
      {/* 상단 네비게이션 헤더 */}
      <header style={{ display: 'flex', alignItems: 'center', marginBottom: '30px' }}>
        <button onClick={() => navigate(-1)} style={{ background: 'none', border: 'none', fontSize: '20px', cursor: 'pointer', color: '#333' }}>←</button>
        <h2 style={{ margin: '0 auto', fontSize: '18px', fontWeight: 'bold' }}>주간 위험도 분석</h2>
        <div style={{ width: '20px' }} /> {/* 가운데 정렬용 더미 div */}
      </header>

      {/* 1. 종합 점수 요약 카드 */}
      <div style={{ backgroundColor: '#FFF', borderRadius: '16px', padding: '24px', marginBottom: '20px', boxShadow: '0 4px 12px rgba(0,0,0,0.05)', textAlign: 'center' }}>
        <h3 style={{ fontSize: '15px', color: '#666', marginBottom: '10px', fontWeight: 'normal' }}>최근 7일 평균 위험도</h3>
        <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'baseline', gap: '8px' }}>
          <span style={{ fontSize: '42px', fontWeight: 'bold', color: statusColor }}>
            {analysisData.average_score}
          </span>
          <span style={{ fontSize: '18px', color: '#888' }}>점</span>
        </div>
        <div style={{ marginTop: '10px', display: 'inline-block', backgroundColor: `${statusColor}15`, color: statusColor, padding: '6px 16px', borderRadius: '20px', fontSize: '14px', fontWeight: 'bold' }}>
          현재 상태: {statusLabel}
        </div>
      </div>

      {/* 2. 주간 꺾은선 차트 영역 (Recharts 활용) */}
      <div style={{ backgroundColor: '#FFF', borderRadius: '16px', padding: '24px 15px', marginBottom: '20px', boxShadow: '0 4px 12px rgba(0,0,0,0.05)' }}>
        <h3 style={{ fontSize: '16px', color: '#333', marginBottom: '20px', paddingLeft: '10px' }}>📊 위험도 추이</h3>
        <div style={{ width: '100%', height: '250px' }}>
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={analysisData.trend_data} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#EEE" />
              <XAxis dataKey="date" tick={{ fontSize: 12, fill: '#888' }} axisLine={false} tickLine={false} dy={10} />
              <YAxis domain={[0, 100]} tick={{ fontSize: 12, fill: '#888' }} axisLine={false} tickLine={false} />
              <Tooltip 
                contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 2px 8px rgba(0,0,0,0.1)' }}
                formatter={(value: any) => [`${value}점`, '위험도']}
                labelStyle={{ color: '#888', marginBottom: '5px' }}
              />
              {/* 위험 기준선 (70점) */}
              <ReferenceLine y={70} stroke="#D32F2F" strokeDasharray="3 3" label={{ position: 'top', value: '위험 기준', fill: '#D32F2F', fontSize: 10 }} />
              
              <Line 
                type="monotone" 
                dataKey="score" 
                stroke="#7A8B5F" 
                strokeWidth={3}
                dot={{ r: 4, fill: '#7A8B5F', strokeWidth: 2, stroke: '#FFF' }}
                activeDot={{ r: 6 }}
                animationDuration={1000}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* 3. 소견 영역 */}
      <div style={{ backgroundColor: '#F0F4E8', borderRadius: '16px', padding: '24px', border: '1px solid #E1E8D5' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px' }}>
          <span style={{ fontSize: '20px' }}>👨‍⚕️</span>
          <h3 style={{ fontSize: '16px', color: '#333', margin: 0 }}>종합 소견</h3>
        </div>
        <p style={{ fontSize: '15px', lineHeight: '1.6', color: '#4A4A4A', margin: 0, wordBreak: 'keep-all' }}>
          {analysisData.insight}
        </p>
      </div>

    </div>
  );
};

export default AnalysisPage;

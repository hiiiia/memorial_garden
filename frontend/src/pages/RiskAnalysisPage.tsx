// src/pages/RiskAnalysisPage.tsx

import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { config } from '../config'; // API 주소 세팅
import '../css/DetailPages.css';

// --- TypeScript 인터페이스 정의 ---
interface RiskData {
  current_score: number;
  level: string;
  description: string;
  weekly_trend: { name: string; score: number }[];
  ai_analysis: { icon: string; text: string; color: string }[];
  recommended_actions: { icon: string; text: string }[];
}

const RiskAnalysisPage = () => {
  const navigate = useNavigate();
  const [data, setData] = useState<RiskData | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string>('');

  useEffect(() => {
    const fetchRiskAnalysis = async () => {
      try {
        const token = localStorage.getItem('access_token');
        if (!token) throw new Error('로그인이 필요합니다.');

        // TODO: 실제 백엔드 API 엔드포인트로 변경
        // const response = await fetch(`${config.apiBaseUrl}/guardian/seniors/risk-analysis`, { ... });

        // [임시] 백엔드가 없으므로 가짜 데이터 세팅
        setTimeout(() => {
          setData({
            current_score: 72,
            level: "높음",
            description: "평소보다 위험도가 증가했습니다.",
            weekly_trend: [
              { name: '월', score: 25 }, { name: '화', score: 35 }, { name: '수', score: 35 },
              { name: '목', score: 45 }, { name: '금', score: 68 }, { name: '토', score: 80 },
              { name: '일', score: 72 },
            ],
            ai_analysis: [
              { icon: '🔍', text: '외로움 관련 표현이 평소보다 35% 증가했어요.', color: '#42A5F5' },
              { icon: '💤', text: '수면 관련 부정 표현이 증가했어요.', color: '#5C6BC0' },
              { icon: '🚪', text: '사회활동 언급이 감소했어요.', color: '#AB47BC' },
            ],
            recommended_actions: [
              { icon: '📞', text: '전화로 안부 확인하기' },
              { icon: '🗓️', text: '방문 일정 조율하기' },
              { icon: '🏥', text: '전문 상담 권장하기' },
            ]
          });
          setIsLoading(false);
        }, 800);

      } catch (err: any) {
        setError(err.message || '데이터를 불러오지 못했습니다.');
        setIsLoading(false);
      }
    };

    fetchRiskAnalysis();
  }, []);

  if (isLoading) return <div style={{ padding: '50px', textAlign: 'center', color: '#888' }}>위험도 데이터를 분석하는 중입니다...</div>;
  if (error || !data) return <div style={{ padding: '50px', textAlign: 'center', color: '#E57373' }}>{error}</div>;

  return (
    <div className="detail-container">
      <div className="detail-content">
        <div className="back-button" onClick={() => navigate(-1)}>
          ← 위험도 분석
        </div>

        {/* 상단: 현재 위험도 & 차트 */}
        <div className="risk-top-grid">
          <div className="detail-card risk-score-box">
            <h3 className="card-title" style={{ alignSelf: 'flex-start' }}>현재 위험도</h3>
            <div className="risk-score" style={{ color: data.current_score >= 70 ? '#D32F2F' : '#388E3C' }}>
              {data.current_score}점
            </div>
            <div className="risk-badge" style={{ 
              backgroundColor: data.current_score >= 70 ? '#FFEBEE' : '#E8F5E9',
              color: data.current_score >= 70 ? '#D32F2F' : '#388E3C' 
            }}>
              {data.level}
            </div>
            <p className="risk-desc">{data.description}</p>
          </div>

          <div className="detail-card">
            <h3 className="card-title">최근 7일 위험도 변화</h3>
            <div style={{ width: '100%', height: '200px' }}>
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={data.weekly_trend} margin={{ top: 15, right: 20, left: -20, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#EEE" />
                  <XAxis dataKey="name" axisLine={false} tickLine={false} tick={{ fontSize: 12, fill: '#888' }} dy={10} />
                  <YAxis axisLine={false} tickLine={false} tick={{ fontSize: 12, fill: '#888' }} domain={[0, 100]} ticks={[0, 25, 50, 75, 100]} />
                  <Tooltip />
                  <Line type="monotone" dataKey="score" stroke="#D32F2F" strokeWidth={2} dot={{ r: 4, strokeWidth: 2, fill: '#FFF' }} activeDot={{ r: 6 }} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>

        {/* 하단: 분석 결과 & 추천 행동 */}
        <div className="risk-bottom-grid">
          <div className="detail-card">
            <h3 className="card-title">AI 분석 결과</h3>
            <ul className="analysis-list">
              {data.ai_analysis.map((item, idx) => (
                <li key={idx} className="analysis-item">
                  <div className="icon-circle" style={{ color: item.color }}>{item.icon}</div>
                  {item.text}
                </li>
              ))}
            </ul>
          </div>

          <div className="detail-card">
            <h3 className="card-title">추천 행동</h3>
            <ul className="action-list">
              {data.recommended_actions.map((action, idx) => (
                <li key={idx} className="action-item">
                  <div className="icon-circle" style={{ backgroundColor: '#F3E5F5', color: '#8E24AA' }}>{action.icon}</div>
                  {action.text}
                </li>
              ))}
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
};

export default RiskAnalysisPage;
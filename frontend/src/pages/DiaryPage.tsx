// src/pages/DiaryPage.tsx

import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { PieChart, Pie, Cell, ResponsiveContainer } from 'recharts';
import { config } from '../config'; // API 주소 세팅
import '../css/DetailPages.css';

// --- TypeScript 인터페이스 정의 ---
interface DiaryData {
  title: string;
  date: string;
  content: string;
  image_url: string;
  summary: string;
  emotions: { name: string; value: number; color: string }[];
}

const DiaryPage = () => {
  const navigate = useNavigate();
  const [data, setData] = useState<DiaryData | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string>('');

  useEffect(() => {
    const fetchDiary = async () => {
      try {
        const token = localStorage.getItem('access_token');
        if (!token) throw new Error('로그인이 필요합니다.');

        // TODO: 실제 백엔드 API 엔드포인트로 변경
        // const response = await fetch(`${config.apiBaseUrl}/guardian/seniors/diary/today`, { ... });
        
        // [임시] 백엔드가 없으므로 가짜 데이터 세팅 (나중에 이 블록을 통째로 지우고 fetch 로직으로 교체하세요)
        setTimeout(() => {
          setData({
            title: "시장에 다녀온 날",
            date: "2026.05.12(목)",
            content: "오늘은 시장에 다녀왔어요.\n오랜만에 친구도 만나고,\n신선한 채소도 샀답니다.\n날씨가 좋아서 기분이 참 좋았어요.",
            image_url: "/sample-diary-img.png", // 실제 이미지가 있다면 public 폴더에 넣거나 URL 사용
            summary: "즐거운 외출과 사람들과의 만남이\n긍정적인 하루를 만들어주었어요.",
            emotions: [
              { name: '긍정', value: 80, color: '#68B38A' },
              { name: '보통', value: 15, color: '#F9C74F' },
              { name: '부정', value: 5, color: '#E57373' },
            ]
          });
          setIsLoading(false);
        }, 800);

      } catch (err: any) {
        setError(err.message || '데이터를 불러오지 못했습니다.');
        setIsLoading(false);
      }
    };

    fetchDiary();
  }, []);

  if (isLoading) return <div style={{ padding: '50px', textAlign: 'center', color: '#888' }}>일기를 불러오는 중입니다...</div>;
  if (error || !data) return <div style={{ padding: '50px', textAlign: 'center', color: '#E57373' }}>{error}</div>;

  return (
    <div className="detail-container">
      <div className="detail-content">
        <div className="back-button" onClick={() => navigate(-1)}>
          ← 오늘의 일기
        </div>

        {/* 상단: 이미지 및 일기 내용 */}
        <div className="detail-card diary-top-section">
          {data.image_url ? (
            <img src={data.image_url} alt={data.title} className="diary-image" />
          ) : (
            <div className="diary-image" style={{ backgroundColor: '#EEE', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <span>이미지 없음</span>
            </div>
          )}
          <div className="diary-text-area">
            <h2 className="diary-title">{data.title}</h2>
            <p className="diary-date">{data.date}</p>
            <p className="diary-body">
              {/* 줄바꿈(\n)을 <br /> 태그로 변환하여 렌더링 */}
              {data.content.split('\n').map((line, i) => (
                <React.Fragment key={i}>
                  {line}<br />
                </React.Fragment>
              ))}
            </p>
          </div>
        </div>

        {/* 하단: 감정 분석 & AI 한줄 요약 */}
        <div className="diary-bottom-grid">
          <div className="detail-card">
            <h3 className="card-title">감정 분석</h3>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div style={{ width: '150px', height: '150px' }}>
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie data={data.emotions} innerRadius={45} outerRadius={70} paddingAngle={2} dataKey="value">
                      {data.emotions.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={entry.color} />
                      ))}
                    </Pie>
                  </PieChart>
                </ResponsiveContainer>
              </div>
              
              <div className="emotion-legend">
                {data.emotions.map((item, idx) => (
                  <div key={idx} className="legend-item">
                    <div className="legend-color" style={{ backgroundColor: item.color }}></div>
                    <span style={{ width: '35px' }}>{item.name}</span>
                    <span style={{ fontWeight: 'bold' }}>{item.value}%</span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          <div className="detail-card">
            <h3 className="card-title">AI 한줄 요약</h3>
            <p className="diary-body" style={{ marginTop: '20px' }}>
              {data.summary.split('\n').map((line, i) => (
                <React.Fragment key={i}>{line}<br /></React.Fragment>
              ))}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default DiaryPage;
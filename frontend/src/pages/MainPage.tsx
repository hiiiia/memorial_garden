// src/pages/MainPage.tsx
import React from 'react';

// 나중에 백엔드에서 받아올 음성 파일 데이터의 예시(Mock)입니다.
const mockAudios = [
  { id: 1, title: "오늘 하루 이야기", date: "2026.06.05", duration: "01:24" },
  { id: 2, title: "잠들기 전 인사", date: "2026.06.04", duration: "00:45" },
  { id: 3, title: "즐거운 노래", date: "2026.06.03", duration: "02:10" },
];

const MainPage = () => {
  return (
    <div style={{ 
      minHeight: '100vh', 
      backgroundColor: '#FDFBF7', // 전체 배경을 따뜻하게
      padding: '40px 20px',
      color: '#4A4A4A' 
    }}>
      <div style={{ maxWidth: '800px', margin: '0 auto' }}>
        
        {/* 상단 인사말 영역 */}
        <div style={{ marginBottom: '40px' }}>
          <h1 style={{ fontSize: '28px', marginBottom: '10px' }}>소중한 목소리가 도착했어요.</h1>
          <p style={{ color: '#888', fontSize: '16px' }}>오늘도 평안한 하루 되세요.</p>
        </div>

        {/* 음성 카드 목록 (Grid 레이아웃) */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(250px, 1fr))', gap: '20px' }}>
          {mockAudios.map((audio) => (
            <div key={audio.id} style={{
              backgroundColor: '#FFFFFF',
              borderRadius: '16px', // 부드러운 곡선
              padding: '20px',
              boxShadow: '0 4px 12px rgba(0, 0, 0, 0.04)', // 은은한 그림자
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'space-between'
            }}>
              <div>
                <h3 style={{ margin: '0 0 8px 0', fontSize: '18px', color: '#333' }}>{audio.title}</h3>
                <span style={{ fontSize: '12px', color: '#999' }}>{audio.date} • {audio.duration}</span>
              </div>
              
              {/* 재생 버튼 (임시 디자인) */}
              <button style={{
                marginTop: '20px',
                padding: '12px',
                backgroundColor: '#7A8B5F', // 메인 올리브색
                color: 'white',
                border: 'none',
                borderRadius: '12px',
                cursor: 'pointer',
                fontWeight: 'bold'
              }}>
                ▶ 재생하기
              </button>
            </div>
          ))}
        </div>

      </div>
    </div>
  );
};

export default MainPage;
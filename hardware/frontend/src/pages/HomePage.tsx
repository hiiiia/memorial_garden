import React from 'react';

interface HomePageProps {
  onEmergency: () => void;
  onTalk: () => void;
  onDiary: () => void;
  onMemory: () => void;
}

const HomePage: React.FC<HomePageProps> = ({
  onEmergency,
  onTalk,
  onDiary,
  onMemory,
}) => {
      return (
    <div className="home-card">
      <div className="logo">🌱 기억정원</div>

      <div className="home-content">
        <div className="robot">🌱</div>

        <div className="info">
          <p className="hello">안녕하세요!</p>
          <h1>김영희 어르신</h1>
          <p className="sub-text">오늘도 좋은 하루 보내세요 😊</p>

          <div className="button-group">
            <button className="menu-btn help-btn" onClick={onEmergency}>
              ☎<span>도움<br />요청하기</span>
            </button>

            <button className="menu-btn talk-btn" onClick={onTalk}>
              🎤<span>이야기<br />시작하기</span>
            </button>

            <button className="menu-btn diary-btn" onClick={onDiary}>
              📖<span>오늘의<br />일기</span>
            </button>

            <button className="menu-btn memory-btn" onClick={onMemory}>
              🖼<span>추억<br />보관함</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default HomePage;
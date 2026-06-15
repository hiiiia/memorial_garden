import React, { useState } from 'react';
import '../css/ElderPage.css';

type Screen = 'home' | 'talk' | 'ai';

const ElderPage = () => {
  const [screen, setScreen] = useState<Screen>('home');

  return (
    <div className="elder-page">
      {screen === 'home' && (
        <div className="home-card">
          <div className="logo">🌱 기억정원</div>

          <div className="home-content">
            <div className="robot">🌱</div>

            <div className="info">
              <p className="hello">안녕하세요!</p>
              <h1>김영희 어르신</h1>
              <p className="sub-text">오늘도 좋은 하루 보내세요 😊</p>

              <div className="button-group">
                <button className="menu-btn help-btn">
                    ☎
                    <span>
                        도움<br />
                        요청하기
                    </span>
                </button>

                <button className="menu-btn talk-btn" onClick={() => setScreen('talk')}>
                    🎤
                    <span>
                        이야기<br />
                        시작하기
                    </span>
                </button>
                <button className="menu-btn diary-btn">📖<span>오늘의 일기</span></button>
                <button className="menu-btn memory-btn">🖼<span>추억 보관함</span></button>
              </div>
            </div>
          </div>
        </div>
      )}

      {screen === 'talk' && (
        <div className="home-card talk-card">
          <h1 className="talk-title">무엇을 이야기할까요?</h1>
          <div className="talk-robot">🌱</div>

          <div className="talk-buttons">
            <button
                type="button"
                className="talk-main-btn"
                onClick={() => setScreen('ai')}
            >
                🎤 말하기
            </button>
            <button className="talk-close-btn" onClick={() => setScreen('home')}>❌ 닫기</button>
          </div>
        </div>
      )}
      {screen === 'ai' && (
        <div className="home-card ai-card">
            <div className="ai-content">
            <div className="ai-robot">🌱</div>

            <div className="speech-bubble">
                안녕하세요 어르신<br />
                오늘은 어떤 하루를<br />
                보내셨나요?
            </div>
            </div>

            <div className="voice-wave">▂▃▅▆▇▆▅▃▂▃▅▆▇▆▅</div>
            <p className="listening-text">말씀을 듣고 있어요...</p>

            <button className="stop-btn" onClick={() => setScreen('home')}>
            ■ 그만하기
            </button>
        </div>
        )}
    </div>
  );
};

export default ElderPage;
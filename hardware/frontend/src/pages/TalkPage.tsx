import React from 'react';

interface TalkPageProps {
  onStartTalk: () => void;
  onClose: () => void;
}

const TalkPage: React.FC<TalkPageProps> = ({
  onStartTalk,
  onClose,
}) => {
  return (
    <div className="home-card talk-card">
      <h1 className="talk-title">무엇을 이야기할까요?</h1>
      <div className="talk-robot">🌱</div>

      <div className="talk-buttons">
        <button
          type="button"
          className="talk-main-btn"
          onClick={onStartTalk}
        >
          🎤 말하기
        </button>

        <button className="talk-close-btn" onClick={onClose}>
          ❌ 닫기
        </button>
      </div>
    </div>
  );
};

export default TalkPage;
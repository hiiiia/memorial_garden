import React from 'react';

interface HelpPageProps {
  onClose: () => void;
}

const HelpPage: React.FC<HelpPageProps> = ({ onClose }) => {
  return (
    <div className="home-card help-card">
      <div className="help-image">
        👵
      </div>

      <div className="help-content">
        <h1 className="help-title">
          도움이 필요하신가요?
        </h1>

        <p className="help-text">
          가족에게 전화로 연결해 드릴게요
        </p>

        <button
          className="help-call-btn"
          onClick={() => {
            alert('보호자 연결 기능');
          }}
        >
          📞 가족에게 전화
        </button>

        <button className="help-no-btn" onClick={onClose}>
          ❌ 아니요
        </button>
      </div>
    </div>
  );
};

export default HelpPage;
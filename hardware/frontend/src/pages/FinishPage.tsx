import React from 'react';

interface FinishPageProps {
  onConfirm: () => void;
}

const FinishPage: React.FC<FinishPageProps> = ({ onConfirm }) => {
  return (
    <div className="home-card finish-card">
      <div className="finish-left">
        <div className="finish-check">✓</div>
        <p className="finish-main-text">가족에게 보냈어요!</p>
      </div>

      <div className="finish-right">
        <div className="finish-family-row">
          <div className="finish-profile">👩</div>
          <p className="finish-family-text">
            보호자에게<br />
            전송되었습니다.
          </p>
        </div>

        <button className="finish-btn" onClick={onConfirm}>
          확인
        </button>
      </div>
    </div>
  );
};

export default FinishPage;
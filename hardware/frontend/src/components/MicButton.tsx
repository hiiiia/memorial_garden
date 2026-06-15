import React from 'react';

type MicButtonProps = {
  state: 'idle' | 'listening' | 'processing' | 'speaking';
  onClick: () => void;
};

const MicButton: React.FC<MicButtonProps> = ({ state, onClick }) => {
  const isIdle = state === 'idle';

  return (
    <footer className="footer-area">
      <button 
        className={`mic-button ${!isIdle ? 'disabled' : ''}`}
        onClick={onClick}
        disabled={!isIdle}
      >
        {isIdle ? '여기를 눌러서 말씀하세요' : '잠시만 기다려주세요'}
      </button>
    </footer>
  );
};

export default MicButton;
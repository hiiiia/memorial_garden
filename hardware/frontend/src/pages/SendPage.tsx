import React from 'react';

interface SendPageProps {
  onSend: () => void;
  onStop: () => void;
}

const SendPage: React.FC<SendPageProps> = ({
  onSend,
  onStop,
}) => {
  return (
    <div className="home-card send-card">
      <h1 className="send-title">가족에게 보내기</h1>

      <div className="send-content">
        <div className="send-left">
          <div className="send-envelope">💌</div>

          <p className="send-question">
            가족에게 오늘의 이야기를<br />
            보내시겠어요?
          </p>
        </div>

        <div className="send-buttons">
          <button className="send-main-btn" onClick={onSend}>
            ✉ 보내기
          </button>

          <button className="send-stop-btn" onClick={onStop}>
            ■ 그만하기
          </button>
        </div>
      </div>
    </div>
  );
};

export default SendPage;
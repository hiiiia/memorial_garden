import React from 'react';

interface PairingData {
  guardianName: string;
  mappingId: number | null;
}

interface GreetingData {
  text: string;
  audio_url: string;
}

interface PopupProps {
  showPairingPopup: boolean;
  pairingData: PairingData;
  showNotification: string | null;
  greetingData: GreetingData | null;
  onAcceptPairing: () => void;
  onRejectPairing: () => void;
  onGreetingChat: () => void;
  onGreetingClose: () => void;
}

const Popup: React.FC<PopupProps> = ({
  showPairingPopup,
  pairingData,
  showNotification,
  greetingData,
  onAcceptPairing,
  onRejectPairing,
  onGreetingChat,
  onGreetingClose,
}) => {
  return (
    <>
      {showPairingPopup && (
        <div className="pairing-popup-overlay">
          <div className="pairing-popup-modal">
            <h1 className="pairing-popup-title">👨‍👩‍👧 가족 연동 요청</h1>

            <p className="pairing-popup-text">
              <strong>{pairingData.guardianName}</strong> 님이<br />
              기기 연동을 요청하셨습니다.<br />
              연결을 수락하시겠습니까?
            </p>

            <div className="pairing-popup-buttons">
              <button
                onClick={onAcceptPairing}
                className="pairing-popup-btn accept"
              >
                ⭕ 수락하기
              </button>

              <button
                onClick={onRejectPairing}
                className="pairing-popup-btn reject"
              >
                ❌ 아니요
              </button>
            </div>
          </div>
        </div>
      )}

      {showNotification && (
        <div className="notification-popup">
          🔔 {showNotification}
        </div>
      )}

      {greetingData && (
        <div className="notification-popup greeting-popup">
          <div className="popup-content greeting-content">
            <h2 className="greeting-title">💌 어르신, 안녕하세요!</h2>

            <p className="greeting-text">{greetingData.text}</p>

            <div className="greeting-buttons">
              <button
                className="greeting-btn btn-listen"
                onClick={() => {
                  const audio = new Audio(greetingData.audio_url);
                  audio.play();
                }}
              >
                🔊 다시 듣기
              </button>

              <button
                className="greeting-btn btn-chat"
                onClick={onGreetingChat}
              >
                ✍️ 대화 나누기
              </button>

              <button
                className="greeting-btn btn-close"
                onClick={onGreetingClose}
              >
                닫기
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
};

export default Popup;
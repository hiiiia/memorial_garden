import React, { useState } from 'react';

interface Guardian {
  mappingId: number;
  guardianName: string;
}

interface SendPageProps {
  guardians: Guardian[];
  onSend: (guardianIds: number[]) => void;
  onStop: () => void;
}

const SendPage: React.FC<SendPageProps> = ({
  guardians,
  onSend,
  onStop,
}) => {
  const [selectedGuardianIds, setSelectedGuardianIds] = useState<number[]>([]);
  const [showGuardianModal, setShowGuardianModal] = useState(false);

  const toggleGuardian = (mappingId: number) => {
    setSelectedGuardianIds((prev) => {
      if (prev.includes(mappingId)) {
        return prev.filter((id) => id !== mappingId);
      }
      return [...prev, mappingId];
    });
  };

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

          <button
            className="guardian-open-btn"
            onClick={() => setShowGuardianModal(true)}
          >
            👥 보호자 선택
          </button>

          <p className="guardian-count">
            선택된 보호자 {selectedGuardianIds.length}명
          </p>
        </div>

        <div className="send-buttons">
          <button
            className="send-main-btn"
            onClick={() => onSend(selectedGuardianIds)}
            disabled={selectedGuardianIds.length === 0}
          >
            ✉ 보내기
          </button>

          <button className="send-stop-btn" onClick={onStop}>
            ■ 그만하기
          </button>
        </div>
      </div>

      {showGuardianModal && (
        <div className="guardian-modal-bg">
          <div className="guardian-modal">
            <h2 className="guardian-modal-title">보낼 보호자를 선택하세요</h2>

            <div className="guardian-modal-list">
              {guardians.map((guardian) => (
                <button
                  key={guardian.mappingId}
                  className={`guardian-select-btn ${
                    selectedGuardianIds.includes(guardian.mappingId)
                      ? 'selected'
                      : ''
                  }`}
                  onClick={() => toggleGuardian(guardian.mappingId)}
                >
                  👤 {guardian.guardianName} 보호자님
                </button>
              ))}
            </div>

            <div className="guardian-modal-buttons">
              <button
                className="guardian-cancel-btn"
                onClick={() => {
                  setSelectedGuardianIds([]);
                  setShowGuardianModal(false);
                }}
              >
                취소
              </button>

              <button
                className="guardian-confirm-btn"
                onClick={() => setShowGuardianModal(false)}
              >
                확인
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default SendPage;
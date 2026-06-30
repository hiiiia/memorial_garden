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

          <div className="guardian-list">
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
    </div>
  );
};

export default SendPage;
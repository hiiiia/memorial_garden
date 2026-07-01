import React from 'react';

type AgentState = 'idle' | 'listening' | 'processing' | 'speaking';

interface AiPageProps {
  aiText: string;
  agentState: AgentState;
  getStatusText: () => string;
  onStop: () => void;
  isStopDisabled?: boolean;
}

const AiPage: React.FC<AiPageProps> = ({
  aiText,
  agentState,
  getStatusText,
  onStop,
  isStopDisabled = false,
}) => {
  return (
    <div className="home-card ai-card">
      <div className="ai-content">
        <div className="ai-robot">🌱</div>

        <div className="speech-bubble">
          {aiText.split('\n').map((line, idx) => (
            <React.Fragment key={idx}>
              {line}<br />
            </React.Fragment>
          ))}
        </div>
      </div>

      <div
        className="voice-wave"
        style={{
          opacity:
            agentState === 'listening' || agentState === 'speaking'
              ? 1
              : 0.2,
        }}
      >
        ▂▃▅▆▇▆▅▃▂▃▅▆▇▆▅
      </div>

      <p className="listening-text">{getStatusText()}</p>

      <button className="stop-btn" onClick={onStop} disabled={isStopDisabled}>
        ■ 그만하기
      </button>
    </div>
  );
};

export default AiPage;

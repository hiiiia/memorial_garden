import React from 'react';

type AgentState = 'idle' | 'listening' | 'processing' | 'speaking' | 'error';

interface AiPageProps {
  aiText: string;
  agentState: AgentState;
  getStatusText: () => string;
  //onStop: () => void;
  isStopDisabled?: boolean;
  onStart: () => void; // 대화시작 (idle일 때)
  onSend: () => void;  // 보내기 (listening일 때)
  onEnd: () => void;   // 대화종료 (항상)
}

const AiPage: React.FC<AiPageProps> = ({
  aiText,
  agentState,
  getStatusText,
  onStart,
  onSend,
  onEnd,
  // onStop,
  isStopDisabled = false,
}) => {
  return (
    <div className="home-card ai-card">
      
      <button className="btn-end" onClick={onEnd}>
        대화종료
      </button>

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

      {/* <button className="stop-btn" onClick={onStop} disabled={isStopDisabled}>
        ■ 그만하기
      </button> */}

      <div className="action-area">
        {/* 1. 녹음시작 버튼: idle 일 때만 활성화 */}
        <button 
          className="action-btn btn-start" 
          onClick={onStart}
          disabled={agentState !== 'idle'}
        >
          이야기시작
        </button>

        {/* 2. 녹음종료 버튼: listening 일 때만 활성화 */}
        <button 
          className="action-btn btn-stop" 
          onClick={onSend}
          disabled={agentState !== 'listening'}
        >
          이야기종료
        </button>
      </div>



    </div>
  );
};

export default AiPage;

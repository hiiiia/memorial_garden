import React, { useState, useEffect, useRef } from 'react';
// 팀원이 작성한 CSS 파일 경로에 맞게 수정해주세요. (예: import '../css/ElderPage.css';)
import '../css/Kiosk.css'; 

type Screen = 'home' | 'talk' | 'ai';
type AgentState = 'idle' | 'listening' | 'processing' | 'speaking';

const KioskPage: React.FC = () => {
  // 1. 화면 전환 상태 (팀원 코드)
  const [screen, setScreen] = useState<Screen>('home');
  
  // 2. 파이썬 에이전트 통신 상태 (기존 코드)
  const [agentState, setAgentState] = useState<AgentState>('idle');
  const [wsConnected, setWsConnected] = useState<boolean>(false);
  const [aiText, setAiText] = useState<string>('안녕하세요 어르신\n오늘은 어떤 하루를\n보내셨나요?');

  const wsRef = useRef<WebSocket | null>(null);

  // 🔌 웹소켓 연결 및 하드웨어 신호 수신 로직
  useEffect(() => {
    const connectWebSocket = () => {
      const ws = new WebSocket('ws://localhost:8765');

      ws.onopen = () => setWsConnected(true);

      ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        
        // 하드웨어 상태 변화 수신
        if (data.status) {
          setAgentState(data.status);
          
          // 하드웨어 버튼(물리 버튼)을 눌러서 갑자기 듣기 시작하면 자동으로 AI 화면으로 전환
          if (data.status !== 'idle' && screen !== 'ai') {
            setScreen('ai');
          }
        }
        
        // AI 최종 응답(자막) 수신
        if (data.type === 'AI_RESPONSE' && data.text) {
          setAiText(data.text);
        }
      };

      ws.onclose = () => {
        setWsConnected(false);
        setTimeout(connectWebSocket, 3000); // 끊기면 3초 후 재연결
      };

      wsRef.current = ws;
    };

    connectWebSocket();
    return () => wsRef.current?.close();
  }, [screen]);

  // 🎤 '말하기' 버튼 클릭 시 실행되는 함수
  const handleStartTalk = () => {
    setScreen('ai'); // AI 화면으로 넘기기
    if (wsRef.current && wsConnected) {
      // 파이썬 쪽으로 강제 녹음 시작 명령 전송
      wsRef.current.send(JSON.stringify({ command: 'force_record' }));
    }
  };

  // ⏳ 현재 에이전트 상태에 따른 하단 안내 문구 변환
  const getStatusText = () => {
    if (agentState === 'listening') return '말씀을 듣고 있어요...';
    if (agentState === 'processing') return '생각하는 중이에요...';
    if (agentState === 'speaking') return '이야기하고 있어요...';
    return '대기 중...';
  };

  return (
    <div className="elder-page">
      {/* 화면 1: 메인 홈 화면 */}
      {screen === 'home' && (
        <div className="home-card">
          <div className="logo">🌱 기억정원</div>
          <div className="home-content">
            <div className="robot">🌱</div>
            <div className="info">
              <p className="hello">안녕하세요!</p>
              <h1>김영희 어르신</h1>
              <p className="sub-text">오늘도 좋은 하루 보내세요 😊</p>

              <div className="button-group">
                <button className="menu-btn help-btn">
                  ☎<span>도움<br />요청하기</span>
                </button>
                <button className="menu-btn talk-btn" onClick={() => setScreen('talk')}>
                  🎤<span>이야기<br />시작하기</span>
                </button>
                <button className="menu-btn diary-btn">📖<span>오늘의 일기</span></button>
                <button className="menu-btn memory-btn">🖼<span>추억 보관함</span></button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* 화면 2: 대화 시작 전 확인 화면 */}
      {screen === 'talk' && (
        <div className="home-card talk-card">
          <h1 className="talk-title">무엇을 이야기할까요?</h1>
          <div className="talk-robot">🌱</div>
          <div className="talk-buttons">
            <button
              type="button"
              className="talk-main-btn"
              onClick={handleStartTalk} // ⬅️ 웹소켓 전송 함수 연결
            >
              🎤 말하기
            </button>
            <button className="talk-close-btn" onClick={() => setScreen('home')}>❌ 닫기</button>
          </div>
        </div>
      )}

      {/* 화면 3: AI 대화 진행 화면 */}
      {screen === 'ai' && (
        <div className="home-card ai-card">
          <div className="ai-content">
            <div className="ai-robot">🌱</div>

            <div className="speech-bubble">
              {/* 파이썬에서 보내준 텍스트를 줄바꿈 처리하여 렌더링 */}
              {aiText.split('\n').map((line, idx) => (
                <React.Fragment key={idx}>
                  {line}<br />
                </React.Fragment>
              ))}
            </div>
          </div>

          {/* 에이전트 상태에 따라 음성 파동 애니메이션 불투명도 조절 */}
          <div 
            className="voice-wave" 
            style={{ opacity: agentState === 'listening' || agentState === 'speaking' ? 1 : 0.2 }}
          >
            ▂▃▅▆▇▆▅▃▂▃▅▆▇▆▅
          </div>
          
          {/* 상태에 맞는 동적 텍스트 출력 */}
          <p className="listening-text">{getStatusText()}</p>

          <button className="stop-btn" onClick={() => {
            setScreen('home');
            // 필요하다면 파이썬으로 강제 종료(stop) 신호를 보낼 수도 있습니다.
          }}>
            ■ 그만하기
          </button>
        </div>
      )}
    </div>
  );
};

export default KioskPage;
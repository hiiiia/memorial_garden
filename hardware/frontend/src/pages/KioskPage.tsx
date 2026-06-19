import React, { useState, useEffect, useRef } from 'react';
// 팀원이 작성한 CSS 파일 경로에 맞게 수정해주세요. (예: import '../css/ElderPage.css';)
import '../css/Kiosk.css'; 

type Screen = 'home' | 'talk' | 'ai' | 'diary' | 'memory' | 'send' | 'finish' | 'detail' | 'help';
type AgentState = 'idle' | 'listening' | 'processing' | 'speaking';

interface MemoryData {
  image: React.ReactNode | string;
  title: string;
  date: string;
  desc: string[];
}
const KioskPage: React.FC = () => {
  // 1. 화면 전환 상태 (팀원 코드)
  const [screen, setScreen] = useState<Screen>('home');
  
  // 2. 파이썬 에이전트 통신 상태 (기존 코드)
  const [agentState, setAgentState] = useState<AgentState>('idle');
  const [wsConnected, setWsConnected] = useState<boolean>(false);
  const [aiText, setAiText] = useState<string>('안녕하세요 어르신\n오늘은 어떤 하루를\n보내셨나요?');

  // 선택된 상세 추억 상태
  const [selectedMemory, setSelectedMemory] = useState<MemoryData | null>(null);
  
  // 추억 보관함 페이징(슬라이드) 상태
  const [memoryPage, setMemoryPage] = useState(0);

  // 실제 데이터가 있다고 가정 (기존 데이터 배열로 교체하세요)
  const allMemories: MemoryData[] = []; 
  
  // 화면에 보여줄 메모리 개수 계산 (예: 한 번에 3개씩 렌더링)
  const itemsPerPage = 3;
  const visibleMemories = allMemories.slice(
    memoryPage * itemsPerPage, 
    (memoryPage + 1) * itemsPerPage
  );

  // 좌우 화살표 클릭 핸들러
  const handlePrevMemory = () => {
    if (memoryPage > 0) setMemoryPage(prev => prev - 1);
  };

  const handleNextMemory = () => {
    if ((memoryPage + 1) * itemsPerPage < allMemories.length) {
      setMemoryPage(prev => prev + 1);
    }
  };

  const wsRef = useRef<WebSocket | null>(null);

// 🔌 웹소켓 연결 및 하드웨어 신호 수신 로직
  useEffect(() => {
    const connectWebSocket = () => {
      const ws = new WebSocket('ws://localhost:8765');

      ws.onopen = () => setWsConnected(true);

      ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        
        if (data.status) {
          setAgentState(data.status);
          
          // 💡 수정됨: 함수형 업데이트를 사용하여 항상 최신 화면 상태(prev)를 확인합니다.
          // 이렇게 하면 의존성 배열에 screen을 넣지 않아도 안전하게 비교할 수 있습니다.
          setScreen((prevScreen) => {
            if (data.status !== 'idle' && prevScreen !== 'ai') {
              return 'ai';
            }
            return prevScreen; // 조건에 안 맞으면 기존 화면 유지
          });
        }
        
        if (data.type === 'AI_RESPONSE' && data.text) {
          setAiText(data.text);
        }
      };

      ws.onclose = () => {
        setWsConnected(false);
        setTimeout(connectWebSocket, 3000);
      };

      wsRef.current = ws;
    };

    connectWebSocket();
    
    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  // 수정됨: screen을 빼고 빈 배열로 두어, 화면이 바뀌어도 웹소켓이 끊기지 않게 합니다.
  }, []);

// 🎤 '말하기' 버튼 클릭 시 실행되는 함수
  const handleStartTalk = () => {
    setScreen('ai'); // AI 화면으로 넘기기
    
    // 수정됨: wsConnected 대신 실제 웹소켓의 연결 상태(readyState)를 확인합니다.
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      // 파이썬 쪽으로 강제 녹음 시작 명령 전송
      wsRef.current.send(JSON.stringify({ command: 'force_record' }));
    } else {
      console.warn("⏳ 웹소켓 연결을 기다리는 중입니다. 잠시 후 다시 눌러주세요.");
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
                <button
                  className="menu-btn diary-btn"
                  onClick={() => setScreen('diary')}
                >
                  📖<span>오늘의<br />일기</span>
                </button>
                <button
                  className="menu-btn memory-btn"
                  onClick={() => setScreen('memory')}
                >
                  🖼<span>추억<br />보관함</span>
                </button>
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
            setScreen('diary');
            // 필요하다면 파이썬으로 강제 종료(stop) 신호를 보낼 수도 있습니다.
          }}>
            ■ 그만하기
          </button>
        </div>
      )}
            {screen === 'diary' && (
        <div className="home-card diary-card">
          <h1 className="diary-title">오늘의 일기</h1>

          <div className="diary-content">
            <div className="diary-image">
              시장 그림
            </div>

            <div className="diary-text-box">
              오늘은 시장에 다녀왔어요.<br />
              채소도 사고 친구도 만나서<br />
              즐거웠어요.
            </div>
          </div>

          <div className="diary-buttons">
            <button className="diary-listen-btn">🔊 다시듣기</button>

            <button className="diary-next-btn" onClick={() => setScreen('send')}>
              ➡ 다음
            </button>
          </div>
        </div>
      )}
      {screen === 'send' && (
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
              <button className="send-main-btn" onClick={() => setScreen('finish')}>
                ✉ 보내기
              </button>

              <button
                className="send-stop-btn"
                onClick={() => setScreen('home')}
              >
                ■ 그만하기
              </button>
            </div>
          </div>
        </div>
      )}

      {screen === 'finish' && (
        <div className="home-card finish-card">
          <div className="finish-left">
            <div className="finish-check">✓</div>
            <p className="finish-main-text">가족에게 보냈어요!</p>
          </div>

          <div className="finish-right">
            <div className="finish-family-row">
              <div className="finish-profile">👩</div>
              <p className="finish-family-text">
                딸(김지현)에게<br />
                전송되었습니다.
              </p>
            </div>

            <button className="finish-btn" onClick={() => setScreen('home')}>
              확인
            </button>
          </div>
        </div>
      )}
      {screen === 'memory' && (
        <div className="home-card memory-card">
          <h1 className="memory-title">나의 추억</h1>

          <div className="memory-content">
            <button className="memory-arrow" onClick={handlePrevMemory}>
              ‹
            </button>

            <div className="memory-list">
              {visibleMemories.map((memory, index) => (
                <div className="memory-item" key={index}>
                  <div className="memory-image">{memory.image}</div>

                  <div className="memory-info">
                    <h2>{memory.title}</h2>
                    <p>{memory.date}</p>
                  </div>

                  <div className="memory-action-buttons">
                    <button
                      className="memory-send-btn"
                      onClick={() => {
                        setSelectedMemory(memory);
                        setScreen('finish');
                      }}
                    >
                      ✉ 보내기
                    </button>

                    <button
                      className="memory-view-btn"
                      onClick={() => {
                        setSelectedMemory(memory);
                        setScreen('detail');
                      }}
                    >
                      🔍 보기
                    </button>
                  </div>
                </div>
              ))}
            </div>

            <button className="memory-arrow" onClick={handleNextMemory}>
              ›
            </button>
          </div>

          <button className="memory-close-btn" onClick={() => setScreen('home')}>
            ❌ 닫기
          </button>
        </div>
      )}
      {screen === 'detail' && (
        <div className="home-card detail-card">
          <div className="detail-top">
            <div className="detail-image-box">
              {selectedMemory?.image}
            </div>

            <div className="detail-info">
              <h1>{selectedMemory?.title}</h1>
              <p className="detail-date">{selectedMemory?.date}</p>

              <p className="detail-desc">
                {selectedMemory?.desc.map((line : string, index: number) => (
                  <React.Fragment key={index}>
                    {line}
                    <br />
                  </React.Fragment>
                ))}
              </p>
            </div>
          </div>

          <div className="detail-buttons">
            <button className="detail-listen-btn">
              🔊 다시듣기
            </button>

            <button
              className="detail-close-btn"
              onClick={() => setScreen('memory')}
            >
              ❌ 닫기
            </button>
          </div>
        </div>
      )}
      {screen === 'help' && (
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

            <button
              className="help-no-btn"
              onClick={() => setScreen('home')}
            >
              ❌ 아니요
            </button>

          </div>
        </div>
      )}
    </div>
  );
};

export default KioskPage;
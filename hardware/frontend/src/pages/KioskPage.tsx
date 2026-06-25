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

interface Diary {
  id: string | number;
  content: string;
  image_url: string;
  created_at: string; // 예: "2026년 06월 24일"
}

const KioskPage: React.FC = () => {
  // ==========================================
  // 1. 화면 및 통신 상태 관리
  // ==========================================
  // 화면 전환 상태
  const [screen, setScreen] = useState<Screen>('home');

  // 파이썬 에이전트 통신 상태
  const [agentState, setAgentState] = useState<AgentState>('idle');
  const [wsConnected, setWsConnected] = useState<boolean>(false);
  const [aiText, setAiText] = useState<string>('안녕하세요 어르신\n오늘은 어떤 하루를\n보내셨나요?');

  // 주기적 안부 묻기 on/off 상태 
  const [isGreetingEnabled, setIsGreetingEnabled] = useState<boolean>(true);
  // 안부 데이터 변수
  const [greetingData, setGreetingData] = useState<{text: string, audio_url: string} | null>(null);

  // 연동 팝업 상태
  const [showPairingPopup, setShowPairingPopup] = useState<boolean>(false);
  const [pairingData, setPairingData] = useState<{ guardianName: string; mappingId: number | null }>({
    guardianName: '',
    mappingId: null
  });

  // ==========================================
  // 2. 그림일기(추억) 데이터 상태 관리
  // ==========================================
  const [diaries, setDiaries] = useState<Diary[]>([]);
  const [selectedDiary, setSelectedDiary] = useState<Diary | null>(null); // 기존 selectedMemory 대체
  const [showNotification, setShowNotification] = useState<string | null>(null); // 새 일기 알림 팝업

  // 백엔드에서 일기 데이터 불러오기
  const fetchDiaries = async () => {

    console.log("다이어리 데이터 get 시작")
    
    try {
      const token = localStorage.getItem('DEVICE_TOKEN');
      console.log("DEVICE_TOKEN =",token);

      if (!token) return;

      const response = await fetch("http://192.168.1.82:8000/api/v1/dependent/diary", {
        method: "GET",
        headers: {
          "Authorization": `Bearer ${token}`,
          "Content-Type": "application/json"
        }
      });
      
      const resData = await response.json();

      // 🌟 수정됨: status_code 검사를 빼고, 데이터(diaries)가 존재하는지만 확실하게 확인!
      if (resData.data && resData.data.diaries) {
        console.log("✅ 일기장 데이터 로드 완료:", resData.data.diaries);
        setDiaries(resData.data.diaries); // React 상태에 일기 데이터 저장
      } else {
        console.warn("⚠️ 일기 데이터가 없습니다.", resData);
      }

    } catch (error) {
      console.error("일기장 데이터를 불러오는데 실패했습니다:", error);
    }
  };

  // ==========================================
  // 3. [오늘의 일기] 날짜 포맷 및 필터링
  // ==========================================
  const getTodayString = () => {
    const now = new Date();
    const y = now.getFullYear();
    const m = String(now.getMonth() + 1).padStart(2, '0');
    const d = String(now.getDate()).padStart(2, '0');
    return `${y}년 ${m}월 ${d}일`;
  };

  const todayFormatted = getTodayString();
  const todayDiary = diaries.find((diary) => diary.created_at === todayFormatted);
  
  // ==========================================
  // 4. [나의 추억] 날짜별 그룹핑 + 3개씩 페이징
  // ==========================================
  const ITEMS_PER_PAGE = 3;

  // 상태: 날짜 인덱스와 페이징 인덱스
  const [selectedDateIndex, setSelectedDateIndex] = useState(0); 
  const [itemStartIndex, setItemStartIndex] = useState(0);       

  // 데이터 파생: 고유 날짜 추출 및 현재 뷰 데이터
  const uniqueDates = Array.from(new Set(diaries.map(d => d.created_at)));
  const currentViewDate = uniqueDates[selectedDateIndex];
  const diariesForDate = diaries.filter((d) => d.created_at === currentViewDate);
  const visibleMemories = diariesForDate.slice(itemStartIndex, itemStartIndex + ITEMS_PER_PAGE);

  // 날짜가 변경되거나 일기가 업데이트되면, 페이지를 처음(0)으로 리셋
  useEffect(() => {
    setItemStartIndex(0);
  }, [selectedDateIndex, diaries]);

  // --- 핸들러: 날짜 이동 (상단 네비게이션) ---
  const handlePrevDate = () => {
    if (selectedDateIndex < uniqueDates.length - 1) setSelectedDateIndex((prev) => prev + 1);
  };
  const handleNextDate = () => {
    if (selectedDateIndex > 0) setSelectedDateIndex((prev) => prev - 1);
  };

  // --- 핸들러: 아이템 페이징 (중앙 화살표) ---
  const handlePrevItems = () => {
    if (itemStartIndex - ITEMS_PER_PAGE >= 0) setItemStartIndex((prev) => prev - ITEMS_PER_PAGE);
  };
  const handleNextItems = () => {
    if (itemStartIndex + ITEMS_PER_PAGE < diariesForDate.length) setItemStartIndex((prev) => prev + ITEMS_PER_PAGE);
  };


  const wsRef = useRef<WebSocket | null>(null);

  // 🔌 웹소켓 연결 및 하드웨어 신호 수신 로직
  useEffect(() => {
    const connectWebSocket = () => {
      const ws = new WebSocket('ws://localhost:8765');

      ws.onopen = () => {
        setWsConnected(true);
        ws.send(JSON.stringify({ command: 'get_token' }));
      };

      ws.onmessage = (event) => {
        const data = JSON.parse(event.data);

        console.log("🌟 [React 웹소켓 수신]:", data);

        // 보호자 연동 요청이 들어왔을 때 팝업 띄우기
        if (data.action === 'SHOW_PAIRING_POPUP') {
          setPairingData({
            guardianName: data.data.guardian_name,
            mappingId: data.data.mapping_id
          });
          setShowPairingPopup(true); // 팝업 열기
        }
        
        // AI 오케스트레이터가 작업 완료 후 호출
        if (data.action === "NEW_DIARY_ARRIVED") {
          // 화면에 큼직한 알림 띄우기
          setShowNotification(data.data.message);
          
          // 5초 뒤에 알림 자동 닫기
          setTimeout(() => setShowNotification(null), 5000);
        }

        if (data.status) {
          setAgentState(data.status);

          // 수정됨: 함수형 업데이트를 사용하여 항상 최신 화면 상태(prev)를 확인합니다.
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

        if(data.token){
          const token = String(data.token);
          const hw_mac = String(data.HW_MAC);
          localStorage.setItem('DEVICE_TOKEN', token);
          localStorage.setItem('HW_MAC', hw_mac);
          console.log('✅ 토큰이 안전하게 저장되었습니다.');
        }

        if (data.action === 'INIT_SETTINGS') {
          console.log("⚙️ 기기 초기 설정값 로드 완료:", data.data);
          setIsGreetingEnabled(data.data.proactive_greeting_enabled);
        }

        if (data.action === 'PROACTIVE_GREETING_ARRIVED') {
              console.log("💌 [WS] 안부 메시지 도착:", data.data);
              
              // 1. 화면에 팝업 띄우기
              setGreetingData({
                text: data.data.text,
                audio_url: data.data.audio_url
              });

              // 2. 오디오 자동 재생 시도
              if (data.data.audio_url) {
                const audio = new Audio(data.data.audio_url);
                audio.play().catch(error => {
                  console.warn("🔇 브라우저 자동 재생 정책으로 인해 소리가 차단되었습니다:", error);
                  // (주의: 브라우저는 사용자가 화면을 한 번이라도 클릭/터치해야 자동 재생을 허용합니다)
                });
              }
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

  const handleAcceptPairing = () => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({
        target: 'cloud', // 파이썬 에이전트에게 이건 클라우드로 보내라고 지시
        payload: {
          action: 'PAIRING_ACCEPTED',
          mapping_id: pairingData.mappingId
        }
      }));
      setShowPairingPopup(false); // 팝업 닫기
      alert(`${pairingData.guardianName} 님과 기기가 연결되었습니다!`); // 어르신을 위한 완료 안내
    }
  };

  //  연동 거절 버튼 클릭 핸들러
  const handleRejectPairing = () => {
    setShowPairingPopup(false);
  };


  // 🚨 긴급 도움 요청 함수
  const handleEmergencyRequest = async () => {
    // 1. 로컬 스토리지에서 HW_MAC 주소 꺼내기
    const macAddress = localStorage.getItem('HW_MAC');

    if (!macAddress) {
      console.error("🚨 기기 MAC 주소를 찾을 수 없습니다. (HW_MAC 확인 필요)");
      alert("기기 정보가 없습니다. 관리자에게 문의하세요."); // 에러 방지용
      return;
    }

    try {
      console.log(`[Emergency] 🚨 긴급 호출 시도 중... (MAC: ${macAddress})`);

      // 2. 백엔드로 POST 요청 보내기 (인증 토큰 없음)
      const response = await fetch("http://192.168.1.82:8000/api/v1/dependent/emergency", {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          mac_address: macAddress
        })
      });

      const resData = await response.json();
      
      // 3. 결과 처리
      if (response.ok) {
        console.log("✅ 긴급 호출 성공:", resData);
        //  어르신이 안심할 수 있도록 화면에 팝업을 띄워주는 것이 좋습니다!
        setShowNotification("보호자에게 긴급 알림을 전송했습니다."); 
      } else {
        console.error("🚨 긴급 호출 실패:", resData);
      }
    } catch (error) {
      console.error("🚨 서버 통신 오류 (긴급 호출):", error);
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
              <button 
                className="menu-btn help-btn"
                onClick={handleEmergencyRequest} 
              >
                ☎<span>도움<br />요청하기</span>
              </button>

                <button className="menu-btn talk-btn" onClick={() => setScreen('talk')}>
                  🎤<span>이야기<br />시작하기</span>
                </button>


                {/* 오늘의 일기 버튼 */}
                <button
                  className="menu-btn diary-btn"
                  onClick={async () => {
                    // 🌟 async/await를 추가해서 순서를 강제합니다!
                    await fetchDiaries(); // 1. 데이터가 도착할 때까지 여기서 멈춰서 기다림
                    setScreen('diary');   // 2. 데이터가 다 도착하면 그제서야 화면을 넘김
                  }}
                >
                  📖<span>오늘의<br />일기</span>
                </button>

                {/* 추억 보관함 버튼 */}
                <button
                  className="menu-btn memory-btn"
                  onClick={async () => {
                    await fetchDiaries(); // 1. 데이터가 도착할 때까지 기다림
                    setScreen('memory');  // 2. 다 도착하면 화면을 넘김
                  }}
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

      {/* ========================================== */}
      {/* 1. 오늘의 일기 (오늘 날짜만)                   */}
      {/* ========================================== */}
      {screen === 'diary' && (
        <div className="home-card diary-card">
          <h1 className="diary-title">오늘의 일기</h1>
          <p className="diary-date">{todayFormatted}</p>

          {todayDiary ? (
            <div className="diary-content">
              <div className="diary-image">
                {todayDiary.image_url ? (
                  <img src={todayDiary.image_url} alt="오늘의 그림" />
                ) : (
                  <span>그림 준비 중 🎨</span>
                )}
              </div>

              <div className="diary-text-box">
                {todayDiary.content}
              </div>
            </div>
          ) : (
            <div className="diary-empty">
              <span className="empty-icon">📭</span>
              <p>어르신, 오늘은 아직 일기를 쓰지 않으셨어요.</p>
              <small>대화를 나누면 일기가 자동으로 만들어집니다.</small>
            </div>
          )}

          <div className="diary-buttons">
            {todayDiary && <button className="diary-listen-btn">🔊 다시듣기</button>}
            <button className="diary-next-btn" onClick={() => setScreen('send')}>
              ➡ 다음
            </button>
          </div>
        </div>
      )}

      {/* ========================================== */}
      {/* 2. 나의 추억 (날짜 선택 + 3개씩 페이징 결합)       */}
      {/* ========================================== */}
      {screen === 'memory' && (
        <div className="home-card memory-card">
          <h1 className="memory-title">나의 추억</h1>
          
          {/* 상단: 날짜 이동 네비게이션 */}
          {uniqueDates.length > 0 && (
            <div className="memory-nav">
              <button 
                onClick={handlePrevDate} 
                disabled={selectedDateIndex === uniqueDates.length - 1}
                className="memory-nav-btn"
              >
                ◀ 과거로
              </button>
              <h2 className="memory-nav-date">{currentViewDate}</h2>
              <button 
                onClick={handleNextDate} 
                disabled={selectedDateIndex === 0}
                className="memory-nav-btn"
              >
                최신으로 ▶
              </button>
            </div>
          )}

          {/* 중앙: 3개씩 보여주는 리스트와 페이징 화살표 */}
          <div className="memory-content">
            <button 
              className="memory-arrow" 
              onClick={handlePrevItems}
              disabled={itemStartIndex === 0}
            >
              ‹
            </button>

            <div className="memory-list">
              {visibleMemories.length > 0 ? (
                visibleMemories.map((memory) => (
                  <div className="memory-item" key={memory.id}>
                    
                    <div className="memory-image">
                      {memory.image_url ? (
                        <img src={memory.image_url} />
                      ) : (
                        <span>🎨</span>
                      )}
                    </div>

                    <div className="memory-action-buttons">
                      <button
                        className="memory-send-btn"
                        onClick={() => {
                          setSelectedDiary(memory);
                          setScreen('finish');
                        }}
                      >
                        ✉ 보내기
                      </button>

                      <button
                        className="memory-view-btn"
                        onClick={() => {
                          setSelectedDiary(memory);
                          setScreen('detail');
                        }}
                      >
                        🔍 보기
                      </button>
                    </div>
                  </div>
                ))
              ) : (
                <div className="memory-empty">
                  <span className="empty-icon">🗂️</span>
                  <p>저장된 추억이 없습니다.</p>
                </div>
              )}
            </div>

            <button 
              className="memory-arrow" 
              onClick={handleNextItems}
              disabled={itemStartIndex + ITEMS_PER_PAGE >= diariesForDate.length}
            >
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
              <img src={selectedDiary?.image_url} />
            </div>

            <div className="detail-info">
              <p className="detail-date">{selectedDiary?.created_at}</p>

              <p className="detail-desc">
                {selectedDiary?.content}
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

      {/* 가족 연동 요청 팝업 (어떤 화면에 있든 최상단에 표시(Modal)) */}
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
                onClick={handleAcceptPairing}
                className="pairing-popup-btn accept"
              >
                ⭕ 수락하기
              </button>
              <button 
                onClick={handleRejectPairing}
                className="pairing-popup-btn reject"
              >
                ❌ 아니요
              </button>
            </div>
          </div>
        </div>
      )}
      {/* 팝업: 새 일기 도착 알림 */}
      {showNotification && (
        <div className="notification-popup">
          🔔 {showNotification}
        </div>

      )}
      
      {/* ========================================== */}
      {/* 안부 묻기 팝업 UI                       */}
      {/* ========================================== */}
      {greetingData && (
        <div className="notification-popup greeting-popup">
          <div className="popup-content greeting-content">
            <h2 className="greeting-title">💌 어르신, 안녕하세요!</h2>
            
            <p className="greeting-text">
              {greetingData.text}
            </p>

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
                onClick={() => {
                  setGreetingData(null); // 팝업 닫기
                  setScreen('send');     // 일기 작성 화면으로 바로 넘기기
                }}
              >
                ✍️ 대화 나누기
              </button>

              <button 
                className="greeting-btn btn-close"
                onClick={() => setGreetingData(null)}
              >
                닫기
              </button>
            </div>
          </div>
        </div>
      )}

    </div>
  );
};

export default KioskPage;
import React, { useState, useEffect, useRef } from 'react';
import { config } from '../config/index';

import '../css/Common.css';
import '../css/HomePage.css';
import '../css/AiPage.css';
import '../css/TalkPage.css';
import '../css/DiaryPage.css';
import '../css/FinishPage.css';
import '../css/SendPage.css';
import '../css/MemoryPage.css';
import '../css/DetailPage.css';
import '../css/HelpPage.css';
import '../css/Popup.css';

import HomePage from './HomePage';
import TalkPage from './TalkPage';
import AiPage from './AiPage';
import SendPage from './SendPage';
import FinishPage from './FinishPage';
import DiaryPage from './DiaryPage';
import MemoryPage from './MemoryPage';
import DetailPage from './DetailPage';
import HelpPage from './HelpPage';
import Popup from './Popup';

type Screen = 'home' | 'talk' | 'ai' | 'diary' | 'memory' | 'send' | 'finish' | 'detail' | 'help';
type AgentState = 'idle' | 'listening' | 'processing' | 'speaking';

interface Diary {
  id: string | number;
  content: string;
  image_url: string;
  created_at: string;
}

interface Guardian {
  mappingId: number;
  guardianName: string;
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
  const [aiText, setAiText] = useState<string>(
    '안녕하세요 어르신\n오늘은 어떤 하루를\n보내셨나요?'
  );

  // 주기적 안부 묻기 on/off 상태 
  const [isGreetingEnabled, setIsGreetingEnabled] = useState<boolean>(true);
  // 안부 데이터 변수
  const [greetingData, setGreetingData] = useState<{
    text: string;
    audio_url: string;
  } | null>(null);

  // 연동 팝업 상태
  const [showPairingPopup, setShowPairingPopup] = useState<boolean>(false);

  const [pairingData, setPairingData] = useState<{
    guardianName: string;
    mappingId: number | null;
  }>({
    guardianName: '',
    mappingId: null,
  });

  const [guardians, setGuardians] = useState<Guardian[]>([]);

  // ==========================================
  // 2. 그림일기(추억) 데이터 상태 관리
  // ==========================================
  const [diaries, setDiaries] = useState<Diary[]>([]);
  const [selectedDiary, setSelectedDiary] = useState<Diary | null>(null);
  const [showNotification, setShowNotification] = useState<string | null>(null);

  const wsRef = useRef<WebSocket | null>(null);

  // 백엔드에서 일기 데이터 불러오기
  const fetchDiaries = async () => {
    console.log('다이어리 데이터 get 시작');

    try {
      const token = localStorage.getItem('DEVICE_TOKEN');
      console.log('DEVICE_TOKEN =', token);

      if (!token) return;

      const response = await fetch(`${config.apiBaseUrl}/api/v1/dependent/diary`, {
        method: 'GET',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });

      const resData = await response.json();

      // 🌟 수정됨: status_code 검사를 빼고, 데이터(diaries)가 존재하는지만 확실하게 확인!
      if (resData.data && resData.data.diaries) {
        console.log('✅ 일기장 데이터 로드 완료:', resData.data.diaries);
        setDiaries(resData.data.diaries);
      } else {
        console.warn('⚠️ 일기 데이터가 없습니다.', resData);
      }
    } catch (error) {
      console.error('일기장 데이터를 불러오는데 실패했습니다:', error);
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
  // 4. [나의 추억] 날짜별 그룹핑 + 2개씩 페이징
  // ==========================================
  const ITEMS_PER_PAGE = 2;

  // 상태: 날짜 인덱스와 페이징 인덱스
  const [selectedDateIndex, setSelectedDateIndex] = useState(0);
  const [itemStartIndex, setItemStartIndex] = useState(0);

  // 데이터 파생: 고유 날짜 추출 및 현재 뷰 데이터
  const uniqueDates = Array.from(new Set(diaries.map((d) => d.created_at)));
  const currentViewDate = uniqueDates[selectedDateIndex];
  const diariesForDate = diaries.filter((d) => d.created_at === currentViewDate);
  const visibleMemories = diariesForDate.slice(
    itemStartIndex,
    itemStartIndex + ITEMS_PER_PAGE
  );

  // 날짜가 변경되거나 일기가 업데이트되면, 페이지를 처음(0)으로 리셋
  useEffect(() => {
    setItemStartIndex(0);
  }, [selectedDateIndex, diaries]);

  // --- 핸들러: 날짜 이동 (상단 네비게이션) ---
  const handlePrevDate = () => {
    if (selectedDateIndex < uniqueDates.length - 1) {
      setSelectedDateIndex((prev) => prev + 1);
    }
  };

  const handleNextDate = () => {
    if (selectedDateIndex > 0) {
      setSelectedDateIndex((prev) => prev - 1);
    }
  };

  // --- 핸들러: 아이템 페이징 (중앙 화살표) ---
  const handlePrevItems = () => {
    if (itemStartIndex - ITEMS_PER_PAGE >= 0) {
      setItemStartIndex((prev) => prev - ITEMS_PER_PAGE);
    }
  };

  const handleNextItems = () => {
    if (itemStartIndex + ITEMS_PER_PAGE < diariesForDate.length) {
      setItemStartIndex((prev) => prev + ITEMS_PER_PAGE);
    }
  };



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

        console.log('🌟 [React 웹소켓 수신]:', data);
        console.log('action 확인:', data.action);
        console.log('data 확인:', data.data);
        console.log('mapping_guardians 확인:', data.data?.mapping_guardians);

        // 보호자 연동 요청이 들어왔을 때 팝업 띄우기
        if (data.action === 'SHOW_PAIRING_POPUP') {
          setPairingData({
            guardianName: data.data.guardian_name,
            mappingId: data.data.mapping_id,
          });
          setShowPairingPopup(true); // 팝업 열기
        }

        // AI 오케스트레이터가 작업 완료 후 호출
        if (data.action === 'NEW_DIARY_ARRIVED') {
          // 화면에 큼직한 알림 띄우기
          setShowNotification(data.data.message);
          // 5초 뒤에 알림 자동 닫기
          setTimeout(() => setShowNotification(null), 5000);
        }

        if (data.status) {
          setAgentState(data.status);

          // 수정됨: 함수형 업데이트를 사용하여 항상 최신 화면 상태(prev)를 확인합니다.
          // 이렇게 하면 의존성 배열에 screen을 넣지 않아도 안전하게 비교할 수 있습니다
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

        if (data.token) {
          const token = String(data.token);
          const hwMac = String(data.HW_MAC);

          localStorage.setItem('DEVICE_TOKEN', token);
          localStorage.setItem('HW_MAC', hwMac);

          console.log('✅ 토큰이 안전하게 저장되었습니다.');
        }

      if (data.action === 'INIT_SETTINGS') {
        console.log('⚙️ 기기 초기 설정값 로드 완료:', data.data);
        setIsGreetingEnabled(data.data.proactive_greeting_enabled);

        if (data.data.mapping_guardians) {
          setGuardians(
            data.data.mapping_guardians.map((guardian: any) => ({
              mappingId: guardian.mapping_id,
              guardianName: guardian.guardian_name,
            }))
          );
        }
      }

        if (data.action === 'PROACTIVE_GREETING_ARRIVED') {
          console.log('💌 [WS] 안부 메시지 도착:', data.data);

          // 1. 화면에 팝업 띄우기
          setGreetingData({
            text: data.data.text,
            audio_url: data.data.audio_url,
          });

          // 2. 오디오 자동 재생 시도
          if (data.data.audio_url) {
            const audio = new Audio(data.data.audio_url);

            audio.play().catch((error) => {
              console.warn('🔇 브라우저 자동 재생 정책으로 인해 소리가 차단되었습니다:', error);
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
      console.warn('⏳ 웹소켓 연결을 기다리는 중입니다. 잠시 후 다시 눌러주세요.');
    }
  };

  const handleAcceptPairing = () => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(
        JSON.stringify({
          target: 'cloud', // 파이썬 에이전트에게 이건 클라우드로 보내라고 지시
          payload: {
            action: 'PAIRING_ACCEPTED',
            mapping_id: pairingData.mappingId,
          },
        })
      );

      setShowPairingPopup(false); // 팝업 닫기
      setGuardians((prev) => {
  const alreadyExists = prev.some(
    (guardian) => guardian.mappingId === pairingData.mappingId
  );

  if (alreadyExists || pairingData.mappingId === null) {
    return prev;
  }

  return [
    ...prev,
    {
      mappingId: pairingData.mappingId,
      guardianName: pairingData.guardianName,
    },
  ];
});
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
      console.error('🚨 기기 MAC 주소를 찾을 수 없습니다. (HW_MAC 확인 필요)');
      alert('기기 정보가 없습니다. 관리자에게 문의하세요.'); // 에러 방지용
      return;
    }

    try {
      console.log(`[Emergency] 🚨 긴급 호출 시도 중... (MAC: ${macAddress})`);

      // 2. 백엔드로 POST 요청 보내기 (인증 토큰 없음)
      const response = await fetch(`${config.apiBaseUrl}/api/v1/dependent/emergency`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          mac_address: macAddress,
        }),
      });

      const resData = await response.json();

      // 3. 결과 처리
      if (response.ok) {
        console.log('✅ 긴급 호출 성공:', resData);
        //  어르신이 안심할 수 있도록 화면에 팝업을 띄워주는 것이 좋습니다!
        setShowNotification('보호자에게 긴급 알림을 전송했습니다.');
      } else {
        console.error('🚨 긴급 호출 실패:', resData);
      }
    } catch (error) {
      console.error('🚨 서버 통신 오류 (긴급 호출):', error);
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
      {screen === 'home' && (
        <HomePage
          onEmergency={handleEmergencyRequest}
          onTalk={() => setScreen('talk')}
          onDiary={async () => {
            await fetchDiaries(); // 1. 데이터가 도착할 때까지 여기서 멈춰서 기다림
            setScreen('diary');   // 2. 데이터가 다 도착하면 그제서야 화면을 넘김
          }}
          onMemory={async () => {
            await fetchDiaries(); // 1. 데이터가 도착할 때까지 기다림
            setScreen('memory');  // 2. 다 도착하면 화면을 넘김
          }}
          guardians={guardians}
        />
      )}

      {screen === 'talk' && (
        <TalkPage
          onStartTalk={handleStartTalk}
          onClose={() => setScreen('home')}
        />
      )}

      {screen === 'ai' && (
        <AiPage
          aiText={aiText}
          agentState={agentState}
          getStatusText={getStatusText}
          onStop={() => {
            if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
              wsRef.current.send(
                JSON.stringify({ command: 'stop_record' })
              );
            }

            setScreen('send');
          }}
        />
      )}

      {screen === 'send' && (
      <SendPage
        guardians={guardians}
        onSend={(guardianIds) => {
          console.log('선택된 보호자 mappingId:', guardianIds);
          console.log('보낼 일기:', selectedDiary);

          if (!selectedDiary) {
            alert('보낼 일기가 없습니다.');
            return;
          }

          if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
            wsRef.current.send(
              JSON.stringify({
                target: 'cloud',
                payload: {
                  action: 'SEND_DIARY',
                  data: {
                    guardian_mapping_ids: guardianIds,
                    diary_id: selectedDiary.id,
                  },
                },
              })
            );

            setScreen('finish');
          } else {
            alert('기기 연결이 끊어졌습니다. 잠시 후 다시 시도해주세요.');
          }
        }}
        onStop={() => setScreen('home')}
      />
    )}

    {screen === 'finish' && (
      <FinishPage onConfirm={() => setScreen('home')} />
    )}

      {screen === 'diary' && (
        <DiaryPage
          todayFormatted={todayFormatted}
          todayDiary={todayDiary}
          onNext={() => {
          if (!todayDiary) {
            alert('오늘의 일기가 없습니다.');
            return;
          }

          setSelectedDiary(todayDiary);
          setScreen('send');
        }}
        />
      )}

      {screen === 'memory' && (
        <MemoryPage
          uniqueDates={uniqueDates}
          currentViewDate={currentViewDate}
          selectedDateIndex={selectedDateIndex}
          itemStartIndex={itemStartIndex}
          itemsPerPage={ITEMS_PER_PAGE}
          diariesForDate={diariesForDate}
          visibleMemories={visibleMemories}
          onPrevDate={handlePrevDate}
          onNextDate={handleNextDate}
          onPrevItems={handlePrevItems}
          onNextItems={handleNextItems}
          onSelectSend={(diary) => {
            setSelectedDiary(diary);
            setScreen('send');
          }}
          onSelectDetail={(diary) => {
            setSelectedDiary(diary);
            setScreen('detail');
          }}
          onClose={() => setScreen('home')}
        />
      )}

      {screen === 'detail' && (
        <DetailPage
          selectedDiary={selectedDiary}
          onClose={() => setScreen('memory')}
        />
      )}

      {screen === 'help' && (
        <HelpPage onClose={() => setScreen('home')} />
      )}

      <Popup
        showPairingPopup={showPairingPopup}
        pairingData={pairingData}
        showNotification={showNotification}
        greetingData={greetingData}
        onAcceptPairing={handleAcceptPairing}
        onRejectPairing={handleRejectPairing}
        onGreetingChat={() => {
          setGreetingData(null);
          setScreen('send');
        }}
        onGreetingClose={() => setGreetingData(null)}
      />
    </div>
  );
};

export default KioskPage;
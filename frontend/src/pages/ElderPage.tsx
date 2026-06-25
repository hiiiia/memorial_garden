import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import '../css/ElderPage.css';

type Screen = 'home' | 'talk' | 'ai' | 'diary' | 'send' | 'finish';
type VoiceUiState = 'idle' | 'recording' | 'processing' | 'speaking' | 'error';

interface RecordedAudioSummary {
  filePath: string;
  durationSeconds: number;
  sizeBytes: number;
}

type AgentStatus = 'listening' | 'processing' | 'speaking' | 'idle' | 'error';

interface AgentMessage {
  status?: AgentStatus;
  type?: 'AI_RESPONSE' | string;
  text?: string;
  message?: string;
  file_path?: string;
  duration_seconds?: number;
  size_bytes?: number;
}

const DEFAULT_AGENT_WS_URL = 'ws://127.0.0.1:8765';

const getVoiceStatusText = (
  voiceState: VoiceUiState,
  isConnectingAgent: boolean,
  isWaitingAgent: boolean,
): string => {
  if (isConnectingAgent) {
    return '음성 장치를 연결하고 있습니다.';
  }
  if (voiceState === 'recording') {
    return '말씀을 듣고 있습니다.';
  }
  if (voiceState === 'processing' || isWaitingAgent) {
    return '이야기를 정리하고 있습니다.';
  }
  if (voiceState === 'speaking') {
    return '안내를 준비하고 있습니다.';
  }
  if (voiceState === 'error') {
    return '음성 장치에 연결할 수 없습니다.';
  }
  return '오늘의 이야기를 들려주세요.';
};

const ElderPage = () => {
  const [screen, setScreen] = useState<Screen>('home');
  const [voiceState, setVoiceState] = useState<VoiceUiState>('idle');
  const [isConnectingAgent, setIsConnectingAgent] = useState(false);
  const [isWaitingAgent, setIsWaitingAgent] = useState(false);
  const [isAgentConnected, setIsAgentConnected] = useState(false);
  const [hardwareError, setHardwareError] = useState<string | null>(null);
  const [hardwareErrorDetail, setHardwareErrorDetail] = useState<string | null>(null);
  const [currentRecordingPath, setCurrentRecordingPath] = useState<string | null>(null);
  const [lastRecording, setLastRecording] = useState<RecordedAudioSummary | null>(null);
  const [aiResponseText, setAiResponseText] = useState('');
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimerRef = useRef<number | null>(null);
  const shouldReconnectRef = useRef(false);
  const isUnmountedRef = useRef(false);
  const agentWsUrl = useMemo(
    () => process.env.REACT_APP_HARDWARE_WS_URL || DEFAULT_AGENT_WS_URL,
    [],
  );

  const clearReconnectTimer = useCallback(() => {
    if (reconnectTimerRef.current !== null) {
      window.clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }
  }, []);

  const handleAgentMessage = useCallback((message: AgentMessage) => {
    if (message.type === 'AI_RESPONSE' && message.text) {
      setAiResponseText(message.text);
    }

    if (!message.status) {
      return;
    }

    setIsWaitingAgent(false);

    if (message.status === 'listening') {
      setVoiceState('recording');
      setCurrentRecordingPath(message.file_path || null);
      setHardwareError(null);
      setHardwareErrorDetail(null);
      setScreen('ai');
      return;
    }

    if (message.status === 'processing') {
      setVoiceState('processing');
      setCurrentRecordingPath(null);
      if (message.file_path) {
        setLastRecording({
          filePath: message.file_path,
          durationSeconds: message.duration_seconds || 0,
          sizeBytes: message.size_bytes || 0,
        });
      }
      setHardwareError(null);
      setHardwareErrorDetail(null);
      setScreen('ai');
      return;
    }

    if (message.status === 'speaking') {
      setVoiceState('speaking');
      setHardwareError(null);
      setHardwareErrorDetail(null);
      setScreen('ai');
      return;
    }

    if (message.status === 'idle') {
      setVoiceState('idle');
      setCurrentRecordingPath(null);
      setHardwareError(null);
      setHardwareErrorDetail(null);
      setScreen('talk');
      return;
    }

    if (message.status === 'error') {
      setVoiceState('error');
      setHardwareError(message.message || '음성 장치에 연결할 수 없습니다.');
      setHardwareErrorDetail(null);
      setScreen('ai');
    }
  }, []);

  const connectAgent = useCallback(() => {
    if (isUnmountedRef.current) {
      return;
    }
    const currentSocket = wsRef.current;
    if (
      currentSocket &&
      (currentSocket.readyState === WebSocket.OPEN || currentSocket.readyState === WebSocket.CONNECTING)
    ) {
      return;
    }

    clearReconnectTimer();
    setIsConnectingAgent(true);
    setHardwareError(null);
    setHardwareErrorDetail(null);

    try {
      const socket = new WebSocket(agentWsUrl);
      wsRef.current = socket;

      socket.onopen = () => {
        if (isUnmountedRef.current) {
          socket.close();
          return;
        }
        setIsAgentConnected(true);
        setIsConnectingAgent(false);
        setVoiceState('idle');
        setHardwareError(null);
        setHardwareErrorDetail(null);
      };

      socket.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data) as AgentMessage;
          handleAgentMessage(message);
        } catch {
          setVoiceState('error');
          setHardwareError('음성 장치 응답을 읽을 수 없습니다.');
          setHardwareErrorDetail(null);
          setIsWaitingAgent(false);
        }
      };

      socket.onerror = () => {
        setIsAgentConnected(false);
        setIsConnectingAgent(false);
        setIsWaitingAgent(false);
        setVoiceState('error');
        setHardwareError('음성 장치에 연결할 수 없습니다.');
        setHardwareErrorDetail(agentWsUrl);
      };

      socket.onclose = () => {
        if (wsRef.current && wsRef.current !== socket) {
          return;
        }
        if (wsRef.current === socket) {
          wsRef.current = null;
        }
        setIsAgentConnected(false);
        setIsConnectingAgent(false);
        setIsWaitingAgent(false);
        if (!isUnmountedRef.current && shouldReconnectRef.current) {
          reconnectTimerRef.current = window.setTimeout(connectAgent, 2000);
          return;
        }
        if (!isUnmountedRef.current) {
          setVoiceState('error');
          setHardwareError('음성 장치에 연결할 수 없습니다.');
          setHardwareErrorDetail(agentWsUrl);
        }
      };
    } catch {
      setIsAgentConnected(false);
      setIsConnectingAgent(false);
      setVoiceState('error');
      setHardwareError('음성 장치에 연결할 수 없습니다.');
      setHardwareErrorDetail(agentWsUrl);
    }
  }, [agentWsUrl, clearReconnectTimer, handleAgentMessage]);

  useEffect(() => {
    isUnmountedRef.current = false;
    shouldReconnectRef.current = false;
    connectAgent();

    return () => {
      isUnmountedRef.current = true;
      shouldReconnectRef.current = false;
      clearReconnectTimer();
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [clearReconnectTimer, connectAgent]);

  const handleRetryHardware = () => {
    if (isConnectingAgent || isWaitingAgent) {
      return;
    }
    shouldReconnectRef.current = false;
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    setVoiceState('idle');
    setIsAgentConnected(false);
    setHardwareError(null);
    setHardwareErrorDetail(null);
    connectAgent();
  };

  const handlePrimaryConversationAction = () => {
    if (voiceState === 'error') {
      handleRetryHardware();
      return;
    }

    if (isConnectingAgent || isWaitingAgent || voiceState === 'processing' || voiceState === 'speaking') {
      return;
    }

    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      setVoiceState('error');
      setHardwareError('음성 장치에 연결할 수 없습니다.');
      setHardwareErrorDetail(agentWsUrl);
      return;
    }

    setIsWaitingAgent(true);
    setHardwareError(null);
    setHardwareErrorDetail(null);
    if (voiceState !== 'recording') {
      setAiResponseText('');
      setScreen('ai');
    }

    try {
      wsRef.current.send(JSON.stringify({ command: 'force_record' }));
      if (voiceState === 'recording') {
        setVoiceState('processing');
      }
    } catch {
      setIsWaitingAgent(false);
      setVoiceState('error');
      setHardwareError('음성 장치에 명령을 보낼 수 없습니다.');
      setHardwareErrorDetail(agentWsUrl);
    }
  };

  const handlePlayLastRecording = () => {
    if (!lastRecording) {
      setVoiceState('error');
      setHardwareError('다시 들을 녹음이 없습니다.');
      setHardwareErrorDetail(null);
    }
  };

  const statusText =
    isConnectingAgent || isWaitingAgent
      ? getVoiceStatusText(voiceState, isConnectingAgent, isWaitingAgent)
      : hardwareError || getVoiceStatusText(voiceState, isConnectingAgent, isWaitingAgent);
  const actionButtonLabel = (() => {
    if (isConnectingAgent) {
      return '연결 중';
    }
    if (isWaitingAgent || voiceState === 'processing') {
      return '잠시만 기다려주세요';
    }
    if (voiceState === 'error') {
      return '다시 시도';
    }
    if (voiceState === 'recording') {
      return '■ 대화 종료';
    }
    return '🎤 대화 시작';
  })();
  const isActionDisabled = isConnectingAgent || isWaitingAgent || voiceState === 'processing' || voiceState === 'speaking';
  const isStartDisabled = isActionDisabled || voiceState === 'error' || !isAgentConnected;
  const hasHardwareError = voiceState === 'error' && Boolean(hardwareError);
  const talkButtonLabel = voiceState === 'recording' ? '■ 대화 종료' : isWaitingAgent ? '준비 중' : '🎤 대화 시작';

  return (
    <div className="elder-page">
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
                    ☎
                    <span>
                        도움<br />
                        요청하기
                    </span>
                </button>

                <button className="menu-btn talk-btn" onClick={() => setScreen('talk')}>
                    🎤
                    <span>
                        이야기<br />
                        시작하기
                    </span>
                </button>
                <button className="menu-btn diary-btn">📖<span>오늘의 일기</span></button>
                <button className="menu-btn memory-btn">🖼<span>추억 보관함</span></button>
              </div>
            </div>
          </div>
        </div>
      )}

      {screen === 'talk' && (
        <div className="home-card talk-card">
          <h1 className="talk-title">무엇을 이야기할까요?</h1>
          <div className="talk-robot">🌱</div>
          <div className={`hardware-status-panel ${hasHardwareError ? 'error' : ''}`}>
            <p className="hardware-status-text">
              {statusText}
            </p>
            {hardwareErrorDetail && (
              <p className="hardware-status-detail">
                {hardwareErrorDetail}
              </p>
            )}
          </div>

          <div className="talk-buttons">
            <button
                type="button"
                className="talk-main-btn"
                onClick={handlePrimaryConversationAction}
                disabled={isStartDisabled}
            >
                {talkButtonLabel}
            </button>
            {hasHardwareError ? (
              <button
                type="button"
                className="talk-close-btn retry-btn"
                onClick={handleRetryHardware}
                disabled={isActionDisabled}
              >
                다시 시도
              </button>
            ) : (
              <button className="talk-close-btn" onClick={() => setScreen('home')}>❌ 닫기</button>
            )}
          </div>
        </div>
      )}
      {screen === 'ai' && (
        <div className={`home-card ai-card voice-state-${voiceState}`}>
            <div className="ai-content">
            <div className="ai-robot">🌱</div>

            <div className="speech-bubble">
                {statusText}<br />
                {voiceState === 'recording' && '천천히 말씀해주세요.'}
                {voiceState === 'processing' && '잠시만 기다려주세요.'}
                {voiceState === 'idle' && '버튼을 눌러 시작해주세요.'}
                {voiceState === 'speaking' && (aiResponseText || '곧 안내해드릴게요.')}
                {voiceState === 'error' && '아래 버튼을 눌러 다시 확인해주세요.'}
            </div>
            </div>

            <div className={`recording-indicator ${voiceState === 'recording' ? 'active' : ''}`}>
              <span className="recording-dot" />
              {voiceState === 'recording' ? '녹음 중' : '대기 중'}
            </div>
            <div className="voice-wave">▂▃▅▆▇▆▅▃▂▃▅▆▇▆▅</div>
            <p className="listening-text">{getVoiceStatusText(voiceState, isConnectingAgent, isWaitingAgent)}</p>
            {currentRecordingPath && (
              <p className="recording-path-text">
                저장 중: {currentRecordingPath}
              </p>
            )}
            {hardwareErrorDetail && (
              <p className="hardware-status-detail ai-error-detail">
                {hardwareErrorDetail}
              </p>
            )}

            <button
              className="stop-btn"
              onClick={handlePrimaryConversationAction}
              disabled={isActionDisabled}
            >
                {actionButtonLabel}
            </button>
            {voiceState === 'error' && (
              <button className="ai-home-btn" onClick={() => setScreen('home')}>
                홈으로 가기
              </button>
            )}
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
              {lastRecording && (
                <span className="recording-summary">
                  녹음 {lastRecording.durationSeconds.toFixed(1)}초 저장
                </span>
              )}
            </div>
          </div>

          <div className="diary-buttons">
            <button
              className="diary-listen-btn"
              onClick={handlePlayLastRecording}
              disabled={!lastRecording}
            >
              🔊 다시듣기
            </button>
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
              <button className="send-main-btn">
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
    </div>
  );
};

export default ElderPage;

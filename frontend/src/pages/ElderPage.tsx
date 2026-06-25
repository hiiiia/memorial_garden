import React, { useCallback, useEffect, useState } from 'react';
import '../css/ElderPage.css';
import {
  getStatus,
  HardwareApiError,
  HardwareState,
  HardwareStatusResponse,
  health,
  playAudio,
  startRecording,
  stopAudio,
  stopRecording,
} from '../services/hardwareApi';

type Screen = 'home' | 'talk' | 'ai' | 'diary' | 'send' | 'finish';
type VoiceUiState = HardwareState | 'stopping';

interface RecordedAudioSummary {
  filePath: string;
  durationSeconds: number;
  sizeBytes: number;
}

const getHardwareErrorMessages = (error: unknown): { message: string; detail?: string } => {
  if (error instanceof HardwareApiError) {
    if (error.kind === 'network' || error.kind === 'timeout') {
      return {
        message: '음성 장치에 연결할 수 없습니다.',
        detail: error.message,
      };
    }
    return {
      message: '음성 장치를 사용할 수 없습니다.',
      detail: error.message,
    };
  }

  return { message: '음성 장치에 연결할 수 없습니다.' };
};

const getVoiceStatusText = (
  voiceState: VoiceUiState,
  isCheckingHardware: boolean,
  isRequestingHardware: boolean,
): string => {
  if (isCheckingHardware) {
    return '음성 장치를 확인하고 있습니다.';
  }
  if (voiceState === 'recording') {
    return '말씀을 듣고 있습니다.';
  }
  if (voiceState === 'stopping' || isRequestingHardware) {
    return '이야기를 정리하고 있습니다.';
  }
  if (voiceState === 'playing') {
    return '안내 음성을 들려드리고 있습니다.';
  }
  if (voiceState === 'error') {
    return '음성 장치에 연결할 수 없습니다.';
  }
  return '오늘의 이야기를 들려주세요.';
};

const ElderPage = () => {
  const [screen, setScreen] = useState<Screen>('home');
  const [voiceState, setVoiceState] = useState<VoiceUiState>('idle');
  const [isCheckingHardware, setIsCheckingHardware] = useState(false);
  const [isRequestingHardware, setIsRequestingHardware] = useState(false);
  const [hardwareError, setHardwareError] = useState<string | null>(null);
  const [hardwareErrorDetail, setHardwareErrorDetail] = useState<string | null>(null);
  const [currentRecordingPath, setCurrentRecordingPath] = useState<string | null>(null);
  const [lastRecording, setLastRecording] = useState<RecordedAudioSummary | null>(null);

  const applyHardwareStatus = useCallback((status: HardwareStatusResponse) => {
    if (status.state === 'recording') {
      setVoiceState('recording');
      setCurrentRecordingPath(status.recording_file_path);
      setHardwareError(null);
      setHardwareErrorDetail(null);
      return;
    }

    if (status.state === 'playing') {
      setVoiceState('playing');
      setHardwareError(null);
      setHardwareErrorDetail(null);
      return;
    }

    if (status.state === 'error') {
      setVoiceState('error');
      setHardwareError('음성 장치에 연결할 수 없습니다.');
      setHardwareErrorDetail(status.last_error || null);
      return;
    }

    setVoiceState('idle');
    setCurrentRecordingPath(null);
    setHardwareError(null);
    setHardwareErrorDetail(null);
  }, []);

  const refreshHardwareStatus = useCallback(async () => {
    setIsCheckingHardware(true);
    try {
      const healthResponse = await health();
      if (healthResponse.status !== 'ok') {
        setVoiceState('error');
        setHardwareError('음성 장치에 연결할 수 없습니다.');
        setHardwareErrorDetail(
          healthResponse.alsa?.error ||
            healthResponse.recordings_directory_error ||
            healthResponse.hardware?.last_error ||
            null,
        );
        return;
      }
      applyHardwareStatus(healthResponse.hardware);
    } catch (error) {
      const { message, detail } = getHardwareErrorMessages(error);
      setVoiceState('error');
      setHardwareError(message);
      setHardwareErrorDetail(detail || null);
    } finally {
      setIsCheckingHardware(false);
    }
  }, [applyHardwareStatus]);

  useEffect(() => {
    void refreshHardwareStatus();
  }, [refreshHardwareStatus]);

  useEffect(() => {
    if (voiceState !== 'playing') {
      return undefined;
    }

    const statusTimer = window.setInterval(async () => {
      try {
        const status = await getStatus();
        if (status.state !== 'playing') {
          applyHardwareStatus(status);
        }
      } catch (error) {
        const { message, detail } = getHardwareErrorMessages(error);
        setVoiceState('error');
        setHardwareError(message);
        setHardwareErrorDetail(detail || null);
      }
    }, 1500);

    return () => window.clearInterval(statusTimer);
  }, [applyHardwareStatus, voiceState]);

  const handleRetryHardware = async () => {
    if (isCheckingHardware || isRequestingHardware) {
      return;
    }
    await refreshHardwareStatus();
  };

  const handleStartRecording = async () => {
    if (isRequestingHardware || isCheckingHardware || voiceState === 'recording' || voiceState === 'stopping') {
      return;
    }

    setIsRequestingHardware(true);
    setHardwareError(null);
    setHardwareErrorDetail(null);

    try {
      const response = await startRecording();
      setCurrentRecordingPath(response.file_path);
      setVoiceState('recording');
      setScreen('ai');
    } catch (error) {
      const { message, detail } = getHardwareErrorMessages(error);
      setVoiceState('error');
      setHardwareError(message);
      setHardwareErrorDetail(detail || null);
      setScreen('ai');
    } finally {
      setIsRequestingHardware(false);
    }
  };

  const handleStopRecording = async () => {
    if (isRequestingHardware || voiceState !== 'recording') {
      return;
    }

    setVoiceState('stopping');
    setIsRequestingHardware(true);
    setHardwareError(null);
    setHardwareErrorDetail(null);

    try {
      const response = await stopRecording();
      setLastRecording({
        filePath: response.file_path,
        durationSeconds: response.duration_seconds,
        sizeBytes: response.size_bytes,
      });
      setCurrentRecordingPath(null);
      setVoiceState('idle');
      setScreen('diary');
    } catch (error) {
      const { message, detail } = getHardwareErrorMessages(error);
      setVoiceState('error');
      setHardwareError(message);
      setHardwareErrorDetail(detail || null);
      setScreen('ai');
    } finally {
      setIsRequestingHardware(false);
    }
  };

  const handlePrimaryConversationAction = async () => {
    if (voiceState === 'error') {
      await handleRetryHardware();
      return;
    }

    if (voiceState === 'recording') {
      await handleStopRecording();
      return;
    }

    await handleStartRecording();
  };

  const handlePlayLastRecording = async () => {
    if (isRequestingHardware) {
      return;
    }

    if (voiceState === 'playing') {
      setIsRequestingHardware(true);
      try {
        await stopAudio();
        setVoiceState('idle');
      } catch (error) {
        const { message, detail } = getHardwareErrorMessages(error);
        setVoiceState('error');
        setHardwareError(message);
        setHardwareErrorDetail(detail || null);
      } finally {
        setIsRequestingHardware(false);
      }
      return;
    }

    if (!lastRecording) {
      setVoiceState('error');
      setHardwareError('다시 들을 녹음이 없습니다.');
      setHardwareErrorDetail(null);
      return;
    }

    setIsRequestingHardware(true);
    setHardwareError(null);
    setHardwareErrorDetail(null);

    try {
      await playAudio({ path: lastRecording.filePath });
      setVoiceState('playing');
    } catch (error) {
      const { message, detail } = getHardwareErrorMessages(error);
      setVoiceState('error');
      setHardwareError(message);
      setHardwareErrorDetail(detail || null);
    } finally {
      setIsRequestingHardware(false);
    }
  };

  const statusText =
    isCheckingHardware || isRequestingHardware
      ? getVoiceStatusText(voiceState, isCheckingHardware, isRequestingHardware)
      : hardwareError || getVoiceStatusText(voiceState, isCheckingHardware, isRequestingHardware);
  const actionButtonLabel = (() => {
    if (isRequestingHardware || voiceState === 'stopping') {
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
  const isActionDisabled = isCheckingHardware || isRequestingHardware || voiceState === 'stopping';
  const isStartDisabled = isActionDisabled || voiceState === 'error';
  const hasHardwareError = voiceState === 'error' && Boolean(hardwareError);
  const talkButtonLabel = voiceState === 'recording' ? '■ 대화 종료' : isRequestingHardware ? '준비 중' : '🎤 대화 시작';

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
                {voiceState === 'stopping' && '잠시만 기다려주세요.'}
                {voiceState === 'idle' && '버튼을 눌러 시작해주세요.'}
                {voiceState === 'playing' && '녹음된 소리를 확인합니다.'}
                {voiceState === 'error' && '아래 버튼을 눌러 다시 확인해주세요.'}
            </div>
            </div>

            <div className={`recording-indicator ${voiceState === 'recording' ? 'active' : ''}`}>
              <span className="recording-dot" />
              {voiceState === 'recording' ? '녹음 중' : '대기 중'}
            </div>
            <div className="voice-wave">▂▃▅▆▇▆▅▃▂▃▅▆▇▆▅</div>
            <p className="listening-text">{getVoiceStatusText(voiceState, isCheckingHardware, isRequestingHardware)}</p>
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
              disabled={isRequestingHardware || !lastRecording}
            >
              {voiceState === 'playing' ? '■ 듣기 중지' : '🔊 다시듣기'}
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

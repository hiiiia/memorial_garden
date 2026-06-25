const DEFAULT_HARDWARE_API_URL = 'http://127.0.0.1:8002';
const DEFAULT_TIMEOUT_MS = 8000;

const normalizeBaseUrl = (value: string): string => value.replace(/\/+$/, '');

export const hardwareApiBaseUrl = normalizeBaseUrl(
  process.env.REACT_APP_HARDWARE_API_URL || DEFAULT_HARDWARE_API_URL,
);

export type HardwareState = 'idle' | 'recording' | 'playing' | 'error';

export interface HardwareStatusResponse {
  state: HardwareState;
  recording_file_path: string | null;
  playback_file_path: string | null;
  last_error: string | null;
}

export interface AlsaDeviceInfo {
  device: string;
  source: string;
  card_index?: number | null;
  card_name?: string | null;
}

export interface HardwareHealthResponse {
  service: string;
  status: 'ok' | 'degraded' | string;
  alsa?: {
    card_match?: string;
    capture?: AlsaDeviceInfo | null;
    playback?: AlsaDeviceInfo | null;
    error?: string | null;
  };
  hardware: HardwareStatusResponse;
  recordings_directory?: string;
  recordings_directory_error?: string | null;
}

export interface StartRecordingResponse {
  status: 'recording';
  file_path: string;
  capture_device?: string;
}

export interface StopRecordingResponse {
  status: 'idle';
  file_path: string;
  size_bytes: number;
  duration_seconds: number;
}

export interface PlayAudioRequest {
  path: string;
}

export interface PlayAudioResponse {
  status: 'playing';
  file_path: string;
  playback_device?: string;
  replaced_file_path?: string | null;
  policy?: string;
}

export interface StopAudioResponse {
  status: 'idle';
  stopped_file_path?: string | null;
}

export type HardwareApiErrorKind = 'http' | 'network' | 'timeout';

export class HardwareApiError extends Error {
  readonly kind: HardwareApiErrorKind;
  readonly status?: number;
  readonly details?: unknown;

  constructor(message: string, kind: HardwareApiErrorKind, status?: number, details?: unknown) {
    super(message);
    this.name = 'HardwareApiError';
    this.kind = kind;
    this.status = status;
    this.details = details;
  }
}

const extractErrorMessage = async (response: Response): Promise<{ message: string; details?: unknown }> => {
  const fallbackMessage = `하드웨어 서버 오류가 발생했습니다. (${response.status})`;
  const contentType = response.headers.get('content-type') || '';

  if (contentType.includes('application/json')) {
    const body = (await response.json().catch(() => null)) as unknown;
    if (body && typeof body === 'object' && 'detail' in body) {
      const detail = (body as { detail?: unknown }).detail;
      if (typeof detail === 'string' && detail.trim()) {
        return { message: detail, details: body };
      }
    }
    return { message: fallbackMessage, details: body };
  }

  const text = await response.text().catch(() => '');
  return { message: text.trim() || fallbackMessage, details: text };
};

const requestHardware = async <T>(
  path: string,
  options: RequestInit = {},
  timeoutMs: number = DEFAULT_TIMEOUT_MS,
): Promise<T> => {
  const controller = new AbortController();
  const timeoutId = window.setTimeout(() => controller.abort(), timeoutMs);

  try {
    const response = await fetch(`${hardwareApiBaseUrl}${path}`, {
      ...options,
      headers: {
        ...(options.body ? { 'Content-Type': 'application/json' } : {}),
        ...options.headers,
      },
      signal: controller.signal,
    });

    if (!response.ok) {
      const { message, details } = await extractErrorMessage(response);
      throw new HardwareApiError(message, 'http', response.status, details);
    }

    return (await response.json()) as T;
  } catch (error) {
    if (error instanceof HardwareApiError) {
      throw error;
    }
    if (error instanceof DOMException && error.name === 'AbortError') {
      throw new HardwareApiError('하드웨어 서버 응답이 지연되고 있습니다.', 'timeout');
    }
    throw new HardwareApiError('음성 장치에 연결할 수 없습니다.', 'network', undefined, error);
  } finally {
    window.clearTimeout(timeoutId);
  }
};

export const health = (): Promise<HardwareHealthResponse> =>
  requestHardware<HardwareHealthResponse>('/health', { method: 'GET' }, 5000);

export const getStatus = (): Promise<HardwareStatusResponse> =>
  requestHardware<HardwareStatusResponse>('/hardware/status', { method: 'GET' }, 5000);

export const startRecording = (): Promise<StartRecordingResponse> =>
  requestHardware<StartRecordingResponse>('/hardware/record/start', { method: 'POST' }, 10000);

export const stopRecording = (): Promise<StopRecordingResponse> =>
  requestHardware<StopRecordingResponse>('/hardware/record/stop', { method: 'POST' }, 20000);

export const playAudio = (request: PlayAudioRequest): Promise<PlayAudioResponse> =>
  requestHardware<PlayAudioResponse>(
    '/hardware/audio/play',
    {
      method: 'POST',
      body: JSON.stringify(request),
    },
    10000,
  );

export const stopAudio = (): Promise<StopAudioResponse> =>
  requestHardware<StopAudioResponse>('/hardware/audio/stop', { method: 'POST' }, 10000);

// src/config/index.ts

export const config = {
  // 백엔드 API 주소
  apiBaseUrl: process.env.REACT_APP_BACKEND_URL || 'http://localhost:8000/',
  
  // 프론트엔드 주소 (리다이렉트용)
  frontendUrl: process.env.REACT_APP_FRONTEND_URL || 'http://localhost:3000/',

  // 카카오 로그인
  kakaoClientId: process.env.REACT_APP_KAKAO_REST_API_KEY || '',
  get redirectUri() {
    return `${this.frontendUrl}/auth/kakao/callback`;
  }
};
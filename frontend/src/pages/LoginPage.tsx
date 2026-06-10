import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Link } from 'react-router-dom';
import { config } from '../config'; // config 객체 불러오기

import { LoginPageProps } from '../types/interface';

import '../css/CustomCalendar.css';
import '../css/LoginPage.css'


const LoginPage = ({ setIsLoggedIn }: LoginPageProps) => {
  const [username, setUsername] = useState<string>('');
  const [password, setPassword] = useState<string>('');
  const [errorMsg, setErrorMsg] = useState<string>('');

  const navigate = useNavigate();


  const handleNormalLogin = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setErrorMsg('');

    const formData = new URLSearchParams();
    formData.append('username', username);
    formData.append('password', password);

    try {
      const response = await fetch(`${config.apiBaseUrl}api/v1/auth/login`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: formData, // URLSearchParams 객체는 브라우저가 알아서 변환해 줍니다.
      });

      const data = await response.json();

      if (response.ok) {
        // 성공 시 토큰과 유저 정보 저장
        const token = data.data?.access_token || data.access_token;
        const guardianInfo = data.data?.guardian || data.guardian;
        
        // 2. 안전하게 저장
        if (token) localStorage.setItem('access_token', token);
        if (guardianInfo) localStorage.setItem('guardian_info', JSON.stringify(guardianInfo));
        // 로그인 됨(true)으로 변경
        setIsLoggedIn(true);


        navigate('/', { replace: true });
      } else {
        setErrorMsg(data.error || '로그인에 실패했습니다.');
      }
    } catch (err) {
      setErrorMsg('서버와 연결할 수 없습니다.');
    }
  };

  const handleKakaoLogin = () => {
    const KAKAO_CLIENT_ID = config.kakaoClientId; 
    const REDIRECT_URI = `${config.frontendUrl}/auth/kakao/callback`;
    const KAKAO_AUTH_URL = `https://kauth.kakao.com/oauth/authorize?client_id=${KAKAO_CLIENT_ID}&redirect_uri=${REDIRECT_URI}&response_type=code`;
    
    window.location.href = KAKAO_AUTH_URL;
  };

  return (
    <div className="login-page-container">
      <div className="login-box">
        
        {/* 헤더 영역 */}
        <div className="login-header">
          <h2 className="login-title">Memorial Garden</h2>
          <p className="login-subtitle">소중한 기억을 함께 돌보는 공간</p>
        </div>
        
        {/* 에러 메시지 출력 영역 */}
        {errorMsg && (
          <div className="error-message">
            {errorMsg}
          </div>
        )}

        {/* 일반 로그인 폼 */}
        <form onSubmit={handleNormalLogin} className="login-form">
          <input 
            type="text" 
            value={username} 
            onChange={(e) => setUsername(e.target.value)} 
            placeholder="아이디를 입력하세요"
            required
            className="login-input"
          />
          
          <input 
            type="password" 
            value={password} 
            onChange={(e) => setPassword(e.target.value)} 
            placeholder="비밀번호를 입력하세요"
            required
            className="login-input"
          />

          <button type="submit" className="login-btn login-btn-normal">
            로그인
          </button>
        </form>

        {/* 구분선 */}
        <div className="login-divider">
          <div className="divider-line"></div>
          <div className="divider-text">또는</div>
          <div className="divider-line"></div>
        </div>

        {/* 카카오 로그인 버튼 */}
        <button 
          onClick={handleKakaoLogin} 
          className="login-btn login-btn-kakao"
        >
          <span className="kakao-icon">💬</span> 카카오로 시작하기
        </button>

        {/* 회원가입 링크 연결 */}
        <div className="signup-link-container">
          아직 계정이 없으신가요?{' '}
          <Link to="/signup" className="signup-link">
            회원가입하기
          </Link>
        </div>

      </div>
    </div>
  );
};


export default LoginPage;
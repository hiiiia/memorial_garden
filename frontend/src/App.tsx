import React, { useState, useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';

import LoginPage from './pages/LoginPage';
import KakaoCallbackPage from './pages/KakaoCallbackPage'; 

import SignupPage from './pages/SignupPage';
import ExtraSignupPage from './pages/ExtraSignupPage';

import DashboardPage from './pages/DashboardPage';
import DiaryPage from './pages/DiaryPage';
import RiskAnalysisPage from './pages/RiskAnalysisPage'; 
import SeniorRegisterPage from './pages/SeniorRegisterPage';

import Header from './components/Header';

const App = () => {
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [isChecking, setIsChecking] = useState(true);

  const [isChecking, setIsChecking] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem('access_token');
    if (token) {
      setIsLoggedIn(true);
    }
    setIsChecking(false);
  }, []);

  const handleLogout = () => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('guardian_info'); 
    localStorage.removeItem('dependent_id');  
    setIsLoggedIn(false);
    alert('로그아웃 되었습니다.');
    window.location.href = '/login';
  };

  // 검사 중일 때는 화면 이동을 멈추고 빈 화면(또는 로딩)을 보여줍니다.
  if (isChecking) {
    return <div style={{ textAlign: 'center', marginTop: '100px' }}>화면을 불러오는 중입니다...</div>;
  }
  
  return (
    <BrowserRouter>
      {/* 상태와 로그아웃 함수를 Props로 넘겨줍니다. */}
      <Header isLoggedIn={isLoggedIn} onLogout={handleLogout} />
      <div style={{ padding: '20px' }}>
        <Routes>
          <Route path="/" element={isLoggedIn ? <DashboardPage /> : <Navigate to="/login" replace />} />

          <Route path="/login" element={isLoggedIn ? <Navigate to="/" replace /> : <LoginPage setIsLoggedIn={setIsLoggedIn} />} />
          <Route path="/signup" element={<SignupPage />} />
          <Route path="/auth/kakao/callback" element={<KakaoCallbackPage setIsLoggedIn={setIsLoggedIn} />} />
          <Route path="/signup/extra" element={<ExtraSignupPage />} />

          {/* 서비스 메인 및 상세 페이지 (비로그인 접근 차단) */}
          <Route path="/diary" element={isLoggedIn ? <DiaryPage /> : <Navigate to="/login" replace />} />
          <Route path="/analysis" element={isLoggedIn ? <RiskAnalysisPage /> : <Navigate to="/login" replace />} />
          <Route path="/register-senior" element={isLoggedIn ? <SeniorRegisterPage /> : <Navigate to="/login" replace />} />
          
        </Routes>
      </div>
    </BrowserRouter>
  );
};

export default App;
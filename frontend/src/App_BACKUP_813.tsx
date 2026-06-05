// src/App.tsx
import React, { useState, useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import LoginPage from './pages/LoginPage';
import KakaoCallbackPage from './pages/KakaoCallbackPage'; 
import ExtraSignupPage from './pages/ExtraSignupPage';
import MainPage from './pages/MainPage';
import Header from './components/Header';

const App = () => {
  const [isLoggedIn, setIsLoggedIn] = useState(false);

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
<<<<<<< HEAD
          <Route 
            path="/" 
            element={
              isLoggedIn ? (
                <div style={{ textAlign: 'center', marginTop: '50px' }}>
                  <h2>환영합니다! 🎉</h2>
                  <p>성공적으로 로그인되었습니다.</p>
                </div>
              ) : (
                <Navigate to="/login" replace />
              )
            } 
          />
          <Route path="/login" element={<LoginPage />} />
          <Route 
            path="/auth/kakao/callback" 
            element={<KakaoCallbackPage setIsLoggedIn={setIsLoggedIn} />} 
          />
          
=======
          <Route path="/"  element={isLoggedIn ? (<MainPage />) : (<Navigate to="/login" replace /> )}  />

          <Route path="/login" element={isLoggedIn ? <Navigate to="/" replace /> : <LoginPage setIsLoggedIn={setIsLoggedIn} />} />

          <Route path="/auth/kakao/callback" element={<KakaoCallbackPage setIsLoggedIn={setIsLoggedIn}  />} />
>>>>>>> 5704f87 (fix(frontend): 카카오 로그인 유저 정보 저장 누락 및 TS 라우팅 에러 수정)
          <Route path="/signup/extra" element={<ExtraSignupPage />} />
        </Routes>
      </div>
    </BrowserRouter>
  );
};

export default App;
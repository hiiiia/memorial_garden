// src/App.tsx
import React, { useState, useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import LoginPage from './pages/LoginPage';
import KakaoCallbackPage from './pages/KakaoCallbackPage'; 
import ExtraSignupPage from './pages/ExtraSignupPage';
import Header from './components/Header';

const App = () => {
  const [isLoggedIn, setIsLoggedIn] = useState(false);

  useEffect(() => {
    const token = localStorage.getItem('access_token');
    if (token) {
      setIsLoggedIn(true);
    }
  }, []);

  const handleLogout = () => {
    localStorage.removeItem('access_token');
    setIsLoggedIn(false);
    alert('로그아웃 되었습니다.');
    window.location.href = '/login';
  };

  return (
    <BrowserRouter>
      {/* 상태와 로그아웃 함수를 Props로 넘겨줍니다. */}
      <Header isLoggedIn={isLoggedIn} onLogout={handleLogout} />

      <div style={{ padding: '20px' }}>
        <Routes>
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
          <Route path="/auth/kakao/callback" element={<KakaoCallbackPage />} />
          <Route path="/signup/extra" element={<ExtraSignupPage />} />
        </Routes>
      </div>
    </BrowserRouter>
  );
};

export default App;
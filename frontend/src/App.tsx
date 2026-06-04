// src/App.tsx
import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import LoginPage from './pages/LoginPage';

const App = () => {
  return (
    <BrowserRouter>
      <Routes>
        {/* 기본 주소(/)로 오면 일단 로그인 페이지로 보냅니다 */}
        <Route path="/" element={<Navigate to="/login" replace />} />
        
        {/* /login 주소일 때 LoginPage 컴포넌트를 보여줍니다 */}
        <Route path="/login" element={<LoginPage />} />
        
        {/* 추후 여기에 카카오 콜백 페이지 등을 추가할 예정입니다! */}
        {/* <Route path="/auth/kakao/callback" element={<KakaoCallbackPage />} /> */}
      </Routes>
    </BrowserRouter>
  );
};

export default App;
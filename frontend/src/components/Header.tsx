// src/components/Header.tsx
import React from 'react';
import { Link } from 'react-router-dom';

// 부모(App.tsx)로부터 받아올 데이터의 타입을 정의합니다.
interface HeaderProps {
  isLoggedIn: boolean;
  onLogout: () => void;
}

const Header = ({ isLoggedIn, onLogout }: HeaderProps) => {
  return (
    <header style={{ 
      padding: '15px 20px', 
      background: '#ffe812', 
      display: 'flex', 
      justifyContent: 'space-between', 
      alignItems: 'center',
      fontWeight: 'bold'
    }}>
      {/* 로고를 누르면 메인으로 가도록 Link를 걸어줍니다 */}
      <Link to="/" style={{ textDecoration: 'none', color: 'black' }}>
        <div>🚀 내 프로젝트</div>
      </Link>
      
      {isLoggedIn ? (
        <button 
          onClick={onLogout} 
          style={{ padding: '5px 15px', cursor: 'pointer', border: 'none', background: '#333', color: 'white', borderRadius: '5px' }}
        >
          로그아웃
        </button>
      ) : (
        <span style={{ fontSize: '14px', color: '#555' }}>로그인이 필요합니다</span>
      )}
    </header>
  );
};

export default Header;
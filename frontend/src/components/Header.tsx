// src/components/Header.tsx
import React from 'react';
import { Link } from 'react-router-dom';

interface HeaderProps {
  isLoggedIn: boolean;
  onLogout: () => void;
}

const Header = ({ isLoggedIn, onLogout }: HeaderProps) => {
  return (
    <header style={{ 
      padding: '15px 30px', 
      backgroundColor: '#FDFBF7', // 따뜻한 아이보리 배경
      borderBottom: '1px solid #EAE5D9', // 아주 연한 경계선
      display: 'flex', 
      justifyContent: 'space-between', 
      alignItems: 'center',
    }}>
      <Link to="/" style={{ textDecoration: 'none', color: '#7A8B5F' }}>
        <h2 style={{ margin: 0, fontSize: '20px', fontWeight: 'bold' }}>
          🌿 Memorial Garden
        </h2>
      </Link>
      
      {isLoggedIn ? (
        <button 
          onClick={onLogout} 
          style={{ 
            padding: '8px 16px', 
            cursor: 'pointer', 
            border: '1px solid #7A8B5F', 
            backgroundColor: 'transparent', 
            color: '#7A8B5F', 
            borderRadius: '20px', // 둥근 모서리로 부드럽게
            fontWeight: 'bold',
            transition: 'all 0.2s' // 호버 액션을 위한 트랜지션
          }}
          onMouseOver={(e) => { e.currentTarget.style.backgroundColor = '#f0efe9'; }}
          onMouseOut={(e) => { e.currentTarget.style.backgroundColor = 'transparent'; }}
        >
          로그아웃
        </button>
      ) : (
        <span style={{ fontSize: '14px', color: '#888' }}>보호자 로그인</span>
      )}
    </header>
  );
};

export default Header;
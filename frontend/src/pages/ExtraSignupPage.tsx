// src/pages/ExtraSignupPage.tsx
import React, { useState } from 'react';
import { useLocation, useNavigate, Navigate } from 'react-router-dom';
import { config } from '../config';

const ExtraSignupPage = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const [name, setName] = useState('');
  
  // 콜백 페이지에서 넘겨준 카카오 임시 데이터를 꺼냅니다.
  const kakaoResponse = location.state?.kakaoData;
  const payload = kakaoResponse?.data;    
  // 카카오에서 이메일을 주지 않았을 경우를 대비해 이메일도 State로 관리합니다.
  const [email, setEmail] = useState(payload.kakao_email|| '');

  // 비정상적인 접근(URL 직접 입력 등) 차단
  if (!payload) {
    alert('잘못된 접근입니다.');
    return <Navigate to="/login" replace />;
  }

  
  // console.log("백엔드에서 넘어온 데이터:", payload);
  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    
    try {
      // 1. 백엔드의 최종 회원가입 API 주소 수정 (/auth/kakao/signup)
      // config.apiBaseUrl과 주소 사이에 슬래시(/)가 겹치거나 빠지지 않도록 안전하게 작성
      const response = await fetch(`${config.apiBaseUrl}/api/v1/auth/kakao/signup`.replace(/([^:]\/)\/+/g, "$1"), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          kakao_id: String(payload.kakao_id), // 혹시 숫자로 넘어올 경우를 대비해 문자열로 변환
          email: email || "",                 // 비워두면 백엔드에서 더미 이메일을 생성함
          name: name,                          // 유저가 방금 입력한 이름,
          username: payload.name || `Kakao-${payload.kakao_id}`, // ID 기본값 세팅
          kakao_access_token: payload.temp_kakao_access_token || "",
          kakao_refresh_token: payload.temp_kakao_refresh_token || ""
        }),
      });

      if (response.ok) {
        alert('회원가입이 완료되었습니다! 다시 로그인해 주세요.');
        navigate('/login');
      } else {
        const errorData = await response.json();
        
        // 백엔드가 'message'로 주든, 'detail'로 주든 모두 호환되도록 처리합니다.
        const errorMessage = errorData.message || errorData.detail || '알 수 없는 오류가 발생했습니다.';
        
        // 유저에게 정확한 에러 원인을 알림창으로 띄워줍니다.
        alert(`가입 실패: ${errorMessage}`);
        
        // (선택) 아이디 입력창을 다시 비워주고 싶다면 여기에 추가
        // setUsername('');

      }
    } catch (error) {
      alert('서버와 통신 중 오류가 발생했습니다.');
    }
  };

  return (
    <div style={{ maxWidth: '400px', margin: '100px auto', padding: '20px', border: '1px solid #ccc' }}>
      <h2>추가 정보 입력</h2>
      {/* 이름이 없을 경우를 대비한 방어 코드 */}
      <p>환영합니다, <b>{payload?.name || `Kakao-${payload?.kakao_id}`}</b>님!</p> 
      
      <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '15px' }}>
        <div>
          <label>이메일 (선택)</label>
          {/* 2. disabled를 지우고 유저가 직접 수정할 수 있게 변경 */}
          <input 
            type="email" 
            value={email} 
            onChange={(e) => setEmail(e.target.value)} 
            placeholder="이메일이 없다면 비워두셔도 됩니다."
            style={{ width: '100%', padding: '8px' }} 
          />
        </div>
        
        <div>
          <label>이름을 입력해주세요</label>
          <input 
            type="text" 
            value={name} 
            onChange={(e) => setName(e.target.value)} 
            placeholder="(해당 이름은 연동시 어르신에게 보이게 되는 이름입니다)"
            required 
            style={{ width: '100%', padding: '8px' }} 
          />
        </div>

        <button type="submit" style={{ padding: '10px', backgroundColor: '#4CAF50', color: 'white', border: 'none', cursor: 'pointer' }}>
          회원가입 완료
        </button>
      </form>
    </div>
  );
};

export default ExtraSignupPage;
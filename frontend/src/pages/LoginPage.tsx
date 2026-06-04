import React, { useState } from 'react';

const LoginPage = () => {
  // 🌟 TypeScript: state가 무조건 문자열(string)임을 명시합니다.
  const [username, setUsername] = useState<string>('');
  const [password, setPassword] = useState<string>('');
  const [errorMsg, setErrorMsg] = useState<string>('');

  // 🌟 TypeScript: e(이벤트)가 HTML 폼 전송 이벤트임을 명시합니다.
  const handleNormalLogin = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setErrorMsg('');

    const formData = new URLSearchParams();
    formData.append('username', username);
    formData.append('password', password);

    try {
      const response = await fetch('http://localhost:8000/api/v1/auth/login', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: formData, // URLSearchParams 객체는 브라우저가 알아서 변환해 줍니다.
      });

      // 백엔드에서 통일한 unified_response 규격에 맞게 데이터가 들어옵니다.
      const data = await response.json();

      if (response.ok) {
        // 성공 시 토큰과 유저 정보 저장
        localStorage.setItem('access_token', data.access_token);
        localStorage.setItem('guardian_info', JSON.stringify(data.guardian));

        alert(`환영합니다, ${data.guardian.name}님!`);
        // TODO: 메인 페이지 리다이렉트
        // window.location.href = '/'; 
      } else {
        setErrorMsg(data.error || '로그인에 실패했습니다.');
      }
    } catch (err) {
      setErrorMsg('서버와 연결할 수 없습니다. 백엔드가 켜져 있는지 확인해주세요.');
    }
  };

  const handleKakaoLogin = () => {
    const KAKAO_CLIENT_ID = "여기에_카카오_REST_API_KEY_입력"; 
    const REDIRECT_URI = "http://localhost:3000/auth/kakao/callback";
    const KAKAO_AUTH_URL = `https://kauth.kakao.com/oauth/authorize?client_id=${KAKAO_CLIENT_ID}&redirect_uri=${REDIRECT_URI}&response_type=code`;
    
    window.location.href = KAKAO_AUTH_URL;
  };

  return (
    <div style={{ maxWidth: '400px', margin: '50px auto', fontFamily: 'sans-serif' }}>
      <h2>Memorial Garden 로그인</h2>
      
      {errorMsg && <p style={{ color: 'red', fontWeight: 'bold' }}>{errorMsg}</p>}

      {/* 🌟 폼 전송 시 handleNormalLogin 함수가 실행됩니다. */}
      <form onSubmit={handleNormalLogin} style={{ display: 'flex', flexDirection: 'column', gap: '15px' }}>
        <div>
          <label>아이디</label><br />
          <input 
            type="text" 
            value={username} 
            onChange={(e) => setUsername(e.target.value)} 
            placeholder="아이디를 입력하세요"
            required
            style={{ width: '100%', padding: '8px', marginTop: '5px' }}
          />
        </div>
        
        <div>
          <label>비밀번호</label><br />
          <input 
            type="password" 
            value={password} 
            onChange={(e) => setPassword(e.target.value)} 
            placeholder="비밀번호를 입력하세요"
            required
            style={{ width: '100%', padding: '8px', marginTop: '5px' }}
          />
        </div>

        <button type="submit" style={{ padding: '10px', backgroundColor: '#4CAF50', color: 'white', border: 'none', cursor: 'pointer' }}>
          로그인
        </button>
      </form>

      <hr style={{ margin: '30px 0' }} />

      <button 
        onClick={handleKakaoLogin} 
        style={{ width: '100%', padding: '10px', backgroundColor: '#FEE500', color: '#000000', border: 'none', fontWeight: 'bold', cursor: 'pointer' }}
      >
        카카오로 시작하기
      </button>
    </div>
  );
};

export default LoginPage;
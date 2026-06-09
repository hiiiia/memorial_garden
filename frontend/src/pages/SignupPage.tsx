import React, { useState } from 'react';
import { config } from '../config'; // API 주소 세팅 (설정에 맞게 경로 수정 필요)

const SignupPage = () => {
  // 1. 폼 데이터 상태 관리 (백엔드 SignupRequest 모델과 1:1 매칭)
  const [formData, setFormData] = useState({
    username: '', // 아이디 또는 별명
    email: '',
    name: '',     // 실명
    phone: '',
    password: '',
    passwordConfirm: '', // 프론트엔드 전용 확인용 필드
  });

  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  // 입력값 변경 핸들러
  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
  };

  // 회원가입 제출 핸들러
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    // 프론트엔드 자체 검증 로직
    if (formData.password !== formData.passwordConfirm) {
      setError('비밀번호가 일치하지 않습니다.');
      return;
    }
    if (formData.password.length < 6) {
      setError('비밀번호는 6자리 이상이어야 합니다.');
      return;
    }

    setIsLoading(true);

    try {
      // 백엔드 회원가입 API 호출
      const response = await fetch(`${config.apiBaseUrl}api/v1/auth/signup`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          username: formData.username,
          email: formData.email,
          name: formData.name,
          phone: formData.phone,
          password: formData.password,
        }),
      });

      const result = await response.json();

      if (response.status === 201) {
        alert('회원가입이 성공적으로 완료되었습니다! 로그인 페이지로 이동합니다.');
        // TODO: 로그인 페이지로 라우팅 (예: navigate('/login'))
        window.location.href = '/login'; 
      } else {
        // 백엔드에서 내려준 에러 메시지 (예: "이미 가입된 이메일입니다.")
        setError(result.error || '회원가입에 실패했습니다. 다시 시도해 주세요.');
      }
    } catch (err) {
      setError('서버와의 통신에 실패했습니다.');
    } finally {
      setIsLoading(false);
    }
  };

  // UI 렌더링
  return (
    <div style={{ minHeight: '100vh', backgroundColor: '#FDFBF7', display: 'flex', alignItems: 'center', justifyContent: 'center', fontFamily: 'sans-serif', padding: '20px' }}>
      <div style={{ width: '100%', maxWidth: '400px', backgroundColor: '#FFF', borderRadius: '20px', padding: '40px 30px', boxShadow: '0 4px 12px rgba(0,0,0,0.05)' }}>
        
        <h2 style={{ fontSize: '24px', fontWeight: 'bold', color: '#333', textAlign: 'center', marginBottom: '10px' }}>
          회원가입
        </h2>
        <p style={{ fontSize: '14px', color: '#888', textAlign: 'center', marginBottom: '30px' }}>
          소중한 가족의 일상을 함께 지켜보세요.
        </p>

        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '15px' }}>
          
          {/* 에러 메시지 출력 영역 */}
          {error && (
            <div style={{ backgroundColor: '#FDECEA', color: '#E53935', padding: '10px', borderRadius: '8px', fontSize: '13px', textAlign: 'center' }}>
              {error}
            </div>
          )}

          <input
            type="email"
            name="email"
            placeholder="이메일"
            value={formData.email}
            onChange={handleChange}
            required
            style={inputStyle}
          />
          
          <input
            type="text"
            name="username"
            placeholder="아이디 (별명)"
            value={formData.username}
            onChange={handleChange}
            required
            style={inputStyle}
          />

          <input
            type="text"
            name="name"
            placeholder="이름 (실명)"
            value={formData.name}
            onChange={handleChange}
            required
            style={inputStyle}
          />

          <input
            type="tel"
            name="phone"
            placeholder="전화번호 (예: 010-1234-5678)"
            value={formData.phone}
            onChange={handleChange}
            required
            style={inputStyle}
          />

          <input
            type="password"
            name="password"
            placeholder="비밀번호 (6자리 이상)"
            value={formData.password}
            onChange={handleChange}
            required
            style={inputStyle}
          />

          <input
            type="password"
            name="passwordConfirm"
            placeholder="비밀번호 확인"
            value={formData.passwordConfirm}
            onChange={handleChange}
            required
            style={inputStyle}
          />

          <button
            type="submit"
            disabled={isLoading}
            style={{
              marginTop: '10px',
              backgroundColor: isLoading ? '#B0B0B0' : '#7A8B5F',
              color: '#FFF',
              border: 'none',
              padding: '14px',
              borderRadius: '12px',
              fontSize: '16px',
              fontWeight: 'bold',
              cursor: isLoading ? 'not-allowed' : 'pointer',
              transition: 'background-color 0.2s'
            }}
          >
            {isLoading ? '가입하는 중...' : '가입하기'}
          </button>
        </form>

        <div style={{ marginTop: '20px', textAlign: 'center', fontSize: '14px', color: '#666' }}>
          이미 계정이 있으신가요?{' '}
          <a href="/login" style={{ color: '#7A8B5F', fontWeight: 'bold', textDecoration: 'none' }}>
            로그인하기
          </a>
        </div>

      </div>
    </div>
  );
};

// 재사용을 위한 인풋 스타일 객체
const inputStyle: React.CSSProperties = {
  width: '100%',
  padding: '14px',
  borderRadius: '12px',
  border: '1px solid #E0E0E0',
  backgroundColor: '#FAFAFA',
  fontSize: '14px',
  outline: 'none',
  boxSizing: 'border-box'
};

export default SignupPage;
// src/pages/KakaoCallbackPage.tsx
import React, { useEffect, useRef } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { config } from '../config'; // config 객체 불러오기


import { LoginPageProps } from '../types/interface';

const KakaoCallbackPage = ({ setIsLoggedIn }: LoginPageProps) => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  
  const code = searchParams.get('code');
  const isCalled = useRef(false); 

  useEffect(() => {
    const sendCodeToBackend = async () => {
      if (!code || isCalled.current) return;
      isCalled.current = true;

      try {
        const response = await fetch(`${config.apiBaseUrl}api/v1/auth/kakao/login`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            code: code,
            redirect_uri: `${config.frontendUrl}/auth/kakao/callback`,
          }),
        });
        
        const data = await response.json();

        if (response.ok) {
          if (response.status === 202) {
            alert('카카오 인증 성공! 이름을 설정해 주세요.');
            navigate('/signup/extra', { state: { kakaoData: data } });
          } else {
            // 토큰 및 데이터 추출
            const token = data.data?.access_token || data.access_token;
            const guardianInfo = data.data?.guardian || data.guardian; 
            
            if (token) localStorage.setItem('access_token', token);
            
            if (guardianInfo) {
              // 1. 전체 가디언 정보를 저장
              localStorage.setItem('guardian_info', JSON.stringify(guardianInfo));
              
              // 2. 대시보드가 즉시 인식할 수 있도록 dependent_id를 저장
              if (guardianInfo.dependent_id) {
                localStorage.setItem('dependent_id', guardianInfo.dependent_id);
              } else {
                localStorage.removeItem('dependent_id'); // 연동된 사람이 없으면 비움
              }
            }

            setIsLoggedIn(true);
            alert('카카오로 로그인되었습니다!');
            navigate('/', { replace: true }); 
          }
        } else {
          // [수정된 방어 로직 1] response.json()을 다시 호출하지 않고 기존 data 변수 사용
          const errorMsg = data.error || data.message || data.detail || '서버 오류가 발생했습니다.';
          alert(`로그인 처리 실패: ${errorMsg}`);
          navigate('/login', { replace: true }); 
        }
      } catch (error) {
        // [방어 로직 2]
        console.error("카카오 로그인 통신 에러:", error);
        alert('서버와 연결할 수 없습니다. DB나 백엔드 서버 상태를 확인해 주세요.');
        navigate('/login', { replace: true });
      }
    };

    sendCodeToBackend();
  }, [code, navigate, setIsLoggedIn]);

  return (
    <div style={{ display: 'flex', justifyContent: 'center', marginTop: '100px' }}>
      <h2>카카오 로그인 처리 중입니다. 잠시만 기다려주세요... 🚀</h2>
    </div>
  );
};

export default KakaoCallbackPage;
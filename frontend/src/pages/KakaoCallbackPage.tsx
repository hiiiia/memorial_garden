// src/pages/KakaoCallbackPage.tsx
import React, { useEffect, useRef } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { config } from '../config'; // config 객체 불러오기

<<<<<<< HEAD

//  App.tsx에서 넘겨준 리모컨(Prop)의 타입을 정의합니다.
interface KakaoCallbackProps {
  setIsLoggedIn: (value: boolean) => void;
}

const KakaoCallbackPage = ({ setIsLoggedIn }: KakaoCallbackProps) => {
=======
// (App.tsx에서 받아온 리모컨)
interface LoginPageProps {
  setIsLoggedIn: (value: boolean) => void;
}


const KakaoCallbackPage = ({ setIsLoggedIn }: LoginPageProps) => {
>>>>>>> 5704f87 (fix(frontend): 카카오 로그인 유저 정보 저장 누락 및 TS 라우팅 에러 수정)
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  
  // URL 주소창에서 '?code=어쩌구' 부분의 값을 낚아챕니다.
  const code = searchParams.get('code');
  
  // React.StrictMode 때문에 API가 두 번 호출되는 것을 막기 위한 방어막입니다.
  const isCalled = useRef(false); 

  useEffect(() => {
    const sendCodeToBackend = async () => {
      if (!code || isCalled.current) return;
      isCalled.current = true;

      try {
        //  백엔드의 /kakao/login API로 코드를 전송합니다!
        const response = await fetch(`${config.apiBaseUrl}api/v1/auth/kakao/login`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            code: code,
            redirect_uri: `${config.frontendUrl}/auth/kakao/callback`, // 카카오 디벨로퍼스에 등록한 주소와 동일해야 합니다.
          }),
        });
        console.log(`${config.frontendUrl}/auth/kakao/callback`);
        const data = await response.json();

        if (response.ok) {
          // 상태 코드가 200(기존 유저) 또는 202(신규 유저)일 때의 로직
          if (response.status === 202) {
            alert('카카오 인증 성공! 사용할 아이디를 설정해 주세요.');
            // 신규 유저용 추가 회원가입(아이디/비번 설정) 페이지로 이동
            navigate('/signup/extra', { state: { kakaoData: data } });
          } else {
            // 기존 유저라면 바로 로그인 처리

            // 토큰 저장
            const token = data.data?.access_token || data.access_token;
            const guardianInfo = data.data?.guardian || data.guardian; 
            if (token) localStorage.setItem('access_token', token);
            if (guardianInfo) localStorage.setItem('guardian_info', JSON.stringify(guardianInfo));

            setIsLoggedIn(true);
            alert('카카오로 로그인되었습니다!');
            navigate('/', { replace: true }); // 메인 화면으로 이동
          }
          } else {
            //  [추가된 방어 로직 1] 백엔드에서 400, 500 에러를 던졌을 때
            const errorData = await response.json().catch(() => ({})); // JSON 파싱 실패 대비
            const errorMsg = errorData.error || errorData.message || errorData.detail || '서버 오류가 발생했습니다.';
            alert(`로그인 처리 실패: ${errorMsg}`);
            navigate('/login', { replace: true }); // 뒤로가기 방지하며 로그인 페이지로 돌려보냄
          }
        } catch (error) {
          // [추가된 방어 로직 2] 백엔드가 완전히 죽었거나 네트워크 통신 자체가 실패했을 때
          console.error("카카오 로그인 통신 에러:", error);
          alert('서버와 연결할 수 없습니다. DB나 백엔드 서버 상태를 확인해 주세요.');
          navigate('/login', { replace: true });
        }
      };
-

    sendCodeToBackend();
  }, [code, navigate]);

  return (
    <div style={{ display: 'flex', justifyContent: 'center', marginTop: '100px' }}>
      <h2>카카오 로그인 처리 중입니다. 잠시만 기다려주세요... 🚀</h2>
    </div>
  );
};

export default KakaoCallbackPage;
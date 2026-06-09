import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import '../css/SeniorRegisterPage.css';

import { SeniorInfo } from '../types/interface';


const SeniorRegisterPage = () => {
  const navigate = useNavigate();

  // 상태 관리
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResult, setSearchResult] = useState<SeniorInfo | null>(null);
  const [isRequestSent, setIsRequestSent] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');

  const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

  // 1. 어르신 검색 핸들러 (실제 API 연동)
  const handleSearch = async () => {
    if (!searchQuery.trim()) return;

    setIsLoading(true);
    setErrorMsg('');
    setSearchResult(null);

    try {
      const token = localStorage.getItem('access_token');
      if (!token) {
        setErrorMsg('로그인이 필요합니다.');
        setIsLoading(false);
        return;
      }

      // 백엔드의 정확도 100% 일치 검색 API 호출
      const response = await fetch(
        `${API_BASE_URL}/api/v1/guardian/search-senior?username=${searchQuery}`,
        {
          method: 'GET',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`
          }
        }
      );


      // JSON으로 변환하기 전에 401 토큰 만료부터 최우선으로 검사
      if (response.status === 401) {
        alert("세션이 만료되었습니다. 다시 로그인해주세요.");
        localStorage.clear(); // 로컬 스토리지 전체 초기화
        navigate('/login');
        return;
      }

      const result = await response.json();

      if (response.ok && result.code === 200) {
        // 검색 성공
        setSearchResult({
          id: result.data.dependent_id,
          username: result.data.username,
          name: result.data.name,
          join_date: result.data.created_at ? result.data.created_at.split('T')[0] : '정보 없음',
          last_active: result.data.last_active || '최근 활동 확인 불가' // 백엔드 스펙에 맞춰 조정
        });
      } else if (result.code === 404) {
        // 일치하는 아이디가 없을 때
        setErrorMsg('해당 아이디를 사용하는 어르신을 찾을 수 없거나, 검색이 허용되지 않은 계정입니다.');
      } else {
        setErrorMsg(result.error || '검색 중 오류가 발생했습니다.');
      }
    } catch (err) {
      console.error("Search API Error:", err);
      setErrorMsg('서버와의 통신에 실패했습니다.');
    } finally {
      setIsLoading(false);
    }
  };

  // 2. 연동 요청 핸들러 (실제 API 연동)
  const handleLinkRequest = async () => {
    if (!searchResult) return;

    setIsLoading(true);
    setErrorMsg('');

    try {
      const token = localStorage.getItem('access_token');
      const guardianStr = localStorage.getItem('guardian_info');

      if (!token || !guardianStr) {
        setErrorMsg('인증 정보가 없습니다. 다시 로그인해주세요.');
        setIsLoading(false);
        return;
      }

      const guardianId = JSON.parse(guardianStr).id;

      // 연동 요청 POST API 호출 (매핑 테이블에 PENDING 상태로 추가하는 백엔드 엔드포인트)
      const response = await fetch(
        `${API_BASE_URL}/api/v1/guardian/link-senior`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`
          },
          body: JSON.stringify({
            dependent_id: searchResult.id
          })
        }
      );


      // JSON으로 변환하기 전에 401 토큰 만료부터 최우선으로 검사
      if (response.status === 401) {
        alert("세션이 만료되었습니다. 다시 로그인해주세요.");
        localStorage.clear(); // 로컬 스토리지 전체 초기화
        navigate('/login');
        return;
      }

      const result = await response.json();

      if (response.ok && (result.code === 200 || result.code === 201)) {
        // 🌟 성공 시 로컬 스토리지에 dependent_id를 저장하여 대시보드에서 인식하게 함
        localStorage.setItem('dependent_id', searchResult.id);
        setIsRequestSent(true); // 성공(대기) 화면으로 상태 전환
      } else {
        setErrorMsg(result.error || '연동 요청에 실패했습니다. (이미 요청되었거나 차단된 상태일 수 있습니다.)');
      }
    } catch (err) {
      console.error("Link Request API Error:", err);
      setErrorMsg('연동 요청 중 서버 에러가 발생했습니다.');
    } finally {
      setIsLoading(false);
    }
  };

  // 3. 연동 취소 핸들러

  // 🌟 인자로 targetId를 받도록 수정합니다.
  const handleCancelRequest = async (targetId: string) => {
    setIsLoading(true);
    setErrorMsg('');

    try {
      const token = localStorage.getItem('access_token');

      if (!token) {
        setErrorMsg('인증 정보가 없습니다. 다시 로그인해주세요.');
        setIsLoading(false);
        return;
      }

      // 연동 취소 DELETE API 호출 (targetId 사용)
      const response = await fetch(
        `${API_BASE_URL}/api/v1/guardian/cancel-link/${targetId}`,
        {
          method: 'DELETE',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`
          }
        }
      );

      // JSON으로 변환하기 전에 401 토큰 만료부터 최우선으로 검사
      if (response.status === 401) {
        alert("세션이 만료되었습니다. 다시 로그인해주세요.");
        localStorage.clear();
        navigate('/login');
        return;
      }

      const result = await response.json();

      if (response.ok && result.code === 200) {
        alert("연동 요청이 취소되었습니다.");
        setSearchResult(null); // 화면 초기화 (다시 검색 가능한 상태로)
      } else {
        setErrorMsg(result.error || '연동 취소에 실패했습니다.');
      }
    } catch (err) {
      console.error("Cancel Link API Error:", err);
      setErrorMsg('서버 에러가 발생했습니다.');
    } finally {
      setIsLoading(false);
    }
  };



  return (
    <div className="register-container">
      <div className="register-content">

        {/* 상단 공통 헤더 */}
        <div style={{ marginBottom: '20px', cursor: 'pointer', fontWeight: 'bold' }} onClick={() => navigate(-1)}>
          ← 뒤로 가기
        </div>

        <div className="register-header">
          <h1 className="register-title">어르신 연동하기</h1>
          <p className="register-subtitle">어르신 계정을 연동하여 건강과 안전을 함께 관리해보세요.</p>
        </div>

        <div className="register-card">

          {/* STEP 1 & 2: 연결 전 화면 (검색 및 결과 확인) */}
          {!isRequestSent ? (
            <>
              <div className="search-section">
                <label className="search-label">어르신 아이디 검색</label>
                <p className="search-desc">어르신이 사용 중인 아이디를 입력하고 검색해주세요.</p>
                <div className="search-input-group">
                  <input
                    type="text"
                    className="search-input"
                    placeholder="예) yeonghui1940"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    onKeyPress={(e) => e.key === 'Enter' && handleSearch()}
                  />
                  <button className="search-btn" onClick={handleSearch} disabled={isLoading}>
                    {isLoading && !searchResult ? '검색중' : '검색'}
                  </button>
                </div>

                {errorMsg && (
                  <div style={{ color: '#D32F2F', fontSize: '13px', marginTop: '10px' }}>{errorMsg}</div>
                )}

                {/* 검색 전 안내 문구 */}
                {!searchResult && !errorMsg && (
                  <div className="search-guide-box">
                    💡 어르신 기기(라즈베리파이) 또는 앱의 [내 정보]에서 아이디를 확인할 수 있습니다.<br />
                    (어르신 설정에서 '검색 허용'이 켜져 있어야 합니다)
                  </div>
                )}
              </div>

              {/* 검색 결과 카드 */}
              {searchResult && (
                <div>
                  <div style={{ fontSize: '13px', color: '#388E3C', backgroundColor: '#E8F5E9', padding: '8px 12px', borderRadius: '4px', marginBottom: '15px' }}>
                    검색 결과를 찾았습니다.
                  </div>

                  <div className="senior-profile-card">
                    <div className="profile-top">
                      <div className="profile-avatar-large">👵🏻</div>
                      <div className="profile-details">
                        <h3 className="senior-name">{searchResult.name} 어르신</h3>
                        <div className="info-row">
                          <span className="info-label">아이디</span>
                          <span className="info-value">{searchResult.username}</span>
                        </div>
                        <div className="info-row">
                          <span className="info-label">가입일</span>
                          <span className="info-value">{searchResult.join_date}</span>
                        </div>
                        <div className="info-row">
                          <span className="info-label">최근 활동</span>
                          <span className="info-value">{searchResult.last_active}</span>
                        </div>
                      </div>
                    </div>

                    <button className="link-request-btn" onClick={handleLinkRequest} disabled={isLoading}>
                      <span>🔗</span> {isLoading ? '요청 중...' : '연동 요청 보내기'}
                    </button>
                  </div>
                </div>
              )}
            </>
          ) : (

            /* STEP 3: 연동 요청 완료(대기) 화면 */
            <div className="success-section">
              <div className="success-icon" style={{ backgroundColor: '#E3F2FD', color: '#1976D2' }}>🛫</div>
              <h2 className="success-title">연동 요청 완료!</h2>
              <p className="success-desc">
                {searchResult?.name} 어르신의 앱으로 연동 요청을 보냈습니다.<br />
                <strong style={{ color: '#1976D2' }}>어르신이 수락하시면</strong> 대시보드에 데이터가 나타납니다.
              </p>

              <div className="senior-profile-card" style={{ textAlign: 'left', marginBottom: '20px', backgroundColor: '#FAFAFA' }}>
                <div className="profile-top" style={{ marginBottom: 0 }}>
                  <div className="profile-avatar-large" style={{ opacity: 0.7 }}>👵🏻</div>
                  <div className="profile-details">
                    <h3 className="senior-name">{searchResult?.name} 어르신</h3>
                    <div className="info-row">
                      <span className="info-label">상태</span>
                      <span className="info-value" style={{ color: '#E65100', fontWeight: 'bold' }}>수락 대기 중</span>
                    </div>
                  </div>
                </div>
              </div>

              <div className="search-guide-box" style={{ textAlign: 'left' }}>
                어르신이 알림을 확인하지 못하시는 경우, 전화로 <strong>앱에 접속하여 연동 요청을 수락</strong>해 달라고 안내해 주세요.
              </div>

              <div className="action-buttons">
                {/* 라우터 설정에 맞춰 루트 경로(/)인 대시보드로 이동 */}
                <button className="btn-solid" onClick={() => navigate('/')}>대시보드로 돌아가기</button>
              </div>
            </div>
          )}

        </div>
      </div>
    </div>
  );
};

export default SeniorRegisterPage;
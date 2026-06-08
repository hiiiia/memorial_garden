// src/pages/SeniorRegisterPage.tsx

import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import '../css/SeniorRegisterPage.css';

interface SeniorInfo {
  senior_id: number;
  username: string;
  name: string;
  join_date: string;
  last_active: string;
}

const SeniorRegisterPage = () => {
  const navigate = useNavigate();
  
  // 상태 관리
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResult, setSearchResult] = useState<SeniorInfo | null>(null);
  const [isRequestSent, setIsRequestSent] = useState(false); // isLinked -> isRequestSent로 의미 명확화
  const [isLoading, setIsLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');

  // 1. 어르신 검색 핸들러 (Mock 데이터)
  const handleSearch = async () => {
    if (!searchQuery.trim()) return;
    
    setIsLoading(true);
    setErrorMsg('');
    setSearchResult(null);

    // [UI 테스트용 임시 로직]
    setTimeout(() => {
      if (searchQuery === 'yeonghui1940' || searchQuery.includes('yeong')) {
        setSearchResult({
          senior_id: 1,
          username: "yeonghui1940",
          name: "김영희",
          join_date: "2026.03.15",
          last_active: "오늘 접속함"
        });
      } else {
        setErrorMsg('해당 아이디를 사용하는 어르신을 찾을 수 없거나, 검색이 허용되지 않은 계정입니다.');
      }
      setIsLoading(false);
    }, 600);
  };

  // 2. 연동 요청 핸들러 (Mock 데이터)
  const handleLinkRequest = async () => {
    if (!searchResult) return;
    
    setIsLoading(true);
    setErrorMsg('');

    // [UI 테스트용 임시 로직]
    setTimeout(() => {
      setIsRequestSent(true); // 성공(대기) 화면으로 상태 전환
      setIsLoading(false);
    }, 600);
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
                    placeholder="예) memorial_user_1"
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
                    💡 어르신 앱의 [설정] &gt; [내 정보]에서 아이디를 확인할 수 있습니다.<br/>
                    (어르신 앱에서 '아이디 검색 허용'이 켜져 있어야 합니다)
                  </div>
                )}
              </div>

              {/* 검색 결과 카드 */}
              {searchResult && (
                <div>
                  <div style={{ fontSize: '13px', color: '#388E3C', backgroundColor: '#E8F5E9', padding: '8px 12px', borderRadius: '4px' }}>
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
              {/* V 체크 마크 대신 종이비행기 알림 느낌의 아이콘으로 교체 */}
              <div className="success-icon" style={{ backgroundColor: '#E3F2FD', color: '#1976D2' }}>🛫</div>
              <h2 className="success-title">연동 요청 완료!</h2>
              <p className="success-desc">
                {searchResult?.name} 어르신의 앱으로 연동 요청을 보냈습니다.<br/>
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
                {/* 대시보드로 이동하여 '수락 대기 중' 상태 확인 */}
                <button className="btn-solid" onClick={() => navigate('/dashboard')}>대시보드로 돌아가기</button>
              </div>
            </div>
          )}

        </div>
      </div>
    </div>
  );
};

export default SeniorRegisterPage;
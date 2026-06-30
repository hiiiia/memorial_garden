import React from 'react';

interface Diary {
  id: string | number;
  content: string;
  image_url: string;
  created_at: string;
}

interface DiaryPageProps {
  todayFormatted: string;
  todayDiary?: Diary;
  onNext: () => void;
}

const DiaryPage: React.FC<DiaryPageProps> = ({
  todayFormatted,
  todayDiary,
  onNext,
}) => {
  return (
    <div className="home-card diary-card">
      <h1 className="diary-title">오늘의 일기</h1>
      <p className="diary-date">{todayFormatted}</p>

      {todayDiary ? (
        <div className="diary-content">
          <div className="diary-image">
            {todayDiary.image_url ? (
              <img src={todayDiary.image_url} alt="오늘의 그림" />
            ) : (
              <span>그림 준비 중 🎨</span>
            )}
          </div>

          <div className="diary-text-box">
            {todayDiary.content}
          </div>
        </div>
      ) : (
        <div className="diary-empty">
          <span className="empty-icon">📭</span>
          <p>어르신, 오늘은 아직 일기를 쓰지 않으셨어요.</p>
          <small>대화를 나누면 일기가 자동으로 만들어집니다.</small>
        </div>
      )}

      <div className="diary-buttons">
        <button className="diary-next-btn" onClick={onNext}>
          ➡ 다음
        </button>
      </div>
    </div>
  );
};

export default DiaryPage;
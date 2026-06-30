import React from 'react';

interface Diary {
  id: string | number;
  content: string;
  image_url: string;
  created_at: string;
}

interface DetailPageProps {
  selectedDiary: Diary | null;
  onClose: () => void;
}

const DetailPage: React.FC<DetailPageProps> = ({
  selectedDiary,
  onClose,
}) => {
  return (
    <div className="home-card detail-card">
      <div className="detail-top">
        <div className="detail-image-box">
          <img src={selectedDiary?.image_url} alt="상세 이미지" />
        </div>

        <div className="detail-info">
          <p className="detail-date">{selectedDiary?.created_at}</p>

          <p className="detail-desc">
            {selectedDiary?.content}
          </p>
        </div>
      </div>

      <div className="detail-buttons">
        <button className="detail-close-btn" onClick={onClose}>
          ❌ 닫기
        </button>
      </div>
    </div>
  );
};

export default DetailPage;
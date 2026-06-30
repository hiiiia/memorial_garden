import React from 'react';

interface Diary {
  id: string | number;
  content: string;
  image_url: string;
  created_at: string;
}

interface MemoryPageProps {
  uniqueDates: string[];
  currentViewDate: string;
  selectedDateIndex: number;
  itemStartIndex: number;
  itemsPerPage: number;
  diariesForDate: Diary[];
  visibleMemories: Diary[];
  onPrevDate: () => void;
  onNextDate: () => void;
  onPrevItems: () => void;
  onNextItems: () => void;
  onSelectSend: (diary: Diary) => void;
  onSelectDetail: (diary: Diary) => void;
  onClose: () => void;
}

const MemoryPage: React.FC<MemoryPageProps> = ({
  uniqueDates,
  currentViewDate,
  selectedDateIndex,
  itemStartIndex,
  itemsPerPage,
  diariesForDate,
  visibleMemories,
  onPrevDate,
  onNextDate,
  onPrevItems,
  onNextItems,
  onSelectSend,
  onSelectDetail,
  onClose,
}) => {
  return (
    <div className="home-card memory-card">
      <h1 className="memory-title">나의 추억</h1>

      {uniqueDates.length > 0 && (
        <div className="memory-nav">
          <button
            onClick={onPrevDate}
            disabled={selectedDateIndex === uniqueDates.length - 1}
            className="memory-nav-btn"
          >
            ◀ 이전
          </button>

          <h2 className="memory-nav-date">{currentViewDate}</h2>

          <button
            onClick={onNextDate}
            disabled={selectedDateIndex === 0}
            className="memory-nav-btn"
          >
            다음 ▶
          </button>
        </div>
      )}

      <div className="memory-content">
        <button
          className="memory-arrow"
          onClick={onPrevItems}
          disabled={itemStartIndex === 0}
        >
          ‹
        </button>

        <div className="memory-list">
          {visibleMemories.length > 0 ? (
            visibleMemories.map((memory) => (
              <div className="memory-item" key={memory.id}>
                <div className="memory-image">
                  {memory.image_url ? (
                    <img src={memory.image_url} alt="추억 이미지" />
                  ) : (
                    <span>🎨</span>
                  )}
                </div>

                <div className="memory-info">
                  <h2>{memory.content.slice(0, 8)} 날</h2>
                  <p>{memory.created_at}</p>
                </div>

                <div className="memory-action-buttons">
                  <button
                    className="memory-send-btn"
                    onClick={() => onSelectSend(memory)}
                  >
                    ✉ 보내기
                  </button>

                  <button
                    className="memory-view-btn"
                    onClick={() => onSelectDetail(memory)}
                  >
                    🔍 보기
                  </button>
                </div>
              </div>
            ))
          ) : (
            <div className="memory-empty">
              <span className="empty-icon">🗂️</span>
              <p>저장된 추억이 없습니다.</p>
            </div>
          )}
        </div>

        <button
          className="memory-arrow"
          onClick={onNextItems}
          disabled={itemStartIndex + itemsPerPage >= diariesForDate.length}
        >
          ›
        </button>
      </div>

      <button className="memory-close-btn" onClick={onClose}>
        ❌ 닫기
      </button>
    </div>
  );
};

export default MemoryPage;
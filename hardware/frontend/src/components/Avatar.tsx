import React from 'react';

// 외부에서 '상태'를 전달받기 위한 타입 정의
type AvatarProps = {
  state: 'idle' | 'listening' | 'processing' | 'speaking';
};

const Avatar: React.FC<AvatarProps> = ({ state }) => {
  return (
    <div className={`avatar-box ${state}`}>
      {state === 'idle' && '👵'}
      {state === 'listening' && '🎙️'}
      {state === 'processing' && '⏳'}
      {state === 'speaking' && '💬'}
    </div>
  );
};

export default Avatar;
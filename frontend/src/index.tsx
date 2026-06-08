// src/index.tsx
import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';

const rootElement = document.getElementById('root');

if (rootElement) {
  const root = ReactDOM.createRoot(rootElement);
  root.render(
    // React.StrictMode는 개발 모드에서 잠재적 버그를 찾기 위해 컴포넌트를 두 번씩 렌더링합니다.
    <React.StrictMode>
      <App />
    </React.StrictMode>
  );
}
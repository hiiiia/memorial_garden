FROM node:18-slim

WORKDIR /app

COPY package*.json ./
RUN npm install --legacy-peer-deps

COPY . .

# Nginx 정적 서빙 대신 React 개발 서버(Hot Reload 지원) 실행
CMD ["npm", "start"]
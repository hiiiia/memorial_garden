## Github Desktop / SourceTree 을 사용하는걸 추천드립니다

# 🚀 [Memorial_garden / 기억정원 프로젝트] 

본 프로젝트는 React, FastAPI, Arduino, Python(AI)을 활용한 [프로젝트 한 줄 설명]입니다.

## 📂 저장소 구조 (Directory Structure)
우리 프로젝트는 하나의 저장소 안에서 폴더로 파트를 구분하는 **모노레포(Monorepo)** 방식을 사용합니다.
본인이 담당하는 파트의 폴더 안에서만 코드를 작성해 주세요!

```text
📁 root
 ├── 📁 frontend   # React.js (웹 프론트엔드)
 ├── 📁 backend    # FastAPI (API 서버)
 ├── 📁 arduino    # C++ (하드웨어 제어)
 └── 📁 ai         # Python, Jupyter (데이터 분석 및 모델링)

```
## 🤝 Git 협업 가이드 (팀원 필독!)

코드 작업 전 반드시 아래의 규칙을 확인해 주세요. 
**`main` 브랜치에 직접 코드를 올리는 것(Push)은 절대 금지합니다!**

### 1. 기본 작업 흐름 (Workflow)
작업은 항상 나만의 '격리된 공간(브랜치)'에서 진행한 뒤, 허락을 받고 합치는(PR) 방식으로 진행합니다.

1. **최신화:** `git pull origin main` (항상 최신 코드를 내려받고 시작하세요)
2. **브랜치 생성 및 이동:** `git checkout -b 브랜치이름`
3. **작업 및 저장:** `git add .` ➡️ `git commit -m "커밋 메시지 규칙 참고"`
4. **내 브랜치에 올리기:** `git push origin 브랜치이름`
5. **리뷰 요청:** GitHub 웹사이트에 접속해서 **Pull Request (PR)** 를 생성합니다.

---

### 2. 브랜치(Branch) 이름 규칙
본인이 어떤 파트의 무슨 작업을 하는지 명확히 적어주세요.
👉 형식: 작업종류/파트/기능이름

파트 구분: front, back, hw(아두이노), ai

작업 종류: feat(기능추가), fix(버그수정), docs(문서), chore(세팅)

✅ 브랜치 이름 예시

feat/front/login-ui : 프론트엔드 로그인 UI 작업

feat/back/user-api : 백엔드 유저 API 연동

fix/hw/sensor-error : 아두이노 센서 인식 오류 수정

docs/ai/model-test : AI 모델 테스트 결과 문서화

---

### 3. 커밋 메시지 (Commit Message) 규칙
커밋 기록만 보고도 어떤 파일이 왜 수정되었는지 알 수 있어야 합니다.
👉 형식: [파트] 작업종류: 작업 내용 요약

* `feat:` 새로운 기능 추가
* `fix:` 버그 수정
* `docs:` 문서 수정 (README 등)
* `style:` 코드 스타일 변경, 띄어쓰기/세미콜론 수정 (로직 변경 없음)
* `refactor:` 코드 리팩토링 (기능은 똑같지만 코드를 깔끔하게 개선)
* `chore:` 패키지 설치, 빌드 세팅 등 자잘한 수정

✅ 커밋 메시지 예시

[front] feat: 카카오 로그인 버튼 추가

[back] fix: DB 연결 시간 초과 에러 해결

[hw] chore: 핀 번호 설정 변수명 변경

[ai] feat: YOLO 객체 인식 기본 로직 추가

**❌ 나쁜 예시**
* `수정함`
* `최종_진짜최종_커밋`
* `feat: 이것저것 많이 고침`

---

### 4. 🚨 머지(Merge) 및 작업 시 주의사항 🚨
이것만은 꼭 지켜주세요! 코드가 날아가는 대참사를 막을 수 있습니다.

1. **작업 시작 전 항상 `Pull` 받기**
   * 내가 작업하는 동안 다른 사람이 코드를 올렸을 수 있습니다. 항상 `git pull origin main`으로 최신 상태를 유지해 주세요.
2. **함부로 Merge 금지 (PR 필수)**
   * 코드를 다 짰다고 혼자서 합치면 안 됩니다. 반드시 **Pull Request**를 열고, 팀원(또는 팀장)의 코드 리뷰와 승인(Approve)을 받은 후에만 `main`에 Merge 할 수 있습니다.
3. **강제 푸시(`push -f`) 절대 금지**
   * 다른 사람의 코드를 덮어씌워 버릴 수 있는 아주 위험한 명령어입니다.
4. **충돌(Conflict)이 발생했을 때**
   * GitHub에서 'Can't automatically merge'라는 경고가 뜨거나 터미널에서 충돌이 났다면 **절대 임의로 남의 코드를 지우지 마세요!**
   * 당황하지 말고 해당 파일을 함께 수정한 팀원이나 팀장에게 즉시 상황을 공유해서 같이 해결해야 합니다.

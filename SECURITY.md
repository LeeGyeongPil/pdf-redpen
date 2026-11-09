# 보안 정책 / Security policy

보안 취약점을 발견하셨다면 **공개 이슈 대신** 이 레포의 **Security → Report a vulnerability**(비공개 취약점 신고)로 알려 주세요. 확인 후 답변드리고, 고친 버전을 릴리스하면서 함께 안내합니다.

If you find a security issue, please **do not open a public issue**. Use **Security → Report a vulnerability** in this repository to report it privately. We will reply after checking and announce the fix with a release.

pdf-redpen은 서버를 열지 않는 CLI입니다. 실제 `review` 모드는 PDF 쪽 글자를 `PDF_REDPEN_BASE_URL`(기본값은 내 컴퓨터의 localhost)로 보내므로, 민감한 문서는 로컬 모델을 쓰세요. API 키(`PDF_REDPEN_API_KEY`)는 `Authorization` 헤더에만 쓰며 리포트·녹화 파일에 기록하지 않습니다. `demo`·`apply`·`clear`·`review --mock`은 네트워크를 쓰지 않습니다.

pdf-redpen is a CLI and opens no server. The real `review` mode sends page text to `PDF_REDPEN_BASE_URL` (default: localhost), so use a local model for sensitive documents. The API key (`PDF_REDPEN_API_KEY`) is only used in the `Authorization` header and is never written to reports or recordings. `demo`, `apply`, `clear` and `review --mock` do not use the network.

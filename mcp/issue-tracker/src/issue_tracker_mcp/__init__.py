"""IssueTracker MCP — GitHub Issues + Projects v2 어댑터.

본 패키지는 외부 이슈 트래커 SaaS 의 추상화 (`IssueTracker` ABC) 와 GitHub
어댑터 구현체를 함께 보유. 다른 backend (Jira / Linear 등) 추가는
`adapters/<name>.py` + `factory.py` 에 1줄 등록 (OCP).
"""

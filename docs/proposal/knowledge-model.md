# 지식 그래프 모델링

> 본 문서는 [`proposal-main.md`](../proposal-main.md) §4 에서 분리. (#66)

### 4.1. Semantic Layer (Neo4j)

## 인터페이스 중심 구현 모델

```
(Class)-[:IMPLEMENTS]->(Interface)
(Class)-[:DEPENDS_ON]->(Interface)
(PublicMethod)-[:BELONGS_TO]->(Interface)
(Module)-[:CONTAINS]->(Class)
```

- **Method 노드는 public 메소드(계약된 인터페이스 시그니처)만 포함** — 내부 구현 상세(private/protected)는 그래프에 포함하지 않음
- 에이전트가 특정 구현체에 종속되지 않고 유연하게 설계 논의
- 인터페이스 매개 객체 간 참조 관계로 변경 영향 범위 즉각 파악

## 과업-코드 추적성 모델

```
(Task)-[:AFFECTS]->(Interface)
(Task)-[:REALIZED_IN]->(Method)
(Feature)-[:DECOMPOSED_INTO]->(Task)
(BugReport)-[:TRACES_TO]->(Method)
```

- Task, Feature, BugReport 노드가 독립적으로 존재
- 과업과 코드 직접 연결로 비즈니스 문맥 유지

### 4.2. Episodic Layer (Doc Store)

## 저장 대상
- **Task 정보**: 목표, 기능, 진행 상태, 히스토리
- **기술 사항**: 설계 결정, 구현 특이점, 주의사항, TODO
- **설계안**: 채택안(메타 정보, 실제 문서는 코드베이스)/미채택안(전문)
- **PRD**: 사용자-P 협의 결과
- **대화 이력**: Task → Session → Item 3계층

## Task/Session/Item 컬렉션

**tasks (태스크):**
```json
{
  "_id": "TASK-001",
  "title": "결제 모듈 추가",
  "goal": "Stripe 연동으로 신용카드 결제 지원",
  "status": "in_progress",
  "prd_ref": "PRD-001",
  "design_choice": {
    "selected": "docs/design/TASK-001-payment-gateway.md",
    "alternatives": ["design_alt_1", "design_alt_2"]
  },
  "assignees": ["Eng:BE", "QA:BE"],
  "created_at": "2026-04-16T09:00:00Z",
  "updated_at": "2026-04-16T10:30:00Z"
}
```

**sessions (대화 세션):**
```json
{
  "_id": "SES-xxx",
  "task_id": "TASK-001",
  "topic": "Eng:BE의 PaymentGateway 인터페이스 설계 변경 제안",
  "participants": ["Eng:BE", "A"],
  "started_at": "2026-04-16T10:00:00Z",
  "closed_at": null
}
```

**items (개별 메시지):**
```json
{
  "_id": "ITM-42",
  "task_id": "TASK-001",
  "session_id": "SES-xxx",
  "prev_item_id": "ITM-41",
  "from": "Eng:BE",
  "to": "A",
  "type": "design_change_proposal",
  "payload": { "...": "..." },
  "timestamp": "2026-04-16T10:15:00Z"
}
```

**technical_notes (기술 문서):**
```json
{
  "_id": "TN-007",
  "task_id": "TASK-001",
  "category": "implementation_note",  // design_decision | todo | caution | concept
  "title": "Stripe webhook 재시도 멱등성 보장",
  "content": "...",
  "source_agent": "Eng:BE",
  "source_diff_ref": "DIFF-015"
}
```

**design_alternatives (미채택 설계안):**
```json
{
  "_id": "design_alt_1",
  "task_id": "TASK-001",
  "title": "Adapter 없이 Stripe SDK 직접 호출",
  "risk_score": 0.6,
  "est_hours": 4,
  "content": "...",
  "rejected_at": "2026-04-16T09:30:00Z",
  "rejection_reason": "Stripe 외 다른 PG 지원 어려움"
}
```

## 조회 쿼리 예시

| 목적 | 쿼리 |
|------|------|
| 태스크 전체 히스토리 | `items.find({ task_id })` 정렬 by timestamp |
| 특정 대화 세션 맥락 | `items.find({ session_id })` 정렬 by prev_item_id 체인 |
| 대화 쓰레드 역추적 | `item_id`에서 `prev_item_id`를 따라 올라가며 재귀 조회 |
| 태스크의 기술 메모 | `technical_notes.find({ task_id })` |
| 태스크의 대안 설계 | `design_alternatives.find({ task_id })` |

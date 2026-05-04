"""IssueTracker MCP 1차 검증 스크립트.

서버: http://localhost:9101/mcp (이미 부팅된 컨테이너 가정)
대상 board: vonkernel/guestbook 의 GITHUB_PROJECT_NUMBER

검증 시퀀스:
  1. field.list      board 의 field 구조 확인
  2. field.create    "Issue Type" single-select 보장 (없으면 추가)
  3. type.list/create  Epic / Story / Task 보장
  4. status.list/create Backlog / Ready 보장
  5. issue.create    [verify] 타이틀로 이슈 생성
  6. issue.transition Ready 로 이동
  7. issue.get       반영 확인
  8. issue.close     검증용 이슈 close
"""

from __future__ import annotations

import asyncio
import sys

from dev_team_shared.issue_tracker import (
    IssueCreate,
    IssueTrackerClient,
)
from dev_team_shared.mcp_client import StreamableMCPClient


async def main() -> int:
    url = "http://localhost:9101/mcp"
    print(f"connecting to {url}...")

    async with await StreamableMCPClient.connect(url) as mcp:
        client = IssueTrackerClient(mcp)

        # 1. field.list
        print("\n[1] field.list")
        fields = await client.field_list()
        for f in fields:
            print(f"    - {f.name} ({f.kind}) id={f.id}")
        names = {f.name: f for f in fields}

        # 2. ensure Type single-select
        print("\n[2] field.create('Type', 'single_select') - idempotent")
        type_field = await client.field_create("Issue Type", "single_select")
        print(f"    Type field: id={type_field.id} kind={type_field.kind}")
        had_type = "Issue Type" in names
        print(f"    (existed before: {had_type})")

        # 3. type.list / create
        print("\n[3] type.list")
        types = await client.type_list()
        for t in types:
            print(f"    - {t.name} id={t.id}")
        type_by_name = {t.name: t for t in types}
        for tname in ["Epic", "Story", "Task"]:
            if tname not in type_by_name:
                created = await client.type_create(tname)
                print(f"    type.create({tname!r}) → id={created.id}")
                type_by_name[tname] = created
        epic = type_by_name["Epic"]

        # 4. status.list / create
        print("\n[4] status.list")
        statuses = await client.status_list()
        for s in statuses:
            print(f"    - {s.name} id={s.id}")
        status_by_name = {s.name: s for s in statuses}
        for sname in ["Backlog", "Ready"]:
            if sname not in status_by_name:
                created_s = await client.status_create(sname)
                print(f"    status.create({sname!r}) → id={created_s.id}")
                status_by_name[sname] = created_s
        backlog = status_by_name["Backlog"]
        ready = status_by_name["Ready"]

        # 5. issue.create
        # 옵션 id 는 update 후 reissued 가능 — refresh 후 사용.
        print("\n[5] issue.create  (Epic + Backlog) — refresh ids first")
        types_now = {t.name: t for t in await client.type_list()}
        statuses_now = {s.name: s for s in await client.status_list()}
        epic = types_now["Epic"]
        backlog = statuses_now["Backlog"]
        ready = statuses_now["Ready"]
        issue = await client.issue_create(
            IssueCreate(
                title="[verify] sandbox issue (auto)",
                body=(
                    "Created by mcp/issue-tracker verify script.\n"
                    "Safe to close / delete."
                ),
                type_id=epic.id,
                status_id=backlog.id,
            ),
        )
        print(f"    ref={issue.ref} title={issue.title!r}")
        print(f"    type={issue.type} status={issue.status}")

        # 6. issue.transition → Ready
        print("\n[6] issue.transition → Ready")
        await client.issue_transition(issue.ref, status_id=ready.id)
        print("    transition OK")

        # 7. issue.get
        print("\n[7] issue.get")
        fetched = await client.issue_get(issue.ref)
        if fetched is None:
            print("    !! issue.get returned None")
            return 1
        print(f"    status={fetched.status} type={fetched.type}")
        if fetched.status is None or fetched.status.name != "Ready":
            print(f"    !! expected status=Ready, got {fetched.status}")
            return 1
        if fetched.type is None or fetched.type.name != "Epic":
            print(f"    !! expected type=Epic, got {fetched.type}")
            return 1

        # 8. issue.close
        print("\n[8] issue.close")
        ok = await client.issue_close(issue.ref)
        print(f"    close ok={ok}")

        print("\nALL PASS ✅")
        print(f"verification issue ref={issue.ref} (closed)")
        return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

# syntax=docker/dockerfile:1
#
# Primary 에이전트 이미지.
#
# 생성 기준: `langgraph dockerfile ./Dockerfile` (langgraph-cli 0.4.x) 결과에
# 다음 두 가지를 커스텀 추가:
#   1) shared 패키지 설치 레이어 (primary 가 dev-team-shared 에 의존).
#   2) `ADD` 경로를 repo root 기준으로 변경 (빌드 컨텍스트 = repo root).
#
# 빌드 (레포 루트에서):
#   docker build -f agents/primary/Dockerfile -t primary:latest .
#
# 빌드 전략 전반은 docs/agent-runtime.md §3 참조.

FROM langchain/langgraph-api:3.13

# -- 1) shared 패키지 설치 (커스텀 레이어, primary 보다 먼저 설치) --
#    shared 를 먼저 설치해 두면 primary 설치 시 `dev-team-shared` 의존을
#    이미 설치된 패키지에서 해소한다 (uv pip 는 pyproject.toml 의
#    [tool.uv.sources] 를 무시하므로 workspace 참조 문제 없음).
ADD ./shared /deps/shared
RUN cd /deps/shared && PYTHONDONTWRITEBYTECODE=1 uv pip install --system --no-cache-dir -c /api/constraints.txt -e .

# -- 2) primary 패키지 설치 (local package) --
#    Docker 환경에는 workspace 루트 pyproject.toml 이 없으므로, primary 의
#    [tool.uv.sources] 블록(workspace 참조)을 제거한 뒤 설치한다.
#    shared 는 위에서 이미 설치되어 있어 `dev-team-shared` 는 일반 패키지
#    레퍼런스로 즉시 해소됨. 로컬 dev 의 pyproject.toml 원본은 영향 없음.
ADD ./agents/primary /deps/primary
RUN sed -i '/^\[tool\.uv\.sources\]/,/^$/d' /deps/primary/pyproject.toml
RUN cd /deps/primary && PYTHONDONTWRITEBYTECODE=1 uv pip install --system --no-cache-dir -c /api/constraints.txt -e .

# langgraph-api 런타임이 로드할 graph 매핑 (langgraph.json 의 graphs 와 동일).
ENV LANGSERVE_GRAPHS='{"primary": "primary_agent.graph:graph"}'

# -- Ensure user deps didn't inadvertently overwrite langgraph-api --
RUN mkdir -p /api/langgraph_api /api/langgraph_runtime /api/langgraph_license && touch /api/langgraph_api/__init__.py /api/langgraph_runtime/__init__.py /api/langgraph_license/__init__.py
RUN PYTHONDONTWRITEBYTECODE=1 uv pip install --system --no-cache-dir --no-deps -e /api
# -- End of ensuring user deps didn't inadvertently overwrite langgraph-api --

# -- Removing build deps from the final image ~<:===~~~ --
RUN pip uninstall -y pip setuptools wheel
RUN rm -rf /usr/local/lib/python*/site-packages/pip* /usr/local/lib/python*/site-packages/setuptools* /usr/local/lib/python*/site-packages/wheel* && find /usr/local/bin -name "pip*" -delete || true
RUN rm -rf /usr/lib/python*/site-packages/pip* /usr/lib/python*/site-packages/setuptools* /usr/lib/python*/site-packages/wheel* && find /usr/bin -name "pip*" -delete || true
RUN uv pip uninstall --system pip setuptools wheel && rm /usr/bin/uv /usr/bin/uvx

WORKDIR /deps/primary

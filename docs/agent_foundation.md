# Nền tảng Agent

Tài liệu này mô tả BaseAgent và controller chung. Phần kế thừa cho điều tra đã
có workflow gọi tool, graph SQLite và client Gemini; xem
[Agent điều tra](investigation_agent.md). Lá chắn, tạo cụm, sàng lọc, xác thực
và giao diện nghiệp vụ chưa triển khai.

## Cấu trúc và luồng xử lý

```text
app/
├── main.py                           # create_app(), health, gắn router
├── agents/
│   ├── base.py                       # prompt, history, LangGraph, run/stream/respond
│   ├── manager.py                    # đăng ký và tra cứu theo agent_id
│   └── default/
│       ├── agent.py                  # agent mặc định, chỉ cấu hình base
│       └── prompt.md
├── controller/agents/agent_controller.py
├── services/llm_client.py             # interface client, chưa gọi SDK thật
├── types/schemas.py                   # ChatRequest, AgentContext, ChatResponse
└── utils/prompt.py                    # đọc prompt Markdown
```

Controller chuyển `ChatRequest` thành `AgentContext`, chọn agent bằng
`AgentManager` rồi gọi `respond_text()`. Không stream: `BaseAgent.run()` dựng
messages và chạy LangGraph `llm → END`, trả `ChatResponse` nội bộ; controller
trả nội dung `text/plain`. `respond()` cũng có sẵn cho
tầng gọi cần `ChatResponse` thay vì plain text.

Stream: `BaseAgent.stream()` gọi `LLMClient.astream()` và phát SSE `delta`, sau
đó `done` với toàn bộ nội dung. Luồng stream gọi client trực tiếp.
Nếu sau này thêm node vào graph, cần mở rộng cả đường
stream tương ứng. Đây chưa phải vòng lặp điều tra hoặc tool calling.

Prompt được đọc từ `prompt.md` của agent, có fallback khi file thiếu hoặc rỗng.
Messages gồm system prompt, hướng dẫn bổ sung `systemPrompt` nếu có, history
user/assistant và message mới. `skillId` và metadata đi trong context để agent
con dùng sau này; agent mặc định chưa có skill riêng. `conversation_id` là mã
đối chiếu, chưa lưu hội thoại; caller phải gửi lại history ở mỗi request.

## Đặc điểm nền tảng

- Dùng `uv`, Python 3.12, `pyproject.toml` và `uv.lock` cho toàn bộ repository.
- Client được truyền vào `create_app()` và agent, manager thuộc từng app;
  không dùng singleton có thể trộn cấu hình giữa các ứng dụng/test.
- Agent ID không tồn tại trả `404`, không tự chạy agent mặc định thay thế.
- Chưa có LLM thật: trả `503`, không giả lập câu trả lời trong môi trường chạy.
- Timeout 30 giây cho toàn bộ một lần run hoặc stream. Run lỗi timeout trả
  `504`, lỗi provider/đầu ra trả `502`. Nếu stream đã bắt đầu, lỗi thành SSE
  `error` (`llm_timeout` hoặc `llm_error`), không phát `done` thành công.
- Lỗi không đưa nguyên văn exception vào response. Hủy task truyền xuống
  client và đóng iterator của provider khi stream kết thúc sớm.
- Chưa nhận `funcCall`/`sessionConfig`, chưa gọi HTTP tool từ request. History
  chỉ nhận user/assistant. Field chưa hỗ trợ bị từ chối bằng `422`.

Đây là API nền tảng để chạy local. Phần xác thực và phân quyền sẽ bổ sung cùng
API nghiệp vụ. `systemPrompt` là hợp đồng dành cho caller tin cậy;
cần kiểm soát quyền này khi xây API nghiệp vụ công khai.

## Chạy và kiểm tra

```bash
uv sync --locked
uv run uvicorn app.main:app --reload
uv run python -m unittest discover -s tests -v
```

Nếu workspace chưa có `uv` trên PATH, thay `uv` bằng `.\.tools\bin\uv.exe`
trong PowerShell. Máy khác cần cài uv; `.tools/` không commit.

| Method | Path | Kết quả |
|---|---|---|
| GET | `/health` | trạng thái service |
| GET | `/api/v1/agents` | `{"agents": ["default"]}` |
| GET | `/api/v1/agents/ids` | `{"agent_ids": ["default"]}` |
| POST | `/api/v1/agents/run` | text hoặc SSE khi đã gắn LLM client |
| GET | `/docs` | Swagger UI |

Ví dụ body cho `/api/v1/agents/run`:

```json
{
  "agent_id": "default",
  "conversation_id": "conv-001",
  "message": "Giới thiệu dự án Thiên La",
  "history": [],
  "streamResponse": false,
  "metadata": {}
}
```

Chấp nhận cả tên field Python (`skill_id`, `system_prompt`, `stream_response`)
và alias (`skillId`, `systemPrompt`, `streamResponse`).

## Mở rộng sau này

1. Triển khai `LLMClient` trong services với `ensure_ready()`, async
   `ainvoke(messages) -> str` và `astream(messages) -> AsyncIterator[str]`.
   Adapter chịu trách nhiệm model, credentials, SDK và đóng kết nối provider.
   Truyền instance vào `create_app(llm_client=client)` tại entrypoint của bạn.
2. Tạo `agents/<tên>/agent.py` kế thừa `BaseAgent`, khai báo `agent_id`, `name`,
   `prompt_file`, `fallback_system_prompt` như `DefaultAgent`. Override
   `resolve_system_prompt(context)` nếu có nhiều skill.
3. Đăng ký agent bằng `AgentManager.register()` trong bước khởi tạo app.
4. Override `_get_graph()` khi cần workflow nhiều node. Tool calling, kiểm tra
   bằng chứng, giới hạn lượt điều tra sẽ xây cùng agent nghiệp vụ.

Các test dùng fake LLM chỉ trong `tests/`; kiểm tra workflow, prompt/history,
concurrency, SSE, timeout, cancellation, registry và HTTP controller mà không
gọi dịch vụ ngoài.

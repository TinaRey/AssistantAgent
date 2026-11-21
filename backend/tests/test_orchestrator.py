import asyncio

from pydantic import BaseModel

from app.integrations.llm import AssistantTurn
from app.tools.base import ToolSpec
from tests.conftest import FakeLLM, call, user


async def test_plain_answer_without_tools(make_runtime) -> None:
    orch, *_ = make_runtime(FakeLLM([AssistantTurn(content="Bonjour")]))
    res = await orch.run(user("salut"))
    assert res.reply == "Bonjour" and res.tool_calls == []


async def test_tool_call_then_answer_is_traced(make_runtime) -> None:
    llm = FakeLLM([call("retrieve_knowledge", '{"query": "brand"}'), AssistantTurn(content="done")])
    orch, _, tracer, _ = make_runtime(llm)
    res = await orch.run(user("x"))
    assert res.reply == "done"
    assert [(t.tool, t.status) for t in res.tool_calls] == [("retrieve_knowledge", "ok")]
    assert tracer.recent()[0].duration_ms >= 0


async def test_iteration_cap_stops_infinite_loop(make_runtime) -> None:
    llm = FakeLLM()  # endlessly asks for the same tool
    orch, *_ = make_runtime(llm, max_iter=3)
    res = await orch.run(user("x"))
    assert res.iteration_limit_reached and llm.chat_calls == 3 and len(res.tool_calls) == 3


async def test_invalid_and_unknown_tools_are_reported_to_model_not_raised(make_runtime) -> None:
    llm = FakeLLM(
        [
            call("retrieve_knowledge", '{"top_k": 99}', "a"),
            call("nope", "{}", "b"),
            AssistantTurn(content="ok"),
        ]
    )
    orch, *_ = make_runtime(llm)
    res = await orch.run(user("x"))
    assert [t.status for t in res.tool_calls] == ["invalid_input", "unknown_tool"]


class _In(BaseModel):
    n: int = 1


async def _slow(inp, ctx):  # type: ignore[no-untyped-def]
    await asyncio.sleep(1)
    return inp


async def _boom(inp, ctx):  # type: ignore[no-untyped-def]
    raise RuntimeError("secret detail")


async def test_timeout_and_unexpected_errors_are_contained(make_runtime) -> None:
    registry = {
        "slow": ToolSpec("slow", "d", _In, _slow, timeout_s=0.05),
        "boom": ToolSpec("boom", "d", _In, _boom),
    }
    llm = FakeLLM([call("slow", "{}", "a"), call("boom", "{}", "b"), AssistantTurn(content="ok")])
    orch, *_ = make_runtime(llm, registry=registry)
    res = await orch.run(user("x"))
    assert [t.status for t in res.tool_calls] == ["timeout", "error"]
    assert "secret detail" not in (res.tool_calls[1].error or "")


async def _send(inp, ctx):  # type: ignore[no-untyped-def]
    _send.count += 1  # type: ignore[attr-defined]
    return inp


_send.count = 0  # type: ignore[attr-defined]


async def test_external_action_requires_human_approval(make_runtime) -> None:
    registry = {"send": ToolSpec("send", "d", _In, _send, requires_approval=True)}
    llm = FakeLLM([call("send", '{"n": 2}'), AssistantTurn(content="waiting for you")])
    orch, runner, *_ = make_runtime(llm, registry=registry)
    res = await orch.run(user("send it"))
    assert _send.count == 0  # type: ignore[attr-defined]  # NOT executed by the model loop
    assert res.tool_calls[0].status == "pending_approval"
    action = res.pending_actions[0]

    done = await runner.approve(action.id)
    assert done.status == "approved" and _send.count == 1  # type: ignore[attr-defined]
    await runner.approve(action.id)  # second approval must not re-run
    assert _send.count == 1  # type: ignore[attr-defined]


async def test_rejected_action_never_runs(make_runtime) -> None:
    registry = {"send": ToolSpec("send", "d", _In, _send, requires_approval=True)}
    before = _send.count  # type: ignore[attr-defined]
    orch, runner, *_ = make_runtime(
        FakeLLM([call("send", "{}"), AssistantTurn(content="k")]), registry=registry
    )
    res = await orch.run(user("x"))
    runner.reject(res.pending_actions[0].id)
    await runner.approve(res.pending_actions[0].id)
    assert _send.count == before  # type: ignore[attr-defined]


async def test_card_results_carry_a_do_not_repeat_note_for_the_model(make_runtime) -> None:  # type: ignore[no-untyped-def]
    from app.schemas.tools import LinkedInPost, LinkedInPosts

    seen: list[list[dict]] = []

    class Spy(FakeLLM):
        async def chat(self, messages, tools):  # type: ignore[no-untyped-def]
            seen.append(list(messages))
            return await super().chat(messages, tools)

    llm = Spy(
        [call("generate_linkedin_post", '{"topic": "t"}'), AssistantTurn(content="ok")],
        structured=[LinkedInPosts(posts=[LinkedInPost(text="p", hashtags=["a"])])],
    )
    orch, *_ = make_runtime(llm)
    await orch.run(user("x"))
    tool_msg = next(m for m in seen[-1] if m["role"] == "tool")
    assert "DÉJÀ affiché" in tool_msg["content"] and '"posts"' in tool_msg["content"]
    # a tool without a UI card is passed through untouched
    llm2 = Spy([call("retrieve_knowledge", '{"query": "b"}'), AssistantTurn(content="ok")])
    seen.clear()
    orch2, *_ = make_runtime(llm2)
    await orch2.run(user("x"))
    assert "DÉJÀ" not in next(m for m in seen[-1] if m["role"] == "tool")["content"]

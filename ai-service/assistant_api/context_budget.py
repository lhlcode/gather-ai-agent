import json

from langchain_core.messages.utils import count_tokens_approximately


# 应用自定预算，不是模型真实上下文上限。
APP_CONTEXT_BUDGET = 8000
OUTPUT_RESERVE = 1600
SAFETY_MARGIN = 800
INPUT_BUDGET = APP_CONTEXT_BUDGET - OUTPUT_RESERVE - SAFETY_MARGIN

MAX_HISTORY_BUDGET = 1800
MAX_SUMMARY_BUDGET = 900
HISTORY_FETCH_LIMIT = 40
MAX_RESOLVED_QUESTION_CHARS = 2000


class ContextBudgetExceeded(Exception):
    pass


def build_json_messages(schema, instruction, payload):
    schema_text = json.dumps(
        schema.model_json_schema(),
        ensure_ascii=False,
    )
    return [
        {
            "role": "system",
            "content": (
                instruction
                + "\n只返回 JSON，遵循以下 JSON Schema：\n"
                + schema_text
            ),
        },
        {
            "role": "user",
            "content": json.dumps(payload, ensure_ascii=False),
        },
    ]


def estimate_messages(messages):
    # 中文场景采用较保守的字符比例，仍然只是估算。
    return count_tokens_approximately(
        messages,
        chars_per_token=1.0,
    )


def require_input_budget(messages):
    estimated = estimate_messages(messages)
    if estimated > INPUT_BUDGET:
        raise ContextBudgetExceeded(
            f"输入估算 {estimated} 超过应用预算 {INPUT_BUDGET}。"
        )
    return estimated


def estimate_history(history):
    if not history:
        return 0
    return estimate_messages([
        {
            "role": "user",
            "content": json.dumps(history, ensure_ascii=False),
        }
    ])


def project_turn(turn):
    response = turn["response"]
    return {
        "turn_id": turn["turn_id"],
        "user_message": turn["user_message"],
        "resolved_question": response.get("resolved_question"),
        "assistant_reply": (
            response["answer"]
            if response["status"] in {
                "answered", "clarify", "partial", "unknown"
            }
            else ""
        ),
        "status": response["status"],
    }


def select_history(
    turns,
    current_message,
    resolver_schema,
    resolver_instruction,
    intent_schema,
    intent_instruction,
    *,
    summary_items=None,
):
    def make_context(selected, summary=()):
        return {
            "recent_history": selected,
            "latest_history_missing": bool(turns) and not selected,
            "history_truncated": len(selected) < len(turns),
            "summary_quotes": list(summary) if selected else [],
        }

    def input_estimates(selected, summary=()):
        payload = {
            **make_context(selected, summary),
            "current_user_message": current_message,
        }

        resolver_messages = build_json_messages(
            resolver_schema,
            resolver_instruction,
            payload,
        )

        # 为补全后的候选问题预留空间，实际请求还会再检查。
        intent_messages = build_json_messages(
            intent_schema,
            intent_instruction,
            {
                **payload,
                "candidate_question": (
                    "问" * MAX_RESOLVED_QUESTION_CHARS
                ),
            },
        )

        return (
            estimate_messages(resolver_messages),
            estimate_messages(intent_messages),
        )

    base_estimates = input_estimates([])
    if max(base_estimates) > INPUT_BUDGET:
        raise ContextBudgetExceeded("当前问题和固定提示已超过应用预算。")

    selected = []
    for turn in reversed(turns):
        candidate = [project_turn(turn), *selected]
        if (
            estimate_history(candidate) > MAX_HISTORY_BUDGET
            or max(input_estimates(candidate)) > INPUT_BUDGET
        ):
            # 不跳过新消息去拼接更旧的话题。
            break
        selected = candidate

    selected_summary = []
    if selected:
        boundary = selected[0]["turn_id"]
        for item in reversed(summary_items or []):
            if item["source_turn"] >= boundary:
                continue
            candidate = [item, *selected_summary]
            if (
                estimate_history(candidate) > MAX_SUMMARY_BUDGET
                or max(input_estimates(selected, candidate)) > INPUT_BUDGET
            ):
                break
            selected_summary = candidate

    resolver_estimate, intent_estimate = input_estimates(selected, selected_summary)
    stats = {
        "candidate_turns": len(turns),
        "selected_turns": len(selected),
        "dropped_turns": len(turns) - len(selected),
        "selected_turn_ids": [item["turn_id"] for item in selected],
        "history_estimate": estimate_history(selected),
        "summary_estimate": estimate_history(selected_summary),
        "summary_turn_ids": [item["source_turn"] for item in selected_summary],
        "resolver_input_estimate": resolver_estimate,
        "intent_reserved_input_estimate": intent_estimate,
        "input_budget": INPUT_BUDGET,
        "estimator": "approx_chars_per_token_1",
    }
    return make_context(selected, selected_summary), stats

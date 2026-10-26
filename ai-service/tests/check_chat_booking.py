import os
os.environ["LANGSMITH_TRACING"]="false"
os.environ["LANGCHAIN_TRACING_V2"]="false"
import asyncio, json, sqlite3, sys, tempfile
from pathlib import Path
import httpx
from fastapi import FastAPI
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import assistant_api.schemas as schemas
import assistant_api.booking_commands as commands
import assistant_api.booking_operation_store as book_store_module
import assistant_api.agent_service as agent_module
import assistant_api.conversation_service as conversation_module
from assistant_api.identity_service import IdentityService
from assistant_api.conversation_store import ConversationStore
from assistant_api.conversation_routes import router
for text in ["帮我报名活动43","报名活动43","请帮我报名活动43。","重新报名活动43","重试报名活动43"]:
    assert commands.parse_booking_command(text) is not None,text
for text in ["活动43能报名吗？","不要报名活动43","他说：报名活动43","报名活动43并支付","报名活动0"]:
    assert commands.parse_booking_command(text) is None,text

calls=[]
model_payloads=[]
receipts={}
lost_reply=set()
next_id=100
async def backend(request):
    global next_id
    auth=request.headers.get("Authorization")
    if auth not in {"Bearer test-a","Bearer test-b"}: return httpx.Response(401)
    uid=7 if auth=="Bearer test-a" else 8
    if request.url.path=="/users/me":
        return httpx.Response(200,json={"userId":uid,"username":f"u{uid}","role":"USER"})
    event_id=int(request.url.path.split("/")[2])
    assert request.url.path==f"/events/{event_id}/booking-operations"
    key=request.headers["Idempotency-Key"]
    calls.append((uid,key,event_id))
    identity=(uid,key)
    replayed=identity in receipts
    if not replayed:
        receipts[identity]={"operationId":key,"orderId":next_id,"eventId":event_id,"status":"UNPAID"}
        next_id+=1
    if identity in lost_reply:
        lost_reply.remove(identity)
        raise httpx.ReadTimeout("simulated lost reply",request=request)
    return httpx.Response(200 if replayed else 201,json={**receipts[identity],"replayed":replayed})

class Business:
    descriptions=[]
    async def call(self,name,args):
        return {"source":"GET /events","events":[]}

async def fake_ask(schema,instruction,payload):
    model_payloads.append(json.dumps(payload,ensure_ascii=False))
    if schema is conversation_module.QuestionResolution:
        question=payload["current_user_message"]
        candidate="报名活动43" if question=="活动43如何报名？" else question
        result={"status":"ready","standalone_question":candidate,"clarification":""}
    elif schema is conversation_module.IntentCheck:
        result={"faithful":True,"reason":"test"}
    else:
        result=(
            {"route":"list_events"}
            if payload["question"]=="列出活动"
            else {"route":"clarify","clarification":"请明确说明。"}
        )
    return schema.model_validate(result),schemas.TokenUsage(input_tokens=1,output_tokens=1,total_tokens=2)

async def main():
    with tempfile.TemporaryDirectory(prefix="chat-booking-lesson-") as folder:
        conversations=ConversationStore(Path(folder)/"conversations.sqlite3")
        booking_store=book_store_module.BookingOperationStore(Path(folder)/"operations.sqlite3")
        def service():
            agent=agent_module.AgentService(None,None,Business(),booking_store)
            agent.ask_json=fake_ask
            return conversation_module.ConversationService(agent,conversations)
        async with httpx.AsyncClient(base_url="https://backend.test",transport=httpx.MockTransport(backend)) as upstream:
            app=FastAPI()
            app.state.backend_client=upstream
            app.state.identity_service=IdentityService(upstream)
            app.state.conversation_store=conversations
            app.state.conversation_service=service()
            app.state.booking_operation_store=booking_store
            app.include_router(router)
            async with httpx.AsyncClient(base_url="https://app.test",transport=httpx.ASGITransport(app=app)) as api:
                a={"Authorization":"Bearer test-a"};b={"Authorization":"Bearer test-b"}
                async def create(headers):
                    r=await api.post("/conversations",headers=headers)
                    assert r.status_code==201,r.text
                    return r.json()["thread_id"]
                ta,tb=await asyncio.gather(create(a),create(b))
                async def chat(text,key=None,headers=None,thread=None):
                    body={"thread_id":thread or ta,"message":text}
                    if key is not None:body["operation_id"]=key
                    return await api.post("/chat",headers=headers or a,json=body)
                missing=await chat("帮我报名活动43")
                assert missing.status_code==200 and missing.json()["status"]=="clarify" and calls==[]
                no_prior=await chat("重试报名活动43","f"*32)
                assert no_prior.json()["status"]=="clarify" and calls==[]

                key="a"*32
                first=await chat("帮我报名活动43",key)
                assert first.status_code==200,first.text
                assert first.json()["tool_results"][0]["status"]=="created"
                assert first.json()["model_calls"]==0 and first.json()["usage"] is None
                first_id=first.json()["tool_results"][0]["order_id"]
                replay=await chat("重试报名活动43",key)
                assert replay.json()["tool_results"][0]["status"]=="replayed"
                assert replay.json()["tool_results"][0]["order_id"]==first_id and len(receipts)==1

                receipts[(7,key)]["status"]="CANCELLED"
                cancelled=await chat("重试报名活动43",key)
                assert cancelled.json()["tool_results"][0]["order_status"]=="CANCELLED" and len(receipts)==1
                new=await chat("重新报名活动43","b"*32)
                assert new.json()["tool_results"][0]["status"]=="created" and len(receipts)==2
                count=len(calls)
                changed=await chat("重试报名活动44",key)
                assert changed.status_code==409 and len(calls)==count
                denied=await chat("报名活动43",key,headers=b,thread=ta)
                assert denied.status_code==404 and len(calls)==count
                foreign_retry=await chat("重试报名活动43",key,headers=b,thread=tb)
                assert foreign_retry.json()["status"]=="clarify" and len(calls)==count

                for question in ["活动43如何报名？","不要报名活动43","他说：报名活动43"]:
                    r=await chat(question,"c"*32)
                    assert r.status_code==200 and len(calls)==count,r.text
                regular=await chat("列出活动")
                assert regular.status_code==200 and regular.json()["source"]=="GET /events"
                assert regular.json()["model_calls"]==3

                lost_key="d"*32
                lost_reply.add((7,lost_key))
                lost=await chat("报名活动43",lost_key)
                assert lost.json()["status"]=="unknown"
                lost_id=receipts[(7,lost_key)]["orderId"]
                app.state.conversation_service=service()
                recovered=await chat("重试报名活动43",lost_key)
                assert recovered.json()["tool_results"][0]["order_id"]==lost_id
                assert recovered.json()["tool_results"][0]["status"]=="replayed"

                original_append=conversations.append_turn
                def fail_append(*args,**kwargs):raise sqlite3.OperationalError("simulated history failure")
                conversations.append_turn=fail_append
                crash_key="e"*32
                crashed=await chat("报名活动43",crash_key)
                assert crashed.status_code==503
                crash_id=receipts[(7,crash_key)]["orderId"]
                conversations.append_turn=original_append
                retried=await chat("报名活动43",crash_key)
                assert retried.json()["tool_results"][0]["order_id"]==crash_id
                assert retried.json()["tool_results"][0]["status"]=="replayed"
                history=conversations.get_history(ta,7,100)
                assert any(t["response"]["status"]=="unknown" for t in history["turns"])
                assert "test-a" not in json.dumps(history,ensure_ascii=False)
                assert all("test-a" not in p for p in model_payloads)
        print("PASS: actual chat/real LangGraph integration with temporary DBs and fake Java/model; explicit commands, 0 model calls for writes, no write from questions/negation/quotes or model rewrite, stable retry, cancelled replay, new key, target binding, auth/thread ownership, missing-key and unregistered retry rejection, lost reply recovery, history-save failure recovery, ordinary read routing. Real backend/model not called.")
if __name__ == "__main__":
    asyncio.run(main())

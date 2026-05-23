import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database import get_db
from models import User, AgentMemory, Conversation, ConversationMessage
from schemas.agent import ChatRequest
from dependencies import get_current_user
from agents.orchestrator import run_orchestrator
from agents.memory import delete_memory

router = APIRouter(prefix="/api/agent", tags=["agent"])


@router.post("/chat")
async def chat(
    body: ChatRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """SSE streaming endpoint for conversational agent."""

    async def event_stream():
        try:
            # Resolve or create conversation
            conv_id = body.conversation_id
            if not conv_id:
                conv = Conversation(user_id=user.id)
                db.add(conv)
                await db.flush()
                conv_id = conv.id
            else:
                conv_result = await db.execute(
                    select(Conversation).where(Conversation.id == conv_id, Conversation.user_id == user.id)
                )
                conv = conv_result.scalar_one_or_none()
                if not conv:
                    yield f"data: {json.dumps({'type': 'error', 'data': 'Conversation not found'})}\n\n"
                    return

            # Save user message
            user_msg = ConversationMessage(
                conversation_id=conv.id,
                role="user",
                content=body.message,
            )
            db.add(user_msg)
            await db.commit()

            # Signal thinking
            yield f"data: {json.dumps({'type': 'token', 'data': ''})}\n\n"

            # Run orchestrator pipeline
            state = await run_orchestrator(
                user_id=str(user.id),
                query=body.message,
                db=db,
                conversation_id=str(conv.id),
            )

            response = state.get("final_response", "I'm unable to process that request right now.")

            # Stream response tokens
            for char in response:
                yield f"data: {json.dumps({'type': 'token', 'data': char})}\n\n"

            # Send reasoning trace
            yield f"data: {json.dumps({'type': 'reasoning_trace', 'data': state.get('reasoning_trace', [])})}\n\n"

            # Save assistant message
            assistant_msg = ConversationMessage(
                conversation_id=conv.id,
                role="assistant",
                content=response,
                reasoning_trace=state.get("reasoning_trace", []),
            )
            db.add(assistant_msg)

            # Update conversation title if first message
            if not conv.title:
                conv.title = body.message[:50]

            await db.commit()

            yield f"data: {json.dumps({'type': 'done', 'data': {'conversation_id': str(conv.id)}})}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'data': str(e)})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/conversations")
async def list_conversations(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Conversation)
        .where(Conversation.user_id == user.id)
        .order_by(Conversation.updated_at.desc())
        .limit(50)
    )
    convs = result.scalars().all()
    return [{"id": str(c.id), "title": c.title, "created_at": c.created_at} for c in convs]


@router.get("/conversations/{conv_id}")
async def get_conversation(
    conv_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Conversation).where(Conversation.id == conv_id, Conversation.user_id == user.id)
    )
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    msgs_result = await db.execute(
        select(ConversationMessage)
        .where(ConversationMessage.conversation_id == conv.id)
        .order_by(ConversationMessage.created_at)
    )
    msgs = msgs_result.scalars().all()
    return [
        {
            "role": m.role,
            "content": m.content,
            "reasoning_trace": m.reasoning_trace,
            "created_at": m.created_at,
        }
        for m in msgs
    ]


@router.get("/memories")
async def list_memories(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(AgentMemory)
        .where(AgentMemory.user_id == user.id)
        .order_by(AgentMemory.created_at.desc())
    )
    memories = result.scalars().all()
    return [
        {
            "id": str(m.id),
            "memory_type": m.memory_type,
            "content": m.content,
            "confidence": float(m.confidence),
            "times_referenced": m.times_referenced,
            "created_at": m.created_at,
        }
        for m in memories
    ]


@router.delete("/memories/{memory_id}")
async def remove_memory(
    memory_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    deleted = await delete_memory(str(memory_id), str(user.id), db)
    if not deleted:
        raise HTTPException(status_code=404, detail="Memory not found")
    return {"success": True}

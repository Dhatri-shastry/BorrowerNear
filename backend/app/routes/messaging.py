import json

from fastapi import APIRouter, Depends, HTTPException, Query
from redis.exceptions import RedisError

from app.db import cursor
from app.dependencies import require_member
from app.redis_store import (allow_message, append_message, conversation_metadata,
    create_or_get_conversation, is_conversation_participant, list_user_conversations, read_messages)
from app.schemas.models import ConversationCreate, MessageCreate

router=APIRouter(prefix="/conversations",tags=["Messaging"])


def _authorized_conversation(conversation_id:str,user_id:int):
    if not is_conversation_participant(conversation_id,user_id):
        raise HTTPException(404,"Conversation not found")
    metadata=conversation_metadata(conversation_id)
    if not metadata:
        raise HTTPException(404,"Conversation not found")
    return metadata


@router.post("",status_code=201)
def create_conversation(data:ConversationCreate,user=Depends(require_member)):
    with cursor() as (_,cur):
        cur.execute("""SELECT r.request_id,r.item_id,r.borrower_id,i.owner_id,i.item_name
          FROM borrow_requests r JOIN items i ON i.item_id=r.item_id WHERE r.request_id=%s""",(data.request_id,))
        request=cur.fetchone()
    if not request: raise HTTPException(404,"Borrow request not found")
    user_id=user["user_id"]
    participants=sorted([request["borrower_id"],request["owner_id"]])
    if user_id not in participants: raise HTTPException(403,"Only request participants can create this conversation")
    try:
        conversation_id=create_or_get_conversation(request["request_id"],request["item_id"],
                                                  request["item_name"],participants)
        metadata=conversation_metadata(conversation_id)
        return {"conversation_id":conversation_id,"request_id":request["request_id"],
                "item_id":request["item_id"],"item_name":request["item_name"],
                "participant_ids":participants,"created_at":metadata.get("created_at")}
    except RedisError as exc:
        raise HTTPException(503,"Messaging service unavailable") from exc


@router.get("")
def list_conversations(user=Depends(require_member),limit:int=Query(30,ge=1,le=100),offset:int=Query(0,ge=0)):
    try:
        docs=list_user_conversations(user["user_id"],limit,offset)
        return [{"conversation_id":d["conversation_id"],"request_id":int(d["request_id"]),
                 "item_id":int(d["item_id"]),"item_name":d["item_name"],
                 "participant_ids":json.loads(d["participant_ids"]),
                 "last_message_at":d["last_message_at"]} for d in docs]
    except RedisError as exc:
        raise HTTPException(503,"Messaging service unavailable") from exc


@router.get("/{conversation_id}/messages")
def list_messages(conversation_id:str,user=Depends(require_member),limit:int=Query(50,ge=1,le=100),offset:int=Query(0,ge=0)):
    try:
        _authorized_conversation(conversation_id,user["user_id"])
        return read_messages(conversation_id,limit,offset)
    except RedisError as exc:
        raise HTTPException(503,"Messaging service unavailable") from exc


@router.post("/{conversation_id}/messages",status_code=201)
def send_message(conversation_id:str,data:MessageCreate,user=Depends(require_member)):
    try:
        _authorized_conversation(conversation_id,user["user_id"])
        if not allow_message(user["user_id"]):
            raise HTTPException(429,"Message rate limit exceeded; try again shortly")
        message=append_message(conversation_id,user["user_id"],data.text)
        return {"conversation_id":conversation_id,**message}
    except RedisError as exc:
        raise HTTPException(503,"Messaging service unavailable") from exc

"""Redis key layout and operations for conversations, caching and message limits.

Permanent Redis data:
  conversation:{id}                 hash with request/item/participant metadata
  conversation:{id}:participants   set of MySQL user IDs
  conversation:{id}:messages       append-only Redis Stream
  request-conversation:{request}   unique request-to-conversation string
  user-conversations:{user}         sorted set ordered by latest activity

Ephemeral Redis data:
  cache:items:{digest}              JSON item-list cache with short TTL
  rate:messages:{user}:{minute}     fixed-window message counter with TTL
"""
import hashlib
import json
import logging
from typing import Any
import time
from datetime import datetime, timezone
from uuid import uuid4

import redis
from redis.exceptions import WatchError

from app.config import get_settings

logger=logging.getLogger("borrownear.redis")
_client=None


def get_redis():
    global _client
    if _client is None:
        _client=redis.Redis.from_url(
            get_settings().redis_url,decode_responses=True,
            socket_connect_timeout=2,socket_timeout=2,health_check_interval=30,
        )
    return _client


def check_redis():
    return bool(get_redis().ping())


def close_redis():
    global _client
    if _client is not None:
        _client.close()
    _client=None


def create_or_get_conversation(request_id:int,item_id:int,item_name:str,participant_ids:list[int]):
    client=get_redis()
    mapping_key=f"request-conversation:{request_id}"
    participant_ids=sorted(set(participant_ids))
    now=datetime.now(timezone.utc).isoformat(timespec="seconds")
    score=time.time()
    for _ in range(5):
        conversation_id=uuid4().hex
        conv_key=f"conversation:{conversation_id}"
        participant_key=f"{conv_key}:participants"
        inbox_keys=[f"user-conversations:{user_id}" for user_id in participant_ids]
        try:
            with client.pipeline() as pipe:
                pipe.watch(mapping_key)
                existing=pipe.get(mapping_key)
                if existing:
                    pipe.unwatch()
                    return existing
                pipe.multi()
                pipe.set(mapping_key,conversation_id)
                pipe.hset(conv_key,mapping={"conversation_id":conversation_id,"request_id":request_id,
                  "item_id":item_id,"item_name":item_name,"participant_ids":json.dumps(participant_ids),
                  "created_at":now,"last_message_at":now})
                pipe.sadd(participant_key,*participant_ids)
                for inbox_key in inbox_keys:
                    pipe.zadd(inbox_key,{conversation_id:score})
                pipe.execute()
                return conversation_id
        except WatchError:
            continue
    raise RuntimeError("Unable to create conversation after concurrent updates")


def conversation_metadata(conversation_id:str):
    return get_redis().hgetall(f"conversation:{conversation_id}")


def is_conversation_participant(conversation_id:str,user_id:int)->bool:
    return bool(get_redis().sismember(f"conversation:{conversation_id}:participants",user_id))


def list_user_conversations(user_id:int,limit:int,offset:int):
    client=get_redis()
    ids=client.zrevrange(f"user-conversations:{user_id}",offset,offset+limit-1)
    if not ids:
        return []
    pipe=client.pipeline(transaction=False)
    for conversation_id in ids:
        pipe.hgetall(f"conversation:{conversation_id}")
    return [data for data in pipe.execute() if data]


def append_message(conversation_id:str,user_id:int,text:str):
    client=get_redis()
    now=datetime.now(timezone.utc).isoformat(timespec="seconds")
    stream_key=f"conversation:{conversation_id}:messages"
    participants=client.smembers(f"conversation:{conversation_id}:participants")
    score=time.time()
    with client.pipeline(transaction=True) as pipe:
        pipe.xadd(stream_key,{"sender_id":user_id,"text":text,"created_at":now},
                  maxlen=10000,approximate=True)
        pipe.hset(f"conversation:{conversation_id}","last_message_at",now)
        for participant_id in participants:
            pipe.zadd(f"user-conversations:{participant_id}",{conversation_id:score})
        results=pipe.execute()
    message_id=results[0]
    return {"message_id":message_id,"sender_id":user_id,"text":text,"created_at":now}


def read_messages(conversation_id:str,limit:int,offset:int):
    stream=f"conversation:{conversation_id}:messages"
    entries=get_redis().xrevrange(stream,max="+",min="-",count=offset+limit)
    selected=entries[offset:offset+limit]
    selected.reverse()
    return [{"message_id":message_id,"sender_id":int(fields["sender_id"]),
             "text":fields["text"],"created_at":fields["created_at"]}
            for message_id,fields in selected]


def allow_message(user_id:int,per_minute:int=30)->bool:
    client=get_redis()
    minute=int(time.time()//60)
    key=f"rate:messages:{user_id}:{minute}"
    count=client.incr(key)
    if count==1:
        client.expire(key,65)
    return count<=per_minute


def item_cache_key(parts:dict)->str:
    canonical=json.dumps(parts,sort_keys=True,separators=(",",":"),default=str)
    return "cache:items:"+hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def get_cached_items(key:str):
    payload=get_redis().get(key)
    if payload is None:
        return None
    try:
        return json.loads(payload)
    except (json.JSONDecodeError,TypeError):
        get_redis().delete(key)
        return None


def set_cached_items(key:str,value:Any,ttl:int|None=None):
    payload=json.dumps(value,separators=(",",":"),default=str)
    get_redis().setex(key,ttl or get_settings().cache_ttl_seconds,payload)


def invalidate_item_caches():
    client=get_redis()
    keys=list(client.scan_iter(match="cache:items:*",count=100))
    if keys:
        client.delete(*keys)


def invalidate_item_caches_safely():
    try:
        invalidate_item_caches()
    except redis.exceptions.RedisError as exc:
        logger.warning("Redis item-cache invalidation skipped (%s)",type(exc).__name__)

import json

import fakeredis
import app.redis_store as store


def test_redis_conversation_stream_cache_and_rate_limit(monkeypatch):
    client=fakeredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(store,"get_redis",lambda:client)

    first=store.create_or_get_conversation(71,12,"Shared drill",[9,3])
    second=store.create_or_get_conversation(71,12,"Shared drill",[3,9])
    assert first==second
    assert store.is_conversation_participant(first,3)
    assert not store.is_conversation_participant(first,44)
    inbox=store.list_user_conversations(9,10,0)
    assert len(inbox)==1 and inbox[0]["item_name"]=="Shared drill"

    one=store.append_message(first,3,"Hello there")
    two=store.append_message(first,9,"Thanks for reaching out")
    assert [m["text"] for m in store.read_messages(first,1,0)]==["Thanks for reaching out"]
    assert [m["text"] for m in store.read_messages(first,10,0)]==["Hello there","Thanks for reaching out"]
    assert one["message_id"] and two["message_id"]

    assert all(store.allow_message(3) for _ in range(30))
    assert not store.allow_message(3)

    key=store.item_cache_key({"category_id":2,"offset":0})
    payload={"items":[{"item_id":12}],"limit":5,"offset":0}
    store.set_cached_items(key,payload,ttl=30)
    assert store.get_cached_items(key)==payload
    assert 0<client.ttl(key)<=30
    store.invalidate_item_caches()
    assert store.get_cached_items(key) is None

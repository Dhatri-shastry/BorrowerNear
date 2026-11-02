"use client";
import Link from "next/link";
import {useEffect,useState} from "react";
import {api,Item} from "@/lib/api";
import {ItemCard} from "@/components/ItemCard";

export default function Home(){const [items,setItems]=useState<Item[]>([]);const [error,setError]=useState("");
 useEffect(()=>{api<{items:Item[]}>('/items?status=AVAILABLE&limit=3').then(x=>setItems(x.items)).catch(e=>setError(e.message));},[]);
 return <><section className="hero"><div className="hero-copy"><span className="eyebrow">A better way to borrow</span><h1>Good things are<br/>closer than you think.</h1><p>Borrow the things you need from people in your neighbourhood. Save money, share useful things, and get to know the community around you.</p><div className="hero-actions"><Link className="button" href="/browse">Explore nearby items</Link><Link className="button-secondary" href="/register">List something to share</Link></div></div></section>
 <section className="container"><div className="section-head"><div><span className="eyebrow">Ready when you are</span><h2>Available around you</h2></div><Link className="text-button" href="/browse">Browse all →</Link></div>{error?<div className="empty">{error}</div>:items.length?<div className="item-grid">{items.map(i=><ItemCard key={i.item_id} item={i}/>)}</div>:<div className="empty">{process.env.NEXT_PUBLIC_API_URL?"Loading nearby items…":"Set NEXT_PUBLIC_API_URL to connect the API."}</div>}</section>
 <section className="how"><div className="container"><div className="section-head"><div><span className="eyebrow">Simple by design</span><h2>Borrowing, made neighbourly</h2></div></div><div className="steps">{[["01","Find what you need","Search useful things listed by people nearby."],["02","Ask to borrow","Choose your dates and send a request to the owner."],["03","Share and return","Agree on handover, enjoy the item, then return it." ]].map(x=><article className="step" key={x[0]}><b>{x[0]}</b><h3>{x[1]}</h3><p>{x[2]}</p></article>)}</div></div></section>
 <section className="container"><div className="section-head"><div><span className="eyebrow">Thoughtful sharing</span><h2>Built around trust</h2><p>Real accounts, clear borrowing records, and reviews after a completed return.</p></div><Link href="/dashboard" className="button-secondary">Your BorrowNear space</Link></div></section></>}

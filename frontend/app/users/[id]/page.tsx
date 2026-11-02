"use client";
import {useEffect,useState} from "react";
import {useParams} from "next/navigation";
import {api,Item} from "@/lib/api";
import {ItemCard} from "@/components/ItemCard";
type Profile={user_id:number;name:string;locality:string;city:string;trust_score:number};
export default function OwnerPage(){const {id}=useParams<{id:string}>();const [profile,setProfile]=useState<Profile|null>(null),[items,setItems]=useState<Item[]>([]),[error,setError]=useState("");useEffect(()=>{api<Profile>(`/users/${id}`).then(setProfile).catch(e=>setError(e.message));api<{items:Item[]}>(`/users/${id}/items`).then(x=>setItems(x.items)).catch(e=>setError(e.message))},[id]);return <div className="container">{error&&<div className="notice">{error}</div>}{profile&&<><span className="eyebrow">A neighbour sharing nearby</span><h1 className="page-title">{profile.name}</h1><p className="muted">{profile.locality}, {profile.city} · Trust score {Number(profile.trust_score).toFixed(2)} / 5</p><h2 style={{fontFamily:'Georgia,serif',marginTop:36}}>Items shared</h2><div className="item-grid">{items.map(i=><ItemCard item={i} key={i.item_id}/>)}</div></>}</div>}

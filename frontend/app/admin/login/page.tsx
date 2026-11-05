"use client";
import Link from "next/link";
import {FormEvent,useState} from "react";
import {useRouter} from "next/navigation";
import {api,saveSession} from "@/lib/api";

export default function AdminLogin(){
 const router=useRouter();
 const [email,setEmail]=useState("");
 const [password,setPassword]=useState("");
 const [error,setError]=useState("");
 const [busy,setBusy]=useState(false);
 async function submit(event:FormEvent){
  event.preventDefault();setBusy(true);setError("");
  try{
   const data=await api<{access_token:string;user:{role:string}}>("/auth/admin/login",{method:"POST",body:JSON.stringify({email,password})});
   saveSession(data.access_token,data.user);router.push("/admin");
  }catch(e){setError((e as Error).message)}finally{setBusy(false)}
 }
 return <div className="auth-wrap"><div className="auth-card"><span className="eyebrow">BorrowNear administration</span><h1>Administrator sign in</h1><form className="form-stack" onSubmit={submit}><label className="label">Admin email<input className="input" type="email" autoComplete="username" required value={email} onChange={e=>setEmail(e.target.value)}/></label><label className="label">Admin password<input className="input" type="password" autoComplete="current-password" required value={password} onChange={e=>setPassword(e.target.value)}/></label>{error&&<div className="notice">{error}</div>}<button className="button" disabled={busy}>{busy?"Signing in…":"Sign in to admin"}</button></form><p className="muted"><Link className="text-button" href="/login">Member sign in</Link></p></div></div>
}

"use client";
import Link from "next/link";
import {useRouter} from "next/navigation";
import {useEffect,useState} from "react";
import {clearSession,token,sessionUser} from "@/lib/api";

export function Shell({children}:{children:React.ReactNode}){
 const router=useRouter();
 const [role,setRole]=useState<string|null>(null);
 useEffect(()=>{
  const syncSession=()=>setRole(token()?sessionUser()?.role??"USER":null);
  syncSession();
  window.addEventListener("borrownear-session-change",syncSession);
  window.addEventListener("storage",syncSession);
  return()=>{
   window.removeEventListener("borrownear-session-change",syncSession);
   window.removeEventListener("storage",syncSession);
  };
 },[]);
 return <>
  <header className="site-header">
   <Link className="brand" href="/">borrow<span>near</span><small>share more, buy less</small></Link>
   <nav>
    {(!role||role==="BORROWER")&&<Link href="/browse">Browse</Link>}
    {role!=="ADMIN"&&<Link href="/dashboard">Dashboard</Link>}
    {(role==="BORROWER"||role==="LENDER")&&<Link href="/messages">Messages</Link>}
    {role==="ADMIN"&&<Link href="/admin">Admin</Link>}
    {role
     ? <button className="nav-cta" type="button" onClick={()=>{clearSession();router.push("/")}}>Sign out</button>
     : <Link className="nav-cta" href="/login">Sign in</Link>}
   </nav>
  </header>
  <main>{children}</main>
  <footer><div className="footer-inner"><span>BorrowNear · Bengaluru</span><span>Neighbourhood sharing, built on trust.</span></div></footer>
 </>;
}

"use client";
import Link from "next/link";
import {useCallback,useEffect,useRef,useState,FormEvent} from "react";
import {useRouter} from "next/navigation";
import {api,ApiError,clearSession,Item,RequestRow,token,saveSession} from "@/lib/api";

type Role="USER"|"LENDER"|"BORROWER"|"ADMIN";
type User={user_id:number;name:string;email:string;role:Role;trust_score:number};
type Tx={transaction_id:number;status:string;borrow_date:string;due_date:string;item_name:string;owner_name:string;borrower_name:string};
type Location={location_id:number;locality:string;city:string};
type Category={category_id:number;category_name:string};
const emptyForm={category_id:"",item_name:"",description:"",condition:"",estimated_value:"",deposit_amount:"0"};
function describeLoadError(error:unknown){if(error instanceof ApiError)return `${error.message} (${error.endpoint})`;return (error as Error)?.message??"Request failed"}

export default function Dashboard(){
 const router=useRouter();
 const [user,setUser]=useState<User|null>(null),[items,setItems]=useState<Item[]>([]),[mine,setMine]=useState<RequestRow[]>([]),[incoming,setIncoming]=useState<RequestRow[]>([]),[history,setHistory]=useState<Tx[]>([]),[categories,setCategories]=useState<Category[]>([]),[locations,setLocations]=useState<Location[]>([]),[error,setError]=useState(""),[message,setMessage]=useState("");
 const [editId,setEditId]=useState<number|null>(null),[editName,setEditName]=useState(""),[form,setForm]=useState(emptyForm),[imageFile,setImageFile]=useState<File|null>(null),[imageRetry,setImageRetry]=useState<{itemId:number;file:File}|null>(null),[imageBusy,setImageBusy]=useState(false);
 const imageInput=useRef<HTMLInputElement>(null);

 const load=useCallback(async()=>{
  setError("");
  try{
   const profile=await api<User>("/auth/me");setUser(profile);
   if(profile.role==="ADMIN"){router.replace("/admin");return}
   if(profile.role==="USER")return;
   if(profile.role==="LENDER"){
    const results=await Promise.allSettled([
     api<{items:Item[]}>(`/users/${profile.user_id}/items?limit=50`),api<RequestRow[]>("/owner/requests"),
     api<Tx[]>("/transactions"),api<Category[]>("/categories"),api<Location[]>("/locations"),
    ]);
    if(results[0].status==="fulfilled")setItems(results[0].value.items);
    if(results[1].status==="fulfilled")setIncoming(results[1].value);
    if(results[2].status==="fulfilled")setHistory(results[2].value);
    if(results[3].status==="fulfilled")setCategories(results[3].value);
    if(results[4].status==="fulfilled")setLocations(results[4].value);
    const failed=results.find(r=>r.status==="rejected");if(failed?.status==="rejected")setError(`Some lender information could not load: ${describeLoadError(failed.reason)}`);
   }else{
    const results=await Promise.allSettled([api<RequestRow[]>("/requests"),api<Tx[]>("/transactions")]);
    if(results[0].status==="fulfilled")setMine(results[0].value);
    if(results[1].status==="fulfilled")setHistory(results[1].value);
    const failed=results.find(r=>r.status==="rejected");if(failed?.status==="rejected")setError(`Some borrower information could not load: ${describeLoadError(failed.reason)}`);
   }
  }catch(e){if(e instanceof ApiError&&e.status===401){clearSession();router.replace("/login");return}setError(describeLoadError(e))}
 },[router]);
 // eslint-disable-next-line react-hooks/set-state-in-effect
 useEffect(()=>{if(!token()){router.replace("/login");return}void load()},[load,router]);

 async function chooseRole(role:"LENDER"|"BORROWER"){
  setError("");try{const updated=await api<User>("/auth/role",{method:"POST",body:JSON.stringify({role})});const accessToken=token();if(accessToken)saveSession(accessToken,updated);setUser(updated);await load()}
  catch(e){setError(describeLoadError(e))}
 }
 async function action(path:string,method="POST",body?:unknown):Promise<boolean>{
  setError("");setMessage("");try{await api<unknown>(path,{method,body:body?JSON.stringify(body):undefined});setMessage("Saved.");await load();return true}
  catch(e){setError(describeLoadError(e));return false}
 }
 async function messageRequest(requestId:number){setError("");try{const c=await api<{conversation_id:string}>("/conversations",{method:"POST",body:JSON.stringify({request_id:requestId})});router.push(`/messages?conversation_id=${encodeURIComponent(c.conversation_id)}`)}catch(e){setError(describeLoadError(e))}}
 async function uploadItemImage(itemId:number,file:File){const body=new FormData();body.append("image",file);await api(`/items/${itemId}/image`,{method:"POST",body})}
 async function addItem(event:FormEvent){
  event.preventDefault();if(!imageFile){setError("Choose an image for this item before publishing.");return}
  setError("");setMessage("");setImageBusy(true);
  try{
   const saved=await api<Item>("/items",{method:"POST",body:JSON.stringify({...form,category_id:Number(form.category_id),estimated_value:Number(form.estimated_value),deposit_amount:Number(form.deposit_amount)})});
   setItems(current=>[saved,...current.filter(item=>item.item_id!==saved.item_id)]);
   try{await uploadItemImage(saved.item_id,imageFile)}catch(uploadError){await load();setImageRetry({itemId:saved.item_id,file:imageFile});setError(`The listing was saved, but its image upload failed: ${(uploadError as Error).message}. Retry the image upload below.`);return}
   setMessage("Your item and image were saved.");setForm(emptyForm);setImageFile(null);if(imageInput.current)imageInput.current.value="";await load();
  }catch(e){setError(describeLoadError(e))}finally{setImageBusy(false)}
 }
 async function retryImageUpload(){if(!imageRetry)return;setImageBusy(true);try{await uploadItemImage(imageRetry.itemId,imageRetry.file);setImageRetry(null);setImageFile(null);if(imageInput.current)imageInput.current.value="";setForm(emptyForm);setError("");setMessage("Item and image saved.")}catch(e){setError(`Image upload failed: ${(e as Error).message}`)}finally{setImageBusy(false)}}

 if(!user)return <div className="container">{error?<div className="notice">{error} <button className="text-button" onClick={()=>void load()}>Retry</button></div>:"Loading your BorrowNear space…"}</div>;
 if(user.role==="USER")return <div className="container"><span className="eyebrow">Account setup</span><h1 className="page-title">How would you like to use BorrowNear?</h1><p className="muted">Choose one role for this account. Existing account data and listings are preserved.</p>{error&&<div className="notice">{error}</div>}<div className="dashboard-grid"><section className="panel"><h2>I want to lend</h2><p className="muted">List items you own and manage borrowing requests from neighbours.</p><button className="button" onClick={()=>void chooseRole("LENDER")}>Choose lender</button></section><section className="panel"><h2>I want to borrow</h2><p className="muted">Browse available items and request the ones you need.</p><button className="button" onClick={()=>void chooseRole("BORROWER")}>Choose borrower</button></section></div></div>;

 const isLender=user.role==="LENDER";
 return <div className="container"><span className="eyebrow">Your BorrowNear space · {isLender?"Lender":"Borrower"}</span><h1 className="page-title">Hello, {user.name.split(" ")[0]}.</h1><p className="muted">{isLender?"Manage your listings and respond to borrowing requests.":"Browse listings, manage your requests and borrowing activity."}</p>{error&&<div className="notice">{error} {imageRetry&&<button className="text-button" disabled={imageBusy} onClick={()=>void retryImageUpload()}>{imageBusy?"Uploading…":"Retry image upload"}</button>} <button className="text-button" onClick={()=>void load()}>Retry dashboard data</button></div>}{message&&<div className="notice success">{message}</div>}<div className="toolbar"><span>Trust score · {Number(user.trust_score).toFixed(2)} / 5</span><button className="text-button" onClick={()=>{clearSession();router.push("/")}}>Sign out</button></div>
  <div className="dashboard-grid">
   {isLender&&<><section className="panel"><h2>Your listings</h2>{items.length?items.map(i=><div className="row" key={i.item_id}><div>{editId===i.item_id?<input className="input" value={editName} maxLength={150} onChange={e=>setEditName(e.target.value)}/>:<><b>{i.item_name}</b><small>{i.status} · {i.locality}</small></>}</div><div><Link className="text-button" href={`/items/${i.item_id}`}>View</Link>{editId===i.item_id?<><button className="text-button" onClick={()=>{void action(`/items/${i.item_id}`,"PATCH",{item_name:editName});setEditId(null)}}>Save</button><button className="text-button" onClick={()=>setEditId(null)}>Cancel</button></>:i.status!=="UNAVAILABLE"&&i.status!=="BORROWED"&&i.status!=="RESERVED"&&<><button className="text-button" onClick={()=>{setEditId(i.item_id);setEditName(i.item_name)}}>Edit</button><button className="text-button danger" onClick={()=>void action(`/items/${i.item_id}`,"DELETE")}>Deactivate</button></>}</div></div>):<p className="muted">Your listings will appear here.</p>}</section>
    <section className="panel"><h2>List an item</h2><form className="form-stack" onSubmit={addItem}><label className="label">Name<input className="input" required maxLength={150} value={form.item_name} onChange={e=>setForm({...form,item_name:e.target.value})}/></label><label className="label">Category<select className="select" required value={form.category_id} onChange={e=>setForm({...form,category_id:e.target.value})}><option value="">Choose category</option>{categories.map(c=><option key={c.category_id} value={c.category_id}>{c.category_name}</option>)}</select></label><label className="label">Description<textarea className="input" maxLength={10000} value={form.description} onChange={e=>setForm({...form,description:e.target.value})}/></label><label className="label">Condition<input className="input" maxLength={100} value={form.condition} onChange={e=>setForm({...form,condition:e.target.value})}/></label><div className="filters"><label className="label">Value<input className="input" type="number" min="0.01" step="0.01" required value={form.estimated_value} onChange={e=>setForm({...form,estimated_value:e.target.value})}/></label><label className="label">Deposit<input className="input" type="number" min="0" step="0.01" value={form.deposit_amount} onChange={e=>setForm({...form,deposit_amount:e.target.value})}/></label></div><label className="label">Item photo (JPEG, PNG, WebP; up to 5 MB)<input className="input" ref={imageInput} type="file" accept="image/jpeg,image/png,image/webp" required disabled={Boolean(imageRetry)||imageBusy} onChange={e=>{const file=e.target.files?.[0]??null;if(file&&file.size>5*1024*1024){setError("Choose an image that is 5 MB or smaller.");e.target.value="";setImageFile(null);return}setError("");setImageFile(file)}}/></label><button className="button" disabled={imageBusy||Boolean(imageRetry)}>{imageBusy?"Saving item…":"Publish listing"}</button></form></section></>}
   {!isLender&&<section className="panel"><h2>Requests you sent</h2>{mine.length?mine.map(r=><div className="row" key={r.request_id}><div><b>{r.item_name}</b><small>{r.start_date} – {r.end_date} · {r.status}</small></div><div><span className="pill">{r.status}</span>{r.status==="PENDING"&&<button className="text-button" onClick={()=>void action(`/requests/${r.request_id}/cancel`)}>Cancel</button>}<button className="text-button" onClick={()=>void messageRequest(r.request_id)}>Message</button></div></div>):<p className="muted">Borrow requests you make show here.</p>}</section>}
   {isLender&&<section className="panel"><h2>Requests for your items</h2>{incoming.length?incoming.map(r=><div className="row" key={r.request_id}><div><b>{r.item_name}</b><small>{r.borrower_name} · {r.start_date} – {r.end_date}</small></div><div>{r.status==="PENDING"?<><button className="text-button" onClick={()=>void action(`/requests/${r.request_id}`,"PATCH",{decision:"APPROVED"})}>Accept</button><button className="text-button danger" onClick={()=>void action(`/requests/${r.request_id}`,"PATCH",{decision:"REJECTED"})}>Reject</button></>:r.status==="APPROVED"?<button className="text-button" onClick={()=>void action(`/requests/${r.request_id}/handover`,"POST",{borrow_date:r.start_date,due_date:r.end_date,condition_before:"Condition recorded at handover"})}>Record handover</button>:<span className="pill">{r.status}</span>}<button className="text-button" onClick={()=>void messageRequest(r.request_id)}>Message</button></div></div>):<p className="muted">Incoming requests will appear here.</p>}</section>}
   <section className="panel" style={{gridColumn:"1 / -1"}}><h2>Borrowing history</h2>{history.length?history.map(t=><div className="row" key={t.transaction_id}><div><b>{t.item_name}</b><small>{t.borrow_date} to {t.due_date} · Owner {t.owner_name} · Borrower {t.borrower_name}</small></div><div><span className="pill">{t.status}</span>{["ACTIVE","OVERDUE"].includes(t.status)&&<button className="text-button" onClick={()=>void action(`/transactions/${t.transaction_id}/return`,"POST",{return_date:new Date(Date.now()-new Date().getTimezoneOffset()*60000).toISOString().slice(0,10),condition_after:"Returned in recorded condition"})}>Record return</button>}{t.status==="RETURNED"&&<button className="text-button" onClick={()=>void action(`/transactions/${t.transaction_id}/reviews`,"POST",{rating:5,comment:"Thank you for sharing through BorrowNear."})}>Leave review</button>}</div></div>):<p className="muted">Completed and active transactions appear here.</p>}</section>
  </div>{isLender&&<p className="muted" style={{marginTop:18}}>Localities: {locations.map(l=>l.locality).join(" · ")}</p>}
 </div>;
}

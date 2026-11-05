export type Item = {
  item_id: number; owner_id: number; owner_name: string; category_id: number;
  category_name: string; item_name: string; description: string | null;
  item_condition: string | null; estimated_value: number; deposit_amount: number;
  status: string; locality: string; city: string; pincode: string;
};
export type RequestRow = {request_id:number;item_id:number;item_name:string;borrower_id?:number;borrower_name?:string;owner_id?:number;owner_name?:string;start_date:string;end_date:string;status:string};
const base="/api/v1";
export class ApiError extends Error {
  constructor(message:string,readonly status:number,readonly endpoint:string){super(message);this.name="ApiError";}
}
function notifySessionChanged(){if(typeof window!=="undefined")window.dispatchEvent(new Event("borrownear-session-change"));}
export function token(){if(typeof window==="undefined")return null;return sessionStorage.getItem("borrownear_token");}
export function sessionUser():{role?:string}|null{if(typeof window==="undefined")return null;try{return JSON.parse(sessionStorage.getItem("borrownear_user")||"null")}catch{return null}}
export function saveSession(accessToken:string,user:unknown){sessionStorage.setItem("borrownear_token",accessToken);sessionStorage.setItem("borrownear_user",JSON.stringify(user));notifySessionChanged();}
export function clearSession(){sessionStorage.removeItem("borrownear_token");sessionStorage.removeItem("borrownear_user");notifySessionChanged();}
export async function api<T>(path:string,options:RequestInit={}):Promise<T>{
  const headers=new Headers(options.headers);headers.set("Accept","application/json");
  if(options.body&&!(options.body instanceof FormData))headers.set("Content-Type","application/json");
  const auth=token();if(auth)headers.set("Authorization",`Bearer ${auth}`);
  let response:Response;
  try{response=await fetch(`${base}${path}`,{...options,headers,cache:"no-store"});}
  catch{throw new Error("BorrowNear API is unavailable. Start the FastAPI server and check its health endpoint.");}
  if(!response.ok){const body=await response.json().catch(()=>({}));const detail=body.detail;
    throw new ApiError(typeof detail==="string"?detail:`Request failed (${response.status})`,response.status,path);}
  return response.json() as Promise<T>;
}

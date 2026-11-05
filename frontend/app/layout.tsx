import type { Metadata } from "next";
import "./globals.css";
import "./item-images.css";
import "./access.css";
import {Shell} from "@/components/Shell";

export const metadata:Metadata={title:"BorrowNear — Borrow from your neighbourhood",description:"A community marketplace for borrowing useful things nearby."};
export default function RootLayout({children}:{children:React.ReactNode}){return <html lang="en"><body><Shell>{children}</Shell></body></html>;}

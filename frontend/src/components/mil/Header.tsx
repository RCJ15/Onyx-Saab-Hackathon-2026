"use client";

import Link from "next/link";
import {  useState } from "react";
import { usePathname } from "next/navigation";

const NAV = [
  { href: "/", label: "OVERVIEW" },
  { href: "/training", label: "TRAIN" },
  { href: "/evaluation", label: "EVALUATE" },
  { href: "/knowledge", label: "KNOWLEDGE" },
  { href: "/settings", label: "SETTINGS" },
];

export function Header() {
  const pathname = usePathname();
  const [time,setTime] = useState(new Date().toISOString());

  setInterval(()=>{setTime(new Date().toISOString()  )},1000)

  return (
    <header className="border-b border-mil-bright bg-surface-0">
      <div className="px-4 py-2 flex items-center justify-between border-b border-mil">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <span className="mil-dot mil-dot-active" />
            <span className="mil-heading text-sm">BOREAL PASSAGE</span>
            <span className="text-dim text-xs tracking-widest">// C2 CONSOLE</span>
          </div>
        </div>
        <div className="flex items-center gap-4 text-xs">
          <span className="text-dim">UNCLASSIFIED // HACKATHON-USE</span>
          <span className="text-accent mil-glow">
            {time.split(".")[0].replace("T", " ")}Z
          </span>
        </div>
      </div>
      <nav className="mil-nav px-4">
        {NAV.map((item) => (
          <Link
            key={item.href}
            href={item.href}
            data-state={pathname === item.href ? "active" : "inactive"}
            className="mil-nav-item no-underline"
          >
            {item.label}
          </Link>
        ))}
      </nav>
    </header>
  );
}

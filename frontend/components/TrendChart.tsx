"use client";

import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

export function TrendChart({ monthly, category }: { monthly: Array<{ month: string; counts: Record<string, number>; total: number }>; category: string }) {
  const data = monthly.map((point) => ({
    month: new Date(`${point.month}-02T12:00:00`).toLocaleDateString("en-US", { month: "short", year: "2-digit" }),
    count: category === "All categories" ? point.total : point.counts[category] || 0,
  }));
  return (
    <div className="chart" role="img" aria-label={`Monthly complaint chart for ${category}`}>
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ top: 12, right: 8, left: -18, bottom: 0 }}>
          <defs>
            <linearGradient id="tealFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#0b7d77" stopOpacity={0.3} />
              <stop offset="95%" stopColor="#0b7d77" stopOpacity={0.02} />
            </linearGradient>
          </defs>
          <CartesianGrid stroke="#dde3df" strokeDasharray="3 5" vertical={false} />
          <XAxis dataKey="month" tick={{ fill: "#65716c", fontSize: 12 }} axisLine={false} tickLine={false} />
          <YAxis allowDecimals={false} tick={{ fill: "#65716c", fontSize: 12 }} axisLine={false} tickLine={false} />
          <Tooltip contentStyle={{ borderRadius: 12, border: "1px solid #d6ded9", boxShadow: "0 10px 30px rgba(8,31,44,.1)" }} />
          <Area type="monotone" dataKey="count" stroke="#0b7d77" strokeWidth={3} fill="url(#tealFill)" activeDot={{ r: 5 }} />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

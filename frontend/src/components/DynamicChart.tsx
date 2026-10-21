"use client";

import React, { useMemo } from "react";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  Legend,
} from "recharts";
import { ChartSpec } from "@/types/chat";

interface Props {
  spec: ChartSpec;
}

const PALETTE = [
  "#38bdf8", // sky-400
  "#818cf8", // indigo-400
  "#34d399", // emerald-400
  "#fbbf24", // amber-400
  "#f472b6", // pink-400
  "#a78bfa", // violet-400
  "#2dd4bf", // teal-400
  "#fb923c", // orange-400
];

const CustomTooltip = ({ active, payload, label }: any) => {
  if (active && payload && payload.length) {
    return (
      <div className="bg-slate-900/95 border border-slate-700/80 p-3 rounded-xl shadow-2xl text-xs backdrop-blur-md min-w-[160px]">
        <p className="font-semibold text-slate-200 mb-1.5 border-b border-slate-800 pb-1">{label}</p>
        <div className="space-y-1">
          {payload.map((entry: any, index: number) => {
            const val = entry.value;
            const isCurr =
              typeof val === "number" &&
              (val > 100 ||
                String(entry.name).toLowerCase().includes("revenue") ||
                String(entry.name).toLowerCase().includes("sales") ||
                String(entry.name).toLowerCase().includes("price"));
            return (
              <p key={`item-${index}`} className="text-slate-300 flex items-center justify-between gap-3">
                <span className="flex items-center gap-1.5">
                  <span
                    className="w-2 h-2 rounded-full inline-block"
                    style={{ backgroundColor: entry.color || entry.fill }}
                  />
                  <span className="capitalize text-slate-400">{entry.name}:</span>
                </span>
                <span className="font-mono font-semibold text-white">
                  {typeof val === "number"
                    ? isCurr
                      ? `$${val.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
                      : val.toLocaleString()
                    : val}
                </span>
              </p>
            );
          })}
        </div>
      </div>
    );
  }
  return null;
};

export default function DynamicChart({ spec }: Props) {
  if (!spec || !spec.data || spec.data.length === 0) {
    return null;
  }

  const { type, title, x_axis, y_axis, data } = spec;

  // 1. Client-Side Resilience & Auto-Pivoting for Multi-Dimensional Data
  const processedData = useMemo(() => {
    if (!data || data.length === 0) return [];

    const xKey = x_axis;
    const xVals = data.map((d) => d[xKey]);
    const hasDuplicates = new Set(xVals).size !== xVals.length;
    const allKeys = Object.keys(data[0] || {});

    // If duplicate x_axis values and 3 columns (e.g. category, year, revenue), auto-pivot
    if (hasDuplicates && allKeys.length === 3) {
      const metricKey =
        allKeys.find((k) => {
          if (k === xKey) return false;
          const val = data[0][k];
          return (
            typeof val === "number" ||
            (!isNaN(Number(String(val).replace(/[$,\s]/g, ""))) && String(val).trim() !== "")
          );
        }) || y_axis;

      const groupKey = allKeys.find((k) => k !== xKey && k !== metricKey);

      if (groupKey && metricKey) {
        const pivoted: Record<string, any> = {};
        for (const item of data) {
          const xVal = item[xKey];
          const gVal = String(item[groupKey]);
          const rawM = item[metricKey];
          const mNum =
            typeof rawM === "number"
              ? rawM
              : Number(String(rawM).replace(/[$,\s]/g, "")) || 0;

          if (!pivoted[xVal]) {
            pivoted[xVal] = { [xKey]: xVal };
          }
          pivoted[xVal][gVal] = mNum;
        }
        return Object.values(pivoted);
      }
    }

    // Standard sanitize: clean all numeric strings to raw numbers
    return data.map((item) => {
      const clean: Record<string, any> = { ...item };
      for (const [k, v] of Object.entries(item)) {
        if (k !== xKey && typeof v === "string" && /^[$\s]*[-+]?[0-9,]+(?:\.[0-9]+)?$/.test(v.trim())) {
          const num = Number(v.replace(/[$,\s]/g, ""));
          if (!isNaN(num)) {
            clean[k] = num;
          }
        }
      }
      return clean;
    });
  }, [data, x_axis, y_axis]);

  // 2. Discover all numeric metrics to plot
  const numericKeys = useMemo(() => {
    if (!processedData || processedData.length === 0) return [];
    const sample = processedData[0];
    const keys: string[] = [];

    // Check if y_axis matches an existing key (case-insensitively or directly)
    let matchedY: string | null = null;
    if (y_axis) {
      for (const k of Object.keys(sample)) {
        if (k.toLowerCase() === y_axis.toLowerCase()) {
          matchedY = k;
          break;
        }
      }
    }

    for (const [k, v] of Object.entries(sample)) {
      if (k === x_axis) continue;
      if (typeof v === "number" && !isNaN(v)) {
        keys.push(k);
      }
    }

    // Fallback to matchedY or keys[1] if keys is empty
    if (keys.length === 0 && matchedY) {
      keys.push(matchedY);
    }
    if (keys.length === 0) {
      const remaining = Object.keys(sample).filter((k) => k !== x_axis);
      if (remaining.length > 0) {
        keys.push(remaining[0]);
      }
    }
    return keys;
  }, [processedData, x_axis, y_axis]);

  // 3. Format Y-Axis values intelligently
  const formatYAxis = (v: number) => {
    if (Math.abs(v) >= 1000000) {
      return `$${(v / 1000000).toFixed(1)}M`;
    }
    if (Math.abs(v) >= 1000) {
      return `$${(v / 1000).toFixed(0)}k`;
    }
    return v.toLocaleString();
  };

  const renderChart = () => {
    switch (type) {
      case "line":
        return (
          <LineChart data={processedData} margin={{ top: 15, right: 25, left: 15, bottom: 30 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#334155" opacity={0.4} />
            <XAxis
              dataKey={x_axis}
              stroke="#94a3b8"
              fontSize={11}
              tickLine={false}
              angle={-20}
              textAnchor="end"
              height={45}
            />
            <YAxis stroke="#94a3b8" fontSize={11} tickLine={false} tickFormatter={formatYAxis} />
            <Tooltip content={<CustomTooltip />} />
            {numericKeys.length > 1 && (
              <Legend wrapperStyle={{ fontSize: "11px", color: "#94a3b8", paddingTop: "8px" }} />
            )}
            {numericKeys.map((key, idx) => (
              <Line
                key={key}
                type="monotone"
                dataKey={key}
                name={key.replace(/_/g, " ").toUpperCase()}
                stroke={PALETTE[idx % PALETTE.length]}
                strokeWidth={2.5}
                dot={{ r: 4, fill: PALETTE[idx % PALETTE.length] }}
                activeDot={{ r: 6 }}
              />
            ))}
          </LineChart>
        );

      case "area":
        return (
          <AreaChart data={processedData} margin={{ top: 15, right: 25, left: 15, bottom: 30 }}>
            <defs>
              {numericKeys.map((key, idx) => (
                <linearGradient key={`grad-${key}`} id={`grad-${key}`} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor={PALETTE[idx % PALETTE.length]} stopOpacity={0.7} />
                  <stop offset="95%" stopColor={PALETTE[idx % PALETTE.length]} stopOpacity={0.05} />
                </linearGradient>
              ))}
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#334155" opacity={0.4} />
            <XAxis
              dataKey={x_axis}
              stroke="#94a3b8"
              fontSize={11}
              tickLine={false}
              angle={-20}
              textAnchor="end"
              height={45}
            />
            <YAxis stroke="#94a3b8" fontSize={11} tickLine={false} tickFormatter={formatYAxis} />
            <Tooltip content={<CustomTooltip />} />
            {numericKeys.length > 1 && (
              <Legend wrapperStyle={{ fontSize: "11px", color: "#94a3b8", paddingTop: "8px" }} />
            )}
            {numericKeys.map((key, idx) => (
              <Area
                key={key}
                type="monotone"
                dataKey={key}
                name={key.replace(/_/g, " ").toUpperCase()}
                stroke={PALETTE[idx % PALETTE.length]}
                fillOpacity={1}
                fill={`url(#grad-${key})`}
              />
            ))}
          </AreaChart>
        );

      case "pie":
        return (
          <PieChart margin={{ top: 10, right: 10, left: 10, bottom: 10 }}>
            <Tooltip content={<CustomTooltip />} />
            <Legend wrapperStyle={{ fontSize: "11px", color: "#94a3b8" }} iconType="circle" />
            <Pie
              data={processedData}
              dataKey={numericKeys[0] || y_axis}
              nameKey={x_axis}
              cx="50%"
              cy="50%"
              outerRadius={85}
              innerRadius={45}
              paddingAngle={3}
              label={({ percent }) =>
                percent !== undefined ? `${(percent * 100).toFixed(0)}%` : ""
              }
              labelLine={false}
            >
              {processedData.map((_, index) => (
                <Cell key={`cell-${index}`} fill={PALETTE[index % PALETTE.length]} />
              ))}
            </Pie>
          </PieChart>
        );

      case "bar":
      default:
        return (
          <BarChart data={processedData} margin={{ top: 15, right: 25, left: 15, bottom: 30 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#334155" opacity={0.4} />
            <XAxis
              dataKey={x_axis}
              stroke="#94a3b8"
              fontSize={11}
              tickLine={false}
              angle={-20}
              textAnchor="end"
              height={45}
            />
            <YAxis stroke="#94a3b8" fontSize={11} tickLine={false} tickFormatter={formatYAxis} />
            <Tooltip content={<CustomTooltip />} />
            {numericKeys.length > 1 && (
              <Legend wrapperStyle={{ fontSize: "11px", color: "#94a3b8", paddingTop: "8px" }} />
            )}
            {numericKeys.length > 1 ? (
              // Multiple series: grouped bars side-by-side with distinct colors
              numericKeys.map((key, idx) => (
                <Bar
                  key={key}
                  dataKey={key}
                  name={key.replace(/_/g, " ").toUpperCase()}
                  fill={PALETTE[idx % PALETTE.length]}
                  radius={[4, 4, 0, 0]}
                />
              ))
            ) : (
              // Single series: colored bar per category
              <Bar dataKey={numericKeys[0] || y_axis} radius={[4, 4, 0, 0]}>
                {processedData.map((_, index) => (
                  <Cell key={`cell-${index}`} fill={PALETTE[index % PALETTE.length]} />
                ))}
              </Bar>
            )}
          </BarChart>
        );
    }
  };

  return (
    <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-4 my-3">
      {title && (
        <h4 className="text-sm font-semibold text-slate-200 mb-3 text-center sm:text-left flex items-center justify-between">
          <span>{title}</span>
          <span className="text-[10px] font-mono uppercase bg-slate-800 px-2 py-0.5 rounded text-sky-400 border border-slate-700/60">
            {type} chart
          </span>
        </h4>
      )}
      <div className="w-full h-64 sm:h-72">
        <ResponsiveContainer width="100%" height="100%">
          {renderChart()}
        </ResponsiveContainer>
      </div>
    </div>
  );
}

"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { ArrowLeft, BookOpen, Search, Zap, FileText } from "lucide-react";

interface RuleItem {
  file_path: string;
  title: string;
  description: string;
  tags: string[];
  metadata?: Record<string, any>;
}

export default function OKFRulesPage() {
  const [rules, setRules] = useState<RuleItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedTag, setSelectedTag] = useState<string | null>(null);

  useEffect(() => {
    fetch("/api/contract-assistant/rules")
      .then((res) => res.json())
      .then((data) => {
        setRules(data.rules || []);
        setLoading(false);
      })
      .catch((err) => {
        console.error("Failed to load OKF rules", err);
        setLoading(false);
      });
  }, []);

  const allTags = Array.from(new Set(rules.flatMap((r) => r.tags || [])));

  const filteredRules = rules.filter((r) => {
    const matchesSearch =
      r.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      r.description.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesTag = !selectedTag || (r.tags && r.tags.includes(selectedTag));
    return matchesSearch && matchesTag;
  });

  return (
    <div className="p-4 sm:p-6 max-w-7xl mx-auto space-y-6">
      {/* Header Banner */}
      <div className="bg-[#3C0A12] text-white p-6 rounded-2xl border-2 border-[#120F0A] shadow-[6px_6px_0px_0px_#120F0A] flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        <div>
          <Link
            href="/dashboard/contract-assistant"
            className="inline-flex items-center gap-1.5 text-xs font-bold text-[#FED39E] hover:underline mb-2"
          >
            <ArrowLeft className="w-3.5 h-3.5" /> Back to Pipeline Board
          </Link>
          <div className="flex items-center gap-2">
            <BookOpen className="w-6 h-6 text-[#FC920D]" />
            <h1 className="text-xl sm:text-2xl font-black font-sans">
              OKF Legal &amp; Governance Rules
            </h1>
          </div>
          <p className="text-xs text-[#FED39E] font-medium mt-1">
            Read-only playbook reference of active policy rules and MCA Section-8 compliance parameters.
          </p>
        </div>

        <div className="bg-[#FC920D] text-[#120F0A] text-xs font-black px-4 py-2 rounded-xl border-2 border-[#120F0A] shadow-[2px_2px_0px_0px_#120F0A]">
          {rules.length} Active Rules Synced
        </div>
      </div>

      {/* Search & Tag Filters */}
      <div className="flex flex-col md:flex-row items-center justify-between gap-4">
        <div className="relative w-full md:w-80">
          <Search className="w-4 h-4 absolute left-3.5 top-1/2 -translate-y-1/2 text-[#716F6C]" />
          <input
            type="text"
            placeholder="Search rules or policy tags..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-10 pr-4 py-2 bg-white border-2 border-[#120F0A] rounded-xl text-xs font-bold focus:outline-none focus:ring-2 focus:ring-[#97192C] shadow-[2px_2px_0px_0px_#120F0A]"
          />
        </div>

        {allTags.length > 0 && (
          <div className="flex items-center gap-2 overflow-x-auto pb-1 max-w-full">
            <button
              onClick={() => setSelectedTag(null)}
              className={`px-3 py-1 text-xs font-bold rounded-lg border transition-all shrink-0 ${
                !selectedTag
                  ? "bg-[#97192C] text-white border-[#120F0A]"
                  : "bg-white text-[#120F0A] border-[#D0CFCE] hover:bg-gray-100"
              }`}
            >
              All Tags
            </button>
            {allTags.map((tag) => (
              <button
                key={tag}
                onClick={() => setSelectedTag(tag)}
                className={`px-3 py-1 text-xs font-bold rounded-lg border transition-all shrink-0 uppercase tracking-wider ${
                  selectedTag === tag
                    ? "bg-[#97192C] text-white border-[#120F0A]"
                    : "bg-white text-[#120F0A] border-[#D0CFCE] hover:bg-gray-100"
                }`}
              >
                {tag}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Rules Grid */}
      {loading ? (
        <div className="p-8 text-center text-xs font-bold text-[#716F6C]">
          Loading OKF playbook rules...
        </div>
      ) : filteredRules.length === 0 ? (
        <div className="p-12 text-center bg-white border-2 border-[#120F0A] rounded-2xl shadow-[4px_4px_0px_0px_#120F0A] space-y-2">
          <FileText className="w-8 h-8 text-[#716F6C] mx-auto" />
          <div className="text-xs font-bold text-[#120F0A]">No rules matching query</div>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {filteredRules.map((rule, idx) => (
            <div
              key={idx}
              className="bg-white border-2 border-[#120F0A] p-5 rounded-2xl shadow-[4px_4px_0px_0px_#120F0A] space-y-3"
            >
              <div className="flex items-start justify-between gap-2">
                <div className="flex items-center gap-2">
                  <Zap className="w-4 h-4 text-[#97192C] shrink-0" />
                  <h3 className="text-sm font-black text-[#120F0A]">{rule.title}</h3>
                </div>
                <span className="text-[10px] font-mono text-[#716F6C] bg-gray-100 border border-gray-300 px-2 py-0.5 rounded shrink-0">
                  {rule.file_path}
                </span>
              </div>

              <p className="text-xs text-[#413F3B] font-medium leading-relaxed">
                {rule.description}
              </p>

              {rule.tags && rule.tags.length > 0 && (
                <div className="flex items-center gap-1.5 pt-2 border-t border-[#D0CFCE]">
                  {rule.tags.map((t, tidx) => (
                    <span
                      key={tidx}
                      className="bg-[#FEE9CF] text-[#97192C] border border-[#120F0A] text-[9px] font-black uppercase px-2 py-0.5 rounded"
                    >
                      {t}
                    </span>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

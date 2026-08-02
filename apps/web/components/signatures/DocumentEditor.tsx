"use client";

import React, { useState } from "react";
import { ChevronLeft, ChevronRight, PenTool, User, Calendar, Type, CheckSquare, Trash2 } from "lucide-react";

export interface RecipientConfig {
  id: string;
  name: string;
  email: string;
  color: string;
}

export interface PlacedField {
  id: string;
  recipient_id: string;
  type: "signature" | "fullname" | "date" | "text" | "checkbox";
  page_number: number;
  pos_x: number; // percentage (0-100)
  pos_y: number; // percentage (0-100)
  width: number; // percentage (0-100)
  height: number; // percentage (0-100)
  required: boolean;
}

interface DocumentEditorProps {
  previews: string[];
  recipients: RecipientConfig[];
  fields: PlacedField[];
  onChangeFields: (fields: PlacedField[]) => void;
  selectedRecipientId: string;
  onSelectRecipient: (id: string) => void;
}

const FIELD_TYPES = [
  { type: "signature", label: "Signature", icon: PenTool, defaultW: 24, defaultH: 7 },
  { type: "fullname", label: "Full Name", icon: User, defaultW: 20, defaultH: 5 },
  { type: "date", label: "Date Signed", icon: Calendar, defaultW: 16, defaultH: 4 },
  { type: "text", label: "Text Field", icon: Type, defaultW: 22, defaultH: 5 },
  { type: "checkbox", label: "Checkbox", icon: CheckSquare, defaultW: 6, defaultH: 4 },
] as const;

export function DocumentEditor({
  previews,
  recipients,
  fields,
  onChangeFields,
  selectedRecipientId,
  onSelectRecipient,
}: DocumentEditorProps) {
  const [currentPage, setCurrentPage] = useState(1);
  const totalPages = previews.length;

  const handleAddField = (type: PlacedField["type"], defaultW: number, defaultH: number) => {
    if (!selectedRecipientId) return;
    const newField: PlacedField = {
      id: `field_${Date.now()}_${Math.random().toString(36).substring(2, 7)}`,
      recipient_id: selectedRecipientId,
      type,
      page_number: currentPage,
      pos_x: 35, // default center position %
      pos_y: 40,
      width: defaultW,
      height: defaultH,
      required: true,
    };
    onChangeFields([...fields, newField]);
  };

  const handleRemoveField = (id: string) => {
    onChangeFields(fields.filter((f) => f.id !== id));
  };

  const activePageFields = fields.filter((f) => f.page_number === currentPage);

  return (
    <div className="flex flex-col lg:flex-row gap-6 w-full">
      {/* Sidebar Tool Palette */}
      <div className="w-full lg:w-72 bg-[#FAF8F5] border-2 border-[#120F0A] rounded-xl p-4 shadow-[4px_4px_0px_0px_#120F0A] flex flex-col gap-5">
        <div>
          <label className="block text-xs font-bold uppercase tracking-wider text-[#716F6C] mb-2">
            Select Signatory
          </label>
          <div className="space-y-2">
            {recipients.map((r) => (
              <button
                key={r.id}
                type="button"
                onClick={() => onSelectRecipient(r.id)}
                className={`w-full flex items-center justify-between p-2.5 rounded-lg border-2 text-xs font-bold transition-all ${
                  selectedRecipientId === r.id
                    ? "border-[#120F0A] bg-white shadow-[2px_2px_0px_0px_#120F0A]"
                    : "border-transparent bg-gray-100 text-[#413F3B]"
                }`}
              >
                <div className="flex items-center gap-2 truncate">
                  <span className="w-3 h-3 rounded-full border border-[#120F0A]" style={{ backgroundColor: r.color }} />
                  <span className="truncate">{r.name}</span>
                </div>
                <span className="text-[10px] text-[#716F6C] font-mono">{r.email}</span>
              </button>
            ))}
          </div>
        </div>

        <hr className="border-[#D0CFCE]" />

        <div>
          <label className="block text-xs font-bold uppercase tracking-wider text-[#716F6C] mb-2">
            Click to Add Field
          </label>
          <div className="grid grid-cols-1 gap-2">
            {FIELD_TYPES.map((ft) => {
              const Icon = ft.icon;
              return (
                <button
                  key={ft.type}
                  type="button"
                  onClick={() => handleAddField(ft.type, ft.defaultW, ft.defaultH)}
                  className="flex items-center gap-2.5 px-3 py-2 bg-white border-2 border-[#120F0A] rounded-lg text-xs font-bold text-[#120F0A] hover:bg-[#FEE9CF] transition-colors shadow-[2px_2px_0px_0px_#120F0A] active:translate-y-[1px]"
                >
                  <Icon className="w-4 h-4 text-[#97192C]" />
                  <span>{ft.label}</span>
                </button>
              );
            })}
          </div>
        </div>
      </div>

      {/* Main Canvas Document Viewer */}
      <div className="flex-1 bg-[#120F0A] border-2 border-[#120F0A] rounded-xl p-4 flex flex-col items-center gap-4">
        {/* Page Toolbar */}
        <div className="flex items-center justify-between w-full max-w-2xl bg-[#413F3B] px-4 py-2 rounded-lg text-white text-xs font-bold">
          <button
            type="button"
            disabled={currentPage <= 1}
            onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
            className="flex items-center gap-1 hover:text-[#FC920D] disabled:opacity-30"
          >
            <ChevronLeft className="w-4 h-4" /> Prev Page
          </button>
          <span>
            Page {currentPage} of {totalPages || 1}
          </span>
          <button
            type="button"
            disabled={currentPage >= totalPages}
            onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
            className="flex items-center gap-1 hover:text-[#FC920D] disabled:opacity-30"
          >
            Next Page <ChevronRight className="w-4 h-4" />
          </button>
        </div>

        {/* PDF Page Canvas Wrapper */}
        <div className="relative w-full max-w-2xl bg-white border-2 border-[#120F0A] rounded-lg overflow-hidden shadow-2xl">
          {previews[currentPage - 1] ? (
            <img
              src={previews[currentPage - 1]}
              alt={`Page ${currentPage}`}
              className="w-full h-auto pointer-events-none select-none"
            />
          ) : (
            <div className="w-full h-96 flex items-center justify-center text-gray-400 text-sm">
              Loading Page Preview...
            </div>
          )}

          {/* Render Placed Fields on Current Page */}
          {activePageFields.map((field) => {
            const recipient = recipients.find((r) => r.id === field.recipient_id);
            const color = recipient?.color || "#97192C";

            return (
              <div
                key={field.id}
                style={{
                  left: `${field.pos_x}%`,
                  top: `${field.pos_y}%`,
                  width: `${field.width}%`,
                  height: `${field.height}%`,
                  borderColor: color,
                  backgroundColor: `${color}1A`,
                }}
                className="absolute border-2 rounded p-1 flex items-center justify-between text-xs font-bold cursor-move shadow-md select-none group"
              >
                <div className="flex items-center gap-1 truncate text-[10px] uppercase font-bold text-[#120F0A]">
                  <span className="w-2 h-2 rounded-full" style={{ backgroundColor: color }} />
                  <span className="truncate">{field.type}</span>
                </div>
                <button
                  type="button"
                  onClick={() => handleRemoveField(field.id)}
                  className="opacity-0 group-hover:opacity-100 p-0.5 bg-red-600 text-white rounded hover:bg-red-700 transition-opacity"
                >
                  <Trash2 className="w-3 h-3" />
                </button>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

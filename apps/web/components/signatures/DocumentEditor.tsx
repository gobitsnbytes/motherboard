"use client";

import React, { useState, useRef } from "react";
import { ChevronLeft, ChevronRight, PenTool, User, Calendar, Type, CheckSquare, Trash2, ZoomIn, ZoomOut, Move, Lightbulb } from "lucide-react";

export interface RecipientConfig {
  id: string;
  name: string;
  email: string;
  color: string;
  requires_otp?: boolean;
  allowed_sig_type?: string;
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
  const [zoom, setZoom] = useState(100);
  const [activeTool, setActiveTool] = useState<PlacedField["type"] | null>("signature");
  const imgContainerRef = useRef<HTMLDivElement | null>(null);
  const [draggingFieldId, setDraggingFieldId] = useState<string | null>(null);
  const dragOffset = useRef<{ x: number; y: number }>({ x: 0, y: 0 });

  const totalPages = previews.length;

  const handlePageClick = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!activeTool || !selectedRecipientId || !imgContainerRef.current) return;
    if ((e.target as HTMLElement).closest(".field-overlay")) return; // Don't trigger when clicking existing field

    const rect = imgContainerRef.current.getBoundingClientRect();
    const clickX = e.clientX - rect.left;
    const clickY = e.clientY - rect.top;

    const ft = FIELD_TYPES.find((f) => f.type === activeTool);
    const defaultW = ft ? ft.defaultW : 20;
    const defaultH = ft ? ft.defaultH : 5;

    // Calculate percentage coordinates centered on click
    let posX = (clickX / rect.width) * 100 - defaultW / 2;
    let posY = (clickY / rect.height) * 100 - defaultH / 2;

    posX = Math.max(0, Math.min(100 - defaultW, posX));
    posY = Math.max(0, Math.min(100 - defaultH, posY));

    const newField: PlacedField = {
      id: `field_${Date.now()}_${Math.random().toString(36).substring(2, 7)}`,
      recipient_id: selectedRecipientId,
      type: activeTool,
      page_number: currentPage,
      pos_x: Number(posX.toFixed(2)),
      pos_y: Number(posY.toFixed(2)),
      width: defaultW,
      height: defaultH,
      required: true,
    };

    onChangeFields([...fields, newField]);
  };

  const handleRemoveField = (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    onChangeFields(fields.filter((f) => f.id !== id));
  };

  const handleMouseDownField = (e: React.MouseEvent, field: PlacedField) => {
    e.stopPropagation();
    setDraggingFieldId(field.id);
    if (imgContainerRef.current) {
      const rect = imgContainerRef.current.getBoundingClientRect();
      const fieldX = (field.pos_x / 100) * rect.width;
      const fieldY = (field.pos_y / 100) * rect.height;
      dragOffset.current = {
        x: e.clientX - rect.left - fieldX,
        y: e.clientY - rect.top - fieldY,
      };
    }
  };

  const handleMouseMoveContainer = (e: React.MouseEvent) => {
    if (!draggingFieldId || !imgContainerRef.current) return;
    const rect = imgContainerRef.current.getBoundingClientRect();
    const targetField = fields.find((f) => f.id === draggingFieldId);
    if (!targetField) return;

    let newX = e.clientX - rect.left - dragOffset.current.x;
    let newY = e.clientY - rect.top - dragOffset.current.y;

    let posX = (newX / rect.width) * 100;
    let posY = (newY / rect.height) * 100;

    posX = Math.max(0, Math.min(100 - targetField.width, posX));
    posY = Math.max(0, Math.min(100 - targetField.height, posY));

    onChangeFields(
      fields.map((f) =>
        f.id === draggingFieldId
          ? { ...f, pos_x: Number(posX.toFixed(2)), pos_y: Number(posY.toFixed(2)) }
          : f
      )
    );
  };

  const handleMouseUpContainer = () => {
    setDraggingFieldId(null);
  };

  const activePageFields = fields.filter((f) => f.page_number === currentPage);

  return (
    <div className="flex flex-col lg:flex-row gap-6 w-full items-start">
      {/* Sidebar Tool Palette */}
      <div className="w-full lg:w-72 bg-muted border-2 border-border rounded-base p-5 shadow-shadow flex flex-col gap-6 shrink-0">
        <div>
          <label className="block text-xs font-black uppercase tracking-wider text-muted-foreground mb-2 font-heading">
            1. Assign Signatory
          </label>
          <div className="space-y-2">
            {recipients.map((r) => {
              const isSelected = selectedRecipientId === r.id;
              return (
                <button
                  key={r.id}
                  type="button"
                  onClick={() => onSelectRecipient(r.id)}
                  className={`w-full flex items-center justify-between p-3 rounded-base border-2 text-xs font-bold font-heading transition-all ${
                    isSelected
                      ? "border-border bg-secondary-background shadow-shadow"
                      : "border-transparent bg-gray-100 text-foreground hover:bg-gray-200"
                  }`}
                >
                  <div className="flex items-center gap-2.5 truncate">
                    <span className="w-3.5 h-3.5 rounded-full border border-border shrink-0" style={{ backgroundColor: r.color }} />
                    <span className="truncate text-foreground">{r.name}</span>
                  </div>
                  <span className="text-[10px] text-muted-foreground font-mono shrink-0">&lt;{r.email.split("@")[0]}&gt;</span>
                </button>
              );
            })}
          </div>
        </div>

        <hr className="border-[#D0CFCE]" />

        <div>
          <label className="block text-xs font-black uppercase tracking-wider text-muted-foreground mb-2 font-heading">
            2. Select Field Type
          </label>
          <div className="grid grid-cols-1 gap-2">
            {FIELD_TYPES.map((ft) => {
              const Icon = ft.icon;
              const isActive = activeTool === ft.type;
              return (
                <button
                  key={ft.type}
                  type="button"
                  onClick={() => setActiveTool(ft.type)}
                  className={`flex items-center justify-between px-3.5 py-2.5 border-2 rounded-base text-xs font-bold font-heading transition-all ${
                    isActive
                      ? "bg-orange text-foreground border-border shadow-shadow"
                      : "bg-secondary-background border-border text-foreground hover:bg-orange/20"
                  }`}
                >
                  <div className="flex items-center gap-2.5">
                    <Icon className="w-4 h-4 text-burgundy" />
                    <span>{ft.label}</span>
                  </div>
                  {isActive && <span className="text-[10px] uppercase font-black tracking-wider bg-dark text-white px-2 py-0.5 rounded">Active</span>}
                </button>
              );
            })}
          </div>
        </div>

        <div className="bg-orange/20 border-2 border-border p-3 rounded-base text-[11px] text-foreground font-medium leading-tight">
          <Lightbulb className="mr-1 inline w-3.5 h-3.5" /> <b>Tip:</b> Click anywhere directly on the PDF document preview to place the active field. Drag fields to move them around.
        </div>
      </div>

      {/* Main Canvas Document Viewer */}
      <div className="flex-1 bg-dark border-2 border-border rounded-base p-4 sm:p-6 flex flex-col items-center gap-4 w-full shadow-shadow">
        {/* Page Toolbar Controls */}
        <div className="flex flex-wrap items-center justify-between w-full max-w-2xl bg-blank px-4 py-2.5 rounded-base text-white text-xs font-bold font-heading border border-white/10 gap-2">
          <div className="flex items-center gap-3">
            <button
              type="button"
              disabled={currentPage <= 1}
              onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
              className="flex items-center gap-1 hover:text-orange disabled:opacity-30 transition-colors"
            >
              <ChevronLeft className="w-4 h-4" /> Prev
            </button>
            <span className="font-mono text-orange">
              Page {currentPage} / {totalPages || 1}
            </span>
            <button
              type="button"
              disabled={currentPage >= totalPages}
              onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
              className="flex items-center gap-1 hover:text-orange disabled:opacity-30 transition-colors"
            >
              Next <ChevronRight className="w-4 h-4" />
            </button>
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setZoom((z) => Math.max(75, z - 10))}
              className="p-1 hover:bg-white/20 rounded-base transition-colors"
              title="Zoom Out"
            >
              <ZoomOut className="w-4 h-4" />
            </button>
            <span className="font-mono text-[11px] px-1">{zoom}%</span>
            <button
              type="button"
              onClick={() => setZoom((z) => Math.min(150, z + 10))}
              className="p-1 hover:bg-white/20 rounded-base transition-colors"
              title="Zoom In"
            >
              <ZoomIn className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* PDF Page Canvas Image Box */}
        <div className="w-full overflow-auto flex justify-center py-2">
          <div
            ref={imgContainerRef}
            onClick={handlePageClick}
            onMouseMove={handleMouseMoveContainer}
            onMouseUp={handleMouseUpContainer}
            onMouseLeave={handleMouseUpContainer}
            style={{ width: `${zoom}%` }}
            className="relative max-w-2xl bg-secondary-background border-2 border-border rounded-base overflow-hidden shadow-shadow cursor-crosshair select-none transition-all duration-150"
          >
            {previews[currentPage - 1] ? (
              <img
                src={previews[currentPage - 1]}
                alt={`Page ${currentPage}`}
                className="w-full h-auto pointer-events-none block"
              />
            ) : (
              <div className="w-full h-96 flex items-center justify-center text-gray-400 text-xs font-bold">
                Rendering Page Preview...
              </div>
            )}

            {/* Placed Interactive Field Overlays */}
            {activePageFields.map((field) => {
              const recipient = recipients.find((r) => r.id === field.recipient_id);
              const color = recipient?.color || "#97192C";
              const isDragging = draggingFieldId === field.id;

              return (
                <div
                  key={field.id}
                  onMouseDown={(e) => handleMouseDownField(e, field)}
                  style={{
                    left: `${field.pos_x}%`,
                    top: `${field.pos_y}%`,
                    width: `${field.width}%`,
                    height: `${field.height}%`,
                    borderColor: color,
                    backgroundColor: `${color}20`,
                  }}
                  className={`field-overlay absolute border-2 rounded-base p-1.5 flex items-center justify-between cursor-move shadow-shadow select-none group transition-shadow ${
                    isDragging ? "ring-2 ring-border z-30 scale-[1.02]" : "z-20 hover:z-30"
                  }`}
                >
                  <div className="flex items-center gap-1.5 truncate">
                    <span className="w-2.5 h-2.5 rounded-full border border-border shrink-0" style={{ backgroundColor: color }} />
                    <span className="text-[10px] font-black uppercase tracking-wider text-dark truncate font-heading">
                      {field.type}
                    </span>
                  </div>

                  <div className="flex items-center gap-1 shrink-0">
                    <Move className="w-3 h-3 text-dark/60 opacity-0 group-hover:opacity-100 transition-opacity" />
                    <button
                      type="button"
                      onClick={(e) => handleRemoveField(e, field.id)}
                      className="p-1 bg-burgundy text-white rounded-sm hover:bg-red-800 transition-colors"
                      title="Remove Field"
                    >
                      <Trash2 className="w-3 h-3" />
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}

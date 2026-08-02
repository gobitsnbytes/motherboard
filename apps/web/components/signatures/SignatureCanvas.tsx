"use client";

import React, { useRef, useState, useEffect } from "react";
import { Check, Eraser, Type, PenTool } from "lucide-react";

interface SignatureCanvasProps {
  onSave: (dataUrl: string) => void;
  onCancel?: () => void;
}

const SCRIPT_FONTS = [
  { name: "Cursive Classic", fontClass: "font-serif italic" },
  { name: "Monospace Draft", fontClass: "font-mono" },
  { name: "Bold Script", fontClass: "font-sans font-bold italic" },
] as const;

export function SignatureCanvas({ onSave, onCancel }: SignatureCanvasProps) {
  const [activeTab, setActiveTab] = useState<"draw" | "type">("draw");
  const [typedName, setTypedName] = useState("");
  const [selectedFont, setSelectedFont] = useState<string>(SCRIPT_FONTS[0].fontClass);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const isDrawing = useRef(false);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.lineWidth = 2.5;
    ctx.lineCap = "round";
    ctx.lineJoin = "round";
    ctx.strokeStyle = "#3C0A12"; // Brand Deep Plum
  }, [activeTab]);

  const startDrawing = (e: React.MouseEvent<HTMLCanvasElement> | React.TouchEvent<HTMLCanvasElement>) => {
    isDrawing.current = true;
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const rect = canvas.getBoundingClientRect();
    const clientX = "touches" in e ? e.touches[0].clientX : e.clientX;
    const clientY = "touches" in e ? e.touches[0].clientY : e.clientY;

    ctx.beginPath();
    ctx.moveTo(clientX - rect.left, clientY - rect.top);
  };

  const draw = (e: React.MouseEvent<HTMLCanvasElement> | React.TouchEvent<HTMLCanvasElement>) => {
    if (!isDrawing.current) return;
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const rect = canvas.getBoundingClientRect();
    const clientX = "touches" in e ? e.touches[0].clientX : e.clientX;
    const clientY = "touches" in e ? e.touches[0].clientY : e.clientY;

    ctx.lineTo(clientX - rect.left, clientY - rect.top);
    ctx.stroke();
  };

  const stopDrawing = () => {
    isDrawing.current = false;
  };

  const clearCanvas = () => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
  };

  const handleSave = () => {
    if (activeTab === "draw") {
      const canvas = canvasRef.current;
      if (!canvas) return;
      onSave(canvas.toDataURL("image/png"));
    } else {
      if (!typedName.trim()) return;
      // Render typed text to a canvas data URL
      const tempCanvas = document.createElement("canvas");
      tempCanvas.width = 400;
      tempCanvas.height = 120;
      const ctx = tempCanvas.getContext("2d");
      if (ctx) {
        ctx.fillStyle = "#3C0A12";
        ctx.font = "italic 32px Georgia, serif";
        ctx.fillText(typedName, 20, 70);
        onSave(tempCanvas.toDataURL("image/png"));
      }
    }
  };

  return (
    <div className="bg-[#FAF8F5] border-2 border-[#120F0A] rounded-xl p-4 shadow-[4px_4px_0px_0px_#120F0A] max-w-lg w-full">
      <div className="flex items-center justify-between border-b-2 border-[#120F0A] pb-3 mb-4">
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => setActiveTab("draw")}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold transition-all ${
              activeTab === "draw"
                ? "bg-[#97192C] text-white shadow-[2px_2px_0px_0px_#120F0A]"
                : "bg-white text-[#120F0A] border border-[#120F0A]"
            }`}
          >
            <PenTool className="w-3.5 h-3.5" /> Draw
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("type")}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold transition-all ${
              activeTab === "type"
                ? "bg-[#97192C] text-white shadow-[2px_2px_0px_0px_#120F0A]"
                : "bg-white text-[#120F0A] border border-[#120F0A]"
            }`}
          >
            <Type className="w-3.5 h-3.5" /> Type
          </button>
        </div>
        {activeTab === "draw" && (
          <button
            type="button"
            onClick={clearCanvas}
            className="flex items-center gap-1 px-2.5 py-1 text-xs font-bold text-[#97192C] hover:bg-[#F4D9D1] rounded"
          >
            <Eraser className="w-3.5 h-3.5" /> Clear
          </button>
        )}
      </div>

      {activeTab === "draw" ? (
        <div className="border-2 border-dashed border-[#A09F9D] rounded-lg bg-white overflow-hidden touch-none mb-4">
          <canvas
            ref={canvasRef}
            width={450}
            height={160}
            onMouseDown={startDrawing}
            onMouseMove={draw}
            onMouseUp={stopDrawing}
            onMouseLeave={stopDrawing}
            onTouchStart={startDrawing}
            onTouchMove={draw}
            onTouchEnd={stopDrawing}
            className="w-full cursor-crosshair"
          />
        </div>
      ) : (
        <div className="space-y-4 mb-4">
          <input
            type="text"
            placeholder="Type your full name..."
            value={typedName}
            onChange={(e) => setTypedName(e.target.value)}
            className="w-full px-3 py-2 border-2 border-[#120F0A] rounded-lg text-sm bg-white font-medium focus:outline-none focus:ring-2 focus:ring-[#97192C]"
          />
          <div className="border-2 border-[#120F0A] rounded-lg p-4 bg-white min-h-[100px] flex items-center justify-center">
            <span className={`text-2xl text-[#3C0A12] ${selectedFont}`}>
              {typedName || "Signature Preview"}
            </span>
          </div>
        </div>
      )}

      <div className="flex justify-end gap-2 pt-2 border-t border-[#D0CFCE]">
        {onCancel && (
          <button
            type="button"
            onClick={onCancel}
            className="px-4 py-2 text-xs font-bold border-2 border-[#120F0A] rounded-lg bg-white text-[#120F0A] hover:bg-gray-100"
          >
            Cancel
          </button>
        )}
        <button
          type="button"
          onClick={handleSave}
          className="flex items-center gap-1.5 px-4 py-2 text-xs font-bold bg-[#FC920D] text-[#120F0A] border-2 border-[#120F0A] rounded-lg shadow-[2px_2px_0px_0px_#120F0A] hover:translate-y-[-1px]"
        >
          <Check className="w-4 h-4" /> Adopt & Sign
        </button>
      </div>
    </div>
  );
}
